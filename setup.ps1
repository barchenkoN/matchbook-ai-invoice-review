param([switch]$WithAI)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundledPython) { & $bundledPython -m venv .venv }
    elseif (Get-Command py -ErrorAction SilentlyContinue) { py -3.12 -m venv .venv }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { python -m venv .venv }
    else { throw 'Install Python 3.12 or newer, then run setup.ps1 again.' }
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
}
& $projectPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
if ($WithAI) {
    & $projectPython -m pip install torch --index-url https://download.pytorch.org/whl/cpu
    if ($LASTEXITCODE -ne 0) { throw 'PyTorch installation failed.' }
    & $projectPython -m pip install -r requirements-ai.txt
    if ($LASTEXITCODE -ne 0) { throw 'Model dependency installation failed.' }
    & $projectPython -m tools.setup_local_ai
    if ($LASTEXITCODE -ne 0) { throw 'Model download failed. Rerun setup.ps1 -WithAI to resume.' }
}
& $projectPython -m tools.fixtures
Write-Host 'Ready. Open Start-Matchbook.cmd or run ./start.ps1.'
