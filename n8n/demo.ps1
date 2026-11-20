# Run from the repository root with Node 24 and npm on PATH.
param([switch]$Hold, [string]$PythonBackend, [string]$PythonExecutable='python')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
Set-Location -LiteralPath $root
$node = (Get-Command node).Source
if ((& $node -p 'process.versions.node.split(".")[0]') -ne '24') {throw 'Use Node 24 for this demo.'}
foreach ($port in 5689,8788) {
  $probe = [Net.Sockets.TcpClient]::new()
  try { $probe.Connect('127.0.0.1',$port) } catch {} finally { $occupied=$probe.Connected; $probe.Dispose() }
  if ($occupied) {throw "Demo port $port is in use. Use an empty demo instance."}
}
$package=Join-Path $env:TEMP 'culo-n8n-2-48-7'
$cli=Join-Path $package 'node_modules/n8n/bin/n8n'
if (!(Test-Path -LiteralPath $cli)) {
  & npm.cmd install --prefix $package n8n@2.48.7 --no-audit --no-fund
  if ($LASTEXITCODE) {throw 'n8n installation failed.'}
}
$env:N8N_USER_FOLDER=Join-Path $env:TEMP ('culo-runtime-'+[guid]::NewGuid().ToString('N'))
$env:N8N_LISTEN_ADDRESS='127.0.0.1'
$env:N8N_HOST='127.0.0.1'
$env:N8N_PORT='5689'
$env:N8N_PROTOCOL='http'
$env:N8N_SECURE_COOKIE='false'
$env:N8N_DIAGNOSTICS_ENABLED='false'
$env:N8N_VERSION_NOTIFICATIONS_ENABLED='false'
$env:N8N_TEMPLATES_ENABLED='false'
$env:N8N_LOG_LEVEL='error'
$env:EXECUTIONS_DATA_SAVE_ON_SUCCESS='none'
$env:EXECUTIONS_DATA_SAVE_ON_ERROR='none'
$env:EXECUTIONS_DATA_SAVE_MANUAL_EXECUTIONS='false'
$env:EXECUTIONS_DATA_SAVE_ON_PROGRESS='false'
$n8nProcess=Start-Process -FilePath $node -ArgumentList @("`"$cli`"",'start') -WindowStyle Hidden -PassThru
try {
  $ready=$false
  for ($i=0;$i -lt 90;$i++) {
    if($n8nProcess.HasExited){throw 'n8n exited before readiness.'}
    try { $ready=(Invoke-WebRequest 'http://127.0.0.1:5689/healthz/readiness' -UseBasicParsing).StatusCode -eq 200 } catch {}
    if ($ready) {break}
    Start-Sleep -Seconds 1
  }
  if(!$ready){throw 'n8n did not become ready.'}
  $config=(& $node n8n/setup-demo.mjs | Select-Object -Last 1)
  if ($LASTEXITCODE -or !(Test-Path -LiteralPath $config)) {throw 'Demo setup failed.'}
  $register=Start-Process -FilePath $node -ArgumentList @("--env-file=`"$config`"",'n8n/service.mjs') -WindowStyle Hidden -PassThru
  Start-Sleep -Seconds 1
  if($register.HasExited){throw 'Register failed to start.'}
  $walkArgs=@("--env-file=$config",'n8n/walkthrough.mjs')
  if($Hold){$walkArgs+='--hold'}
  & $node @walkArgs
  if ($LASTEXITCODE) {throw 'Synthetic walkthrough failed.'}
  if($PythonBackend){
    & $PythonExecutable n8n/verify-python.py $PythonBackend $config
    if($LASTEXITCODE){throw 'Python sender compatibility check failed.'}
  }
  if($Hold){
    Write-Host "Review at http://127.0.0.1:8788/review as handler. Private demo credentials are in $config. Keep them off camera."
    Read-Host 'Press Enter after the rehearsal to stop this instance' | Out-Null
  }
} finally {
  if($register -and !$register.HasExited){$register.Kill();$register.WaitForExit()}
  if(!$n8nProcess.HasExited){$n8nProcess.Kill();$n8nProcess.WaitForExit()}
}
