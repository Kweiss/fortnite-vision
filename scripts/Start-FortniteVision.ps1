$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    $venvPath = Join-Path $projectRoot ".venv"
    $pythonCreated = $false

    if (Get-Command py -ErrorAction SilentlyContinue) {
        py -3.11 --version *> $null
        if ($LASTEXITCODE -eq 0) {
            py -3.11 -m venv $venvPath
            $pythonCreated = $true
        }
    }

    if (-not $pythonCreated -and (Get-Command python -ErrorAction SilentlyContinue)) {
        python --version *> $null
        if ($LASTEXITCODE -eq 0) {
            python -m venv $venvPath
            $pythonCreated = $true
        }
    }

    if (-not $pythonCreated) {
        throw "Python 3.10+ was not found. Install 64-bit Python 3.11 from python.org, then rerun this script."
    }
}

& $venvPython -m pip install --upgrade pip
& $venvPython -m pip install -e $projectRoot
& $venvPython -m droid_monitor
