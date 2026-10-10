param(
    [string]$ToolsDirectory = (Join-Path $env:USERPROFILE '.cache\hdzero-monitor-tools'),
    [string]$StockProject = 'Monitor-DM5680-1R3',
    [string]$CandidateProject = 'Monitor-Favorites-Offline-v4'
)

$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$installation = Get-Content -Raw -LiteralPath (Join-Path $ToolsDirectory 'tools.json') | ConvertFrom-Json
$headless = Join-Path $installation.ghidra 'support\analyzeHeadless.bat'
$projectDirectory = Join-Path $workspace 'artifacts\ghidra'
$exportDirectory = Join-Path $workspace ('artifacts\firmware-analysis\startup-run-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
foreach ($project in @($StockProject, $CandidateProject)) {
    if ($project -notmatch '^[A-Za-z0-9_-]+$' -or
        -not (Test-Path -LiteralPath (Join-Path $projectDirectory ($project + '.gpr')))) {
        throw 'Startup comparison requires the existing validated receiver projects.'
    }
}
New-Item -ItemType Directory -Path $exportDirectory | Out-Null
$previousJava = $env:JAVA_HOME
$reports = @()
try {
    $env:JAVA_HOME = $installation.jdk
    foreach ($item in @(
        @{Name='stock'; Project=$StockProject; Image='receiver-8051.bin'; Size=62003},
        @{Name='favorites'; Project=$CandidateProject; Image='receiver-candidate-ANALYSIS-ONLY.bin'; Size=62398}
    )) {
        $reportPath = Join-Path $exportDirectory ($item.Name + '-startup.json')
        $logPath = Join-Path $exportDirectory ($item.Name + '-ghidra.log')
        & $headless $projectDirectory $item.Project -process $item.Image -noanalysis `
            -scriptPath (Join-Path $PSScriptRoot 'ghidra') `
            -postScript ReceiverStartupTests.java $reportPath $item.Size -log $logPath
        if ($LASTEXITCODE -ne 0) { throw 'Ghidra startup run failed.' }
        $log = Get-Content -Raw -LiteralPath $logPath
        if ($log -match 'REPORT SCRIPT ERROR' -or $log -notmatch 'Passed 2 bounded receiver startup checks' -or
            -not (Test-Path -LiteralPath $reportPath)) { throw 'Startup script did not complete.' }
        $report = Get-Content -Raw -LiteralPath $reportPath | ConvertFrom-Json
        if ($report.passed -ne 2 -or $report.checks.Count -ne 2 -or $report.hardware_access -ne $false -or
            $report.feature_acceptance -ne $false -or @($report.checks | Where-Object { $_.passed -ne $true }).Count -ne 0) {
            throw 'Startup report failed validation.'
        }
        $reports += $report
    }
} finally {
    $env:JAVA_HOME = $previousJava
}
for ($index = 0; $index -lt 2; $index++) {
    $stock = $reports[0].checks[$index]
    $favorites = $reports[1].checks[$index]
    foreach ($field in @('initial_ram_fill', 'instructions', 'paged_movx_adapter_instructions', 'external_write_bytes',
                        'maximum_sp', 'final_sp', 'stop_pc', 'external_ram_sha256', 'internal_ram_sha256')) {
        if ($stock.$field -ne $favorites.$field) { throw "Startup differs between stock and Favorites: $field" }
    }
}
@{
    hardware_access=$false; feature_acceptance=$false; passed=4; startup_state_equal=$true
    stock_sha256=$reports[0].image_sha256; favorites_sha256=$reports[1].image_sha256
    reports=@('stock-startup.json', 'favorites-startup.json')
    boundary='C-runtime initialization only, with explicit P2:R0 and memory aliases; hardware init and ROM loading are untested.'
} | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $exportDirectory 'comparison.json') -Encoding utf8
Write-Output "Verified bounded startup comparison: $exportDirectory"
