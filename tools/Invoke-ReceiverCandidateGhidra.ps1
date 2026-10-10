param(
    [Parameter(Mandatory = $true)][string]$Stock,
    [Parameter(Mandatory = $true)][string]$CandidateDirectory,
    [string]$Python = 'python',
    [string]$ToolsDirectory = (Join-Path $env:USERPROFILE '.cache\hdzero-monitor-tools'),
    [string]$ProjectName = 'Monitor-Favorites-Offline-v4',
    [switch]$Refresh
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$directory = (Resolve-Path -LiteralPath $CandidateDirectory).Path
$fixture = Join-Path $directory 'receiver-candidate-ANALYSIS-ONLY.bin'
# Hash metadata alone is insufficient: regenerate every candidate byte from the pinned stock input.
& $Python (Join-Path $PSScriptRoot 'monitor_receiver_candidate.py') --stock $Stock --verify-dir $directory
if ($LASTEXITCODE -ne 0) { throw 'Candidate or change manifest failed regeneration verification.' }
$hash = (Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne '7c4970a56cc56618c0d3979942cbe0c76a57d3f4191bf8a06ab57b39c5a6eb16') {
    throw 'The Ghidra candidate suite accepts only the eight requested Favorites in their pinned order.'
}
if ($ProjectName -notmatch '^[A-Za-z0-9_-]+$') { throw 'Unexpected project name.' }
$installation = Get-Content -Raw -LiteralPath (Join-Path $ToolsDirectory 'tools.json') | ConvertFrom-Json
$headless = Join-Path $installation.ghidra 'support\analyzeHeadless.bat'
$projectDirectory = Join-Path $workspace 'artifacts\ghidra'
$exportDirectory = Join-Path $workspace ('artifacts\firmware-analysis\candidate-run-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Force -Path $projectDirectory | Out-Null
New-Item -ItemType Directory -Path $exportDirectory | Out-Null
$arguments = @($projectDirectory, $ProjectName)
$projectFile = Join-Path $projectDirectory ($ProjectName + '.gpr')
if (Test-Path -LiteralPath $projectFile) {
    if (-not $Refresh) { throw 'Candidate project exists. Use -Refresh to test it without reimporting.' }
    $arguments += @('-process', [IO.Path]::GetFileName($fixture), '-noanalysis')
} else {
    if ($Refresh) { throw 'Refresh requires an existing candidate project.' }
    $arguments += @('-import', $fixture, '-loader', 'BinaryLoader', '-loader-baseAddr', '0',
                    '-processor', '8051:BE:16:default', '-cspec', 'default', '-analysisTimeoutPerFile', '180',
                    '-preScript', 'ReceiverSeeds.java')
}
$reportPath = Join-Path $exportDirectory 'candidate-tests.json'
$arguments += @('-scriptPath', (Join-Path $PSScriptRoot 'ghidra'),
                '-postScript', 'ReceiverConnectedTests.java', $reportPath,
                '-postScript', 'ReceiverInventory.java', (Join-Path $exportDirectory 'inventory.json'),
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
if ($log -match 'REPORT SCRIPT ERROR' -or $log -notmatch 'Passed 5735 receiver selection-prefix checks' -or
    $log -notmatch 'Receiver reference inventory exported' -or -not (Test-Path -LiteralPath $reportPath)) {
    throw 'Candidate test/inventory scripts did not complete. Inspect the log.'
}
$report = Get-Content -Raw -LiteralPath $reportPath | ConvertFrom-Json
if ($report.image_sha256 -ne $hash -or $report.hardware_access -ne $false -or $report.patched_image -ne $true -or
    $report.passed -ne 5735 -or $report.checks.Count -ne 5735 -or $report.connected_session_checks -ne 1152 -or
    @($report.checks | Where-Object { $_.passed -ne $true }).Count -ne 0) {
    throw 'Candidate report did not validate the full pinned experiment.'
}
$inventory = Get-Content -Raw -LiteralPath (Join-Path $exportDirectory 'inventory.json') | ConvertFrom-Json
if (@($inventory.references_into_label_rewrite_interiors).Count -ne 0 -or
    @($inventory.literal_references | Where-Object { $_.literal -in @('0xc6c0', '0xc6f0') }).Count -ne 0) {
    throw 'Candidate retains a stock table pointer or an unexpected interior label reference.'
}
Write-Output "Offline candidate project: $projectFile"
Write-Output "Verified candidate results: $exportDirectory"
