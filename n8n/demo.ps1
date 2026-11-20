# Run from the checkout or extracted working-agent archive.
param([switch]$Hold, [switch]$Trace, [switch]$Offline, [switch]$Isolated, [string]$PythonBackend,
      [string]$PythonExecutable=$(if ($env:PYTHON) {$env:PYTHON} else {'python'}))
$demoArgs = @((Join-Path $PSScriptRoot 'demo.py'))
if ($Hold) { $demoArgs += '--hold' }
if ($Trace) { $demoArgs += '--trace' }
if ($Offline) { $demoArgs += '--offline' }
if ($Isolated) { $demoArgs += '--isolated' }
if ($PythonBackend) { $demoArgs += @('--offline-python-backend', $PythonBackend) }
& $PythonExecutable @demoArgs
exit $LASTEXITCODE
