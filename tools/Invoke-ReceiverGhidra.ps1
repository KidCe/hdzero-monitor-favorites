param(
    [Parameter(Mandatory = $true)][string]$Image,
    [string]$ToolsDirectory = (Join-Path $env:USERPROFILE '.cache\hdzero-monitor-tools'),
    [string]$ProjectName = 'Monitor-DM5680-1R3',
    [switch]$Refresh
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$fixture = (Resolve-Path -LiteralPath $Image).Path
$hash = (Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne 'ca65d71948658569f02715e312d62cf10742cac10ffca4271ee933210c5a5652') {
    throw 'Receiver import requires the unchanged, pinned decoded fixture.'
}
if ($ProjectName -notmatch '^[A-Za-z0-9_-]+$') { throw 'Unexpected project name.' }
$installation = Get-Content -Raw -LiteralPath (Join-Path $ToolsDirectory 'tools.json') | ConvertFrom-Json
$headless = Join-Path $installation.ghidra 'support\analyzeHeadless.bat'
$projectDirectory = Join-Path $workspace 'artifacts\ghidra'
$exportDirectory = Join-Path $workspace ('artifacts\firmware-analysis\receiver-run-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Force -Path $projectDirectory | Out-Null
New-Item -ItemType Directory -Path $exportDirectory | Out-Null
$arguments = @($projectDirectory, $ProjectName)
$projectFile = Join-Path $projectDirectory ($ProjectName + '.gpr')
if (Test-Path -LiteralPath $projectFile) {
    if (-not $Refresh) { throw 'Project exists. Use -Refresh to export and test it.' }
    $arguments += @('-process', [IO.Path]::GetFileName($fixture), '-noanalysis')
} else {
    if ($Refresh) { throw 'Refresh requires an existing project.' }
    $arguments += @('-import', $fixture, '-loader', 'BinaryLoader', '-loader-baseAddr', '0',
                    '-processor', '8051:BE:16:default', '-cspec', 'default', '-analysisTimeoutPerFile', '180',
                    '-preScript', 'ReceiverSeeds.java')
}
$reportPath = Join-Path $exportDirectory 'selection-tests.json'
$arguments += @('-scriptPath', (Join-Path $PSScriptRoot 'ghidra'),
                '-postScript', 'ReceiverExport.java', (Join-Path $exportDirectory 'functions'),
                '-postScript', 'ReceiverSelectionTests.java', $reportPath,
                '-max-cpu', '4', '-log', (Join-Path $exportDirectory 'ghidra.log'))
$previousJava = $env:JAVA_HOME
try {
    $env:JAVA_HOME = $installation.jdk
    & $headless @arguments
    if ($LASTEXITCODE -ne 0) { throw "Ghidra exited with code $LASTEXITCODE" }
} finally {
    $env:JAVA_HOME = $previousJava
}
$log = Get-Content -Raw -LiteralPath (Join-Path $exportDirectory 'ghidra.log')
if ($log -match 'REPORT SCRIPT ERROR' -or $log -notmatch 'Exported [0-9]+ decoded receiver candidates' -or
    $log -notmatch 'Passed 221 receiver selection-prefix checks' -or -not (Test-Path -LiteralPath $reportPath)) {
    throw 'Receiver scripts did not complete. Inspect the log; headless exit code alone is insufficient.'
}
$report = Get-Content -Raw -LiteralPath $reportPath | ConvertFrom-Json
if ($report.image_sha256 -ne $hash -or $report.hardware_access -ne $false -or $report.patched_image -ne $false -or
    $report.passed -ne 221 -or $report.checks.Count -ne 221 -or @($report.checks | Where-Object { $_.passed -ne $true }).Count -ne 0) {
    throw 'Receiver test report did not validate the full stock-code suite.'
}
Write-Output "Project: $projectFile"
Write-Output "Export and tests: $exportDirectory"
