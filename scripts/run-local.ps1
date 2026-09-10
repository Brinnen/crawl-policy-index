# Fetch a small real panel, then print the allow/block table.
# This PC blocks unsigned .exe files, so this uses Python only.

$ErrorActionPreference = "Stop"
$Root = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { Get-Location }
$Py = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$env:PYTHONPATH = "$Root\parser"

if (-not (Test-Path $Py)) {
    Write-Host "Python was not found at $Py"
    exit 1
}

Set-Location $Root
Write-Host "Step 1/2: fetching robots.txt for the sites in data\panel-mini.csv"
& $Py "$Root\scripts\smoke_fetch.py" --panel "$Root\data\panel-mini.csv" --out "$Root\data\smoke"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Fetch failed. Copy the red text and send it."
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Step 2/2: parsing into a table"
& $Py "$Root\scripts\policy_table.py" --input "$Root\data\smoke" --out "$Root\data\policy-table.csv"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Parse failed. Copy the red text and send it."
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "A * after allow/block means the site named that bot on purpose."
Write-Host "Open the full spreadsheet at:"
Write-Host "  $Root\data\policy-table.csv"
exit 0
