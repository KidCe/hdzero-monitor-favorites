param(
    [Parameter(Mandatory = $true)][string]$Application,
    [string]$ToolsDirectory = (Join-Path $env:USERPROFILE '.cache\hdzero-monitor-tools'),
    [string]$ProjectName = 'Monitor-1R3',
    [switch]$Refresh
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$fixture = (Resolve-Path -LiteralPath $Application).Path
$hash = (Get-FileHash -LiteralPath $fixture -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne 'cf55cfc99d8db202c9f6f93348b4241d048c2dfd1ce5b6d2c82dc6ead4607c34') {
    throw 'Ghidra import requires the unchanged, pinned application fixture.'
}
if ($ProjectName -notmatch '^[A-Za-z0-9_-]+$') { throw 'Unexpected project name.' }
$installation = Get-Content -Raw -LiteralPath (Join-Path $ToolsDirectory 'tools.json') | ConvertFrom-Json
$headless = Join-Path $installation.ghidra 'support\analyzeHeadless.bat'
$projectDirectory = Join-Path $workspace 'artifacts\ghidra'
$exportDirectory = Join-Path $workspace ('artifacts\firmware-analysis\ghidra-export-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
New-Item -ItemType Directory -Force -Path $projectDirectory | Out-Null
$arguments = @($projectDirectory, $ProjectName)
$projectFile = Join-Path $projectDirectory ($ProjectName + '.gpr')
if (Test-Path -LiteralPath $projectFile) {
    if (-not $Refresh) { throw 'Project exists. Use -Refresh to export from it without repeating analysis.' }
    $arguments += @('-process', [IO.Path]::GetFileName($fixture), '-noanalysis')
} else {
    if ($Refresh) { throw 'Refresh requires an existing project.' }
    $arguments += @('-import', $fixture, '-loader', 'BinaryLoader', '-loader-baseAddr', '0x20008000',
                    '-processor', 'ARM:LE:32:v7', '-cspec', 'default', '-analysisTimeoutPerFile', '300')
}
$arguments += @('-scriptPath', (Join-Path $PSScriptRoot 'ghidra'), '-preScript', 'MonitorSeeds.java',
                '-postScript', 'MonitorExport.java', $exportDirectory,
                '0x2023edc0', '0x2007f954', '0x2007fc2c', '0x2007f8d0',
                '@0x20434ded', '@0x20351bd4', '@0x20431dd4',
                '-max-cpu', '4', '-log', ($exportDirectory + '.log'))
& $headless @arguments
if ($LASTEXITCODE -ne 0) { throw "Ghidra exited with code $LASTEXITCODE" }
# Headless can exit zero after a script error. Confirm both scripts completed and a new export exists.
$log = Get-Content -Raw -LiteralPath ($exportDirectory + '.log')
if ($log -notmatch 'Seeded vectors/settings/string candidates' -or
    $log -notmatch 'Exported [0-9]+ candidate functions' -or
    -not (Test-Path -LiteralPath (Join-Path $exportDirectory 'report.json'))) {
    throw 'Ghidra did not complete the requested seed/export scripts. Inspect the log.'
}
Write-Output "Project: $projectFile"
Write-Output "Export: $exportDirectory"
