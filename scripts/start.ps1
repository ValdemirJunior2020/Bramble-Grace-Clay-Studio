$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Logs=Join-Path $Root 'logs';New-Item -ItemType Directory -Force $Logs|Out-Null
$Runtime=Join-Path $Root 'runtime';New-Item -ItemType Directory -Force $Runtime|Out-Null
$PidFile=Join-Path $Runtime 'owned-pids.txt'
function Record-Owned($proc,[string]$label){try{$ticks=$proc.StartTime.ToFileTimeUtc();Add-Content -Encoding UTF8 $PidFile "$($proc.Id)|$ticks|$label"}catch{}}
$env:HF_HOME=Join-Path $Root 'data\models\huggingface'
$env:PATH=(Join-Path $Root 'data\models\rhubarb')+';'+$env:PATH
function IsPortFree([int]$p){try{$l=[Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$p);$l.Start();$l.Stop();return $true}catch{return $false}}
function IsHealthy($url){try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 $url;return $r.StatusCode -eq 200}catch{return $false}}
function FreePort([int]$start){for($p=$start;$p -lt $start+40;$p++){if(IsPortFree $p){return $p}};throw 'No free local port found.'}
$ttsPy=Join-Path $Root 'runtime\chatterbox-venv\Scripts\python.exe';$ttsPort=8766
if((Test-Path $ttsPy) -and -not(IsHealthy "http://127.0.0.1:$ttsPort/health")){
  $proc=Start-Process $ttsPy -ArgumentList @('-m','uvicorn','scripts.chatterbox_service:app','--host','127.0.0.1','--port',"$ttsPort") -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Logs 'chatterbox.log') -RedirectStandardError (Join-Path $Logs 'chatterbox-error.log') -PassThru
  Record-Owned $proc 'chatterbox'
}
$env:CHATTERBOX_SERVICE_URL="http://127.0.0.1:$ttsPort"
$comfy=Join-Path $Root 'data\models\comfyui';$comfyPy=Join-Path $comfy '.venv\Scripts\python.exe';$comfyPort=8188
if(Test-Path (Join-Path $comfy 'main.py')){
  if(-not(IsHealthy "http://127.0.0.1:$comfyPort/system_stats")){
    if(-not(IsPortFree $comfyPort)){$comfyPort=FreePort 8189}
    if(Test-Path $comfyPy){$proc=Start-Process $comfyPy -ArgumentList @('main.py','--listen','127.0.0.1','--port',"$comfyPort") -WorkingDirectory $comfy -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Logs 'comfyui.log') -RedirectStandardError (Join-Path $Logs 'comfyui-error.log') -PassThru;Record-Owned $proc 'comfyui'}
  }
}
$env:COMFYUI_URL="http://127.0.0.1:$comfyPort"
$backendPy=Join-Path $Root '.venv\Scripts\python.exe';if(-not(Test-Path $backendPy)){throw 'Run INSTALL.bat first.'}
$backendPort=8765
if(IsHealthy "http://127.0.0.1:$backendPort/api/health"){$url="http://127.0.0.1:$backendPort"}
else{
 if(-not(IsPortFree $backendPort)){$backendPort=FreePort 8767}
 $env:BRAMBLE_BACKEND_PORT="$backendPort"
 $proc=Start-Process $backendPy -ArgumentList @('backend\run.py') -WorkingDirectory $Root -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Logs 'backend.log') -RedirectStandardError (Join-Path $Logs 'backend-error.log') -PassThru
 Record-Owned $proc 'backend'
 $url="http://127.0.0.1:$backendPort"
 for($i=0;$i -lt 80;$i++){if(IsHealthy "$url/api/health"){break};Start-Sleep -Milliseconds 250}
 if(-not(IsHealthy "$url/api/health")){throw 'Backend did not start. Check logs\backend-error.log'}
}
Set-Content -Encoding UTF8 (Join-Path $Runtime 'last-url.txt') $url
Start-Process $url
Write-Host "Bramble & Grace Clay Studio is running at $url"
