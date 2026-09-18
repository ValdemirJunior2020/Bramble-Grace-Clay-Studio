$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$LogDir=Join-Path $Root 'logs'
New-Item -ItemType Directory -Force $LogDir|Out-Null
$DataDirs=@('data\projects','data\characters','data\voices','data\models','data\cache','data\temp','logs','runtime')
foreach($d in $DataDirs){New-Item -ItemType Directory -Force (Join-Path $Root $d)|Out-Null}
$env:HF_HOME=Join-Path $Root 'data\models\huggingface'

Write-Host '=== Bramble & Grace Clay Studio Installer ==='

function Need($cmd,$label){
  if(-not(Get-Command $cmd -ErrorAction SilentlyContinue)){
    throw "$label is required but was not found."
  }
}

Need git 'Git'
Need node 'Node.js'
Need npm 'npm'
Need ffmpeg 'FFmpeg'

$tmpOut=[IO.Path]::GetTempFileName()
$tmpErr=[IO.Path]::GetTempFileName()
try {
  $probe=Start-Process -FilePath 'py' -ArgumentList @('-3.11','-c','import sys;print(sys.executable)') -Wait -PassThru -NoNewWindow -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr -ErrorAction SilentlyContinue
  if($probe -and $probe.ExitCode -eq 0){
    $py=(Get-Content $tmpOut -Raw).Trim()
  }
} finally {
  Remove-Item $tmpOut,$tmpErr -Force -ErrorAction SilentlyContinue
}
if(-not $py){
  $python=Get-Command python -ErrorAction SilentlyContinue
  if($python){$py=$python.Source}
}
if(-not $py){throw 'Python 3.11 is required for the Clay Studio backend.'}

$venv=Join-Path $Root '.venv'
if(-not(Test-Path (Join-Path $venv 'Scripts\python.exe'))){& $py -m venv $venv}
$vpy=Join-Path $venv 'Scripts\python.exe'
& $vpy -m pip install --upgrade pip
if($LASTEXITCODE -ne 0){throw 'Backend pip upgrade failed.'}
& $vpy -m pip install -r (Join-Path $Root 'backend\requirements.txt')
if($LASTEXITCODE -ne 0){throw 'Backend dependency installation failed.'}

Push-Location (Join-Path $Root 'frontend')
try {
  if(-not(Test-Path 'node_modules')){npm install}else{npm install --prefer-offline}
  if($LASTEXITCODE -ne 0){throw 'Frontend npm install failed.'}
  npm run build
  if($LASTEXITCODE -ne 0){throw 'Frontend production build failed.'}
} finally {
  Pop-Location
}

& $vpy -c "import sys;sys.path.insert(0,r'$Root\backend');from app.storage import init_db,ensure_default_characters;init_db();ensure_default_characters();print('Application data ready')"
if($LASTEXITCODE -ne 0){throw 'Could not initialize local application data.'}

& $vpy (Join-Path $Root 'demo\create_demo.py')
if($LASTEXITCODE -ne 0){throw 'Could not create/verify the demo project.'}

$rhubarbExe=Join-Path $Root 'data\models\rhubarb\rhubarb.exe'
if(-not(Test-Path $rhubarbExe)){
  $a=Read-Host 'Install small Rhubarb Lip Sync tool now? [Y/n]'
  if($a -notmatch '^[Nn]'){& (Join-Path $Root 'scripts\install_optional.ps1') -Component rhubarb}
}

$chatterVenv=Join-Path $Root 'runtime\chatterbox-venv\Scripts\python.exe'
$chatterReady=Join-Path $Root 'runtime\chatterbox-model-ready.txt'
if((Test-Path $chatterVenv) -and -not(Test-Path $chatterReady)){
  Write-Host 'Existing Chatterbox runtime found, but its model preload did not finish. Repairing it now...' -ForegroundColor Yellow
  & (Join-Path $Root 'scripts\install_optional.ps1') -Component chatterbox
} elseif(-not(Test-Path $chatterVenv)){
  $a=Read-Host 'Install Chatterbox Multilingual TTS and cache its model for offline use? This is a larger download. [y/N]'
  if($a -match '^[Yy]'){& (Join-Path $Root 'scripts\install_optional.ps1') -Component chatterbox}
}

$comfyMain=Join-Path $Root 'data\models\comfyui\main.py'
if(-not(Test-Path $comfyMain)){
  $a=Read-Host 'Install optional ComfyUI engine now? Large video models are NOT downloaded automatically. [y/N]'
  if($a -match '^[Yy]'){& (Join-Path $Root 'scripts\install_optional.ps1') -Component comfyui}
}

Write-Host ''
Write-Host 'Installation complete. Running check...'
& (Join-Path $Root 'scripts\check.ps1')
