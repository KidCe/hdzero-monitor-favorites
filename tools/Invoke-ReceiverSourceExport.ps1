param(
    [Parameter(Mandatory = $true)][string]$OutputDirectory,
    [string]$ProjectName = 'Monitor-DM5680-1R3',
    [string]$ToolsDirectory = (Join-Path $env:USERPROFILE '.cache\hdzero-monitor-tools')
)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
if ($ProjectName -notmatch '^[A-Za-z0-9_-]+$') { throw 'Unexpected project name.' }
$projectDirectory = Join-Path $workspace 'artifacts\ghidra'
if (-not (Test-Path -LiteralPath (Join-Path $projectDirectory ($ProjectName + '.gpr')))) {
    throw 'Import the pinned stock receiver with Invoke-ReceiverGhidra.ps1 first.'
}
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Source export directory must be new.' }
New-Item -ItemType Directory -Path $OutputDirectory | Out-Null
$root = (Resolve-Path -LiteralPath $OutputDirectory).Path
$reportPath = Join-Path $root 'instructions.json'
$installation = Get-Content -Raw -LiteralPath (Join-Path $ToolsDirectory 'tools.json') | ConvertFrom-Json
$previousJava = $env:JAVA_HOME
try {
    $env:JAVA_HOME = $installation.jdk
    & (Join-Path $installation.ghidra 'support\analyzeHeadless.bat') $projectDirectory $ProjectName `
        -process receiver-8051.bin -noanalysis -scriptPath (Join-Path $PSScriptRoot 'ghidra') `
        -postScript ReceiverSourceExport.java $reportPath -log (Join-Path $root 'ghidra.log')
    if ($LASTEXITCODE -ne 0) { throw 'Ghidra source export failed.' }
} finally { $env:JAVA_HOME = $previousJava }
$log = Get-Content -Raw -LiteralPath (Join-Path $root 'ghidra.log')
if ($log -match 'REPORT SCRIPT ERROR' -or $log -notmatch 'Exported 28350 source instructions covering 48283 bytes') {
    throw 'Pinned source export did not complete.'
}
$report = Get-Content -Raw -LiteralPath $reportPath | ConvertFrom-Json
if ($report.image_sha256 -ne 'ca65d71948658569f02715e312d62cf10742cac10ffca4271ee933210c5a5652' -or
    $report.instruction_count -ne 28350 -or $report.instruction_bytes -ne 48283) {
    throw 'Unexpected source export coverage or input hash.'
}
Write-Output "Recovered instruction inventory: $reportPath"
