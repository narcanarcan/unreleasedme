$ErrorActionPreference = "Stop"

$python = Get-Command python -ErrorAction SilentlyContinue
if ($python) {
  $pythonPath = $python.Source
} else {
  $pythonPath = "C:\Users\narcan\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
}

if (-not (Test-Path $pythonPath)) {
  throw "Python 3.12 or newer is required."
}

& $pythonPath "$PSScriptRoot\server.py"
