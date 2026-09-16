param([switch]$WithoutAI, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    Write-Host 'Run setup.ps1 once to install the project dependencies.'
    exit 1
}
$launchArguments = @('-m', 'tools.launch')
if ($WithoutAI) { $launchArguments += '--without-ai' }
if ($NoBrowser) { $launchArguments += '--no-browser' }
& $projectPython @launchArguments
exit $LASTEXITCODE
