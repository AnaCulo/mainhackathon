# Run from the checkout or extracted working-agent archive.
param([switch]$Hold, [switch]$Trace, [switch]$Offline, [switch]$Isolated, [string]$PythonBackend,
      [string]$PythonExecutable=$(if ($env:PYTHON) {$env:PYTHON} else {'python'}))
# Windows Python decodes text with the ANSI code page unless UTF-8 mode is on. Every Python
# process the launcher starts (backend, trace, harnesses) inherits this.
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
if (-not (Get-Command $PythonExecutable -ErrorAction SilentlyContinue)) {
  Write-Error "Python not found as '$PythonExecutable'. Install Python 3.13 or set `$env:PYTHON to its full path."
  exit 1
}
$demoArgs = @((Join-Path $PSScriptRoot 'demo.py'))
if ($Hold) { $demoArgs += '--hold' }
if ($Trace) { $demoArgs += '--trace' }
if ($Offline) { $demoArgs += '--offline' }
if ($Isolated) { $demoArgs += '--isolated' }
if ($PythonBackend) { $demoArgs += @('--offline-python-backend', $PythonBackend) }
& $PythonExecutable @demoArgs
exit $LASTEXITCODE
