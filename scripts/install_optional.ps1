param([Parameter(Mandatory=$true)][ValidateSet('rhubarb','chatterbox','comfyui')][string]$Component)

$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Models=Join-Path $Root 'data\models'
New-Item -ItemType Directory -Force -Path $Models | Out-Null
$env:HF_HOME=Join-Path $Models 'huggingface'

function Py311 {
  $tmpOut=[IO.Path]::GetTempFileName()
  $tmpErr=[IO.Path]::GetTempFileName()
  try {
    $p=Start-Process -FilePath 'py' -ArgumentList @('-3.11','-c','import sys;print(sys.executable)') -Wait -PassThru -NoNewWindow -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr -ErrorAction SilentlyContinue
    if($p -and $p.ExitCode -eq 0){ return (Get-Content $tmpOut -Raw).Trim() }
  } finally {
    Remove-Item $tmpOut,$tmpErr -Force -ErrorAction SilentlyContinue
  }
  $python=Get-Command python -ErrorAction SilentlyContinue
  if($python){ return $python.Source }
  throw 'Python 3.11 is required.'
}

function Find-Python313 {
  $tmpOut=[IO.Path]::GetTempFileName()
  $tmpErr=[IO.Path]::GetTempFileName()
  try {
    $p=Start-Process -FilePath 'py' -ArgumentList @('-3.13','-c','import sys;print(sys.executable)') -Wait -PassThru -NoNewWindow -RedirectStandardOutput $tmpOut -RedirectStandardError $tmpErr -ErrorAction SilentlyContinue
    if($p -and $p.ExitCode -eq 0){
      $value=(Get-Content $tmpOut -Raw).Trim()
      if($value -and (Test-Path $value)){ return $value }
    }
  } catch {} finally {
    Remove-Item $tmpOut,$tmpErr -Force -ErrorAction SilentlyContinue
  }
  return $null
}

function Ensure-Python313 {
  $found=Find-Python313
  if($found){ return $found }

  Write-Host 'Python 3.13 is required for the official AMD Windows ROCm ComfyUI runtime.'
  Write-Host 'Python 3.13 is not installed. Installing it automatically now...' -ForegroundColor Cyan

  $installed=$false
  try {
    $p=Start-Process -FilePath 'py' -ArgumentList @('install','3.13') -Wait -PassThru -NoNewWindow -ErrorAction SilentlyContinue
    if($p -and $p.ExitCode -eq 0){ $installed=$true }
  } catch {}

  $found=Find-Python313
  if($found){ return $found }

  if(Get-Command winget -ErrorAction SilentlyContinue){
    Write-Host 'Python launcher install did not finish. Trying Windows Package Manager...' -ForegroundColor Yellow
    $args=@('install','-e','--id','Python.Python.3.13','--scope','user','--silent','--accept-package-agreements','--accept-source-agreements')
    $p=Start-Process -FilePath 'winget' -ArgumentList $args -Wait -PassThru -NoNewWindow
    if($p.ExitCode -ne 0){
      Write-Host "winget returned exit code $($p.ExitCode)." -ForegroundColor Yellow
    }
  }

  $found=Find-Python313
  if($found){ return $found }

  throw 'Python 3.13 could not be installed automatically. Run "py install 3.13" once, then rerun INSTALL.bat.'
}

if($Component -eq 'rhubarb'){
  $dest=Join-Path $Models 'rhubarb'
  if(Test-Path (Join-Path $dest 'rhubarb.exe')){Write-Host 'Rhubarb already installed.';exit 0}
  $zip=Join-Path $env:TEMP 'rhubarb-1.14.0.zip'
  $url='https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.14.0/Rhubarb-Lip-Sync-1.14.0-Windows.zip'
  Write-Host 'Downloading Rhubarb Lip Sync 1.14.0...'
  Invoke-WebRequest -UseBasicParsing $url -OutFile $zip
  $tmp=Join-Path $env:TEMP ('rhubarb-'+[guid]::NewGuid())
  Expand-Archive $zip $tmp -Force
  New-Item -ItemType Directory -Force -Path $dest|Out-Null
  $exe=Get-ChildItem $tmp -Recurse -Filter rhubarb.exe|Select-Object -First 1
  if(-not $exe){throw 'rhubarb.exe was not found in the downloaded archive.'}
  Copy-Item (Join-Path $exe.Directory.FullName '*') $dest -Recurse -Force
  Remove-Item $tmp -Recurse -Force
  Remove-Item $zip -Force
  Write-Host 'Rhubarb installed.'
  exit 0
}

if($Component -eq 'chatterbox'){
  $py=Py311
  $venv=Join-Path $Root 'runtime\chatterbox-venv'
  if(-not(Test-Path (Join-Path $venv 'Scripts\python.exe'))){ & $py -m venv $venv }
  $vpy=Join-Path $venv 'Scripts\python.exe'
  & $vpy -m pip install --upgrade pip
  if($LASTEXITCODE -ne 0){throw 'Could not upgrade pip in the Chatterbox environment.'}
  & $vpy -m pip install chatterbox-tts fastapi uvicorn
  if($LASTEXITCODE -ne 0){throw 'Could not install Chatterbox dependencies.'}

  $marker=Join-Path $Root 'runtime\chatterbox-model-ready.txt'
  Remove-Item $marker -Force -ErrorAction SilentlyContinue
  $env:BRAMBLE_CHATTERBOX_READY=$marker
  Push-Location $Root
  try {
    & $vpy (Join-Path $Root 'scripts\download_chatterbox.py')
    if($LASTEXITCODE -ne 0){throw 'Chatterbox model preload failed.'}
  } finally {
    Pop-Location
  }
  if(-not(Test-Path $marker)){throw 'Chatterbox preload finished without creating the ready marker.'}
  Write-Host 'Chatterbox runtime installed and multilingual model cached.' -ForegroundColor Green
  exit 0
}

if($Component -eq 'comfyui'){
  $dest=Join-Path $Models 'comfyui'
  if(Test-Path (Join-Path $dest 'main.py')){Write-Host 'ComfyUI already installed.';exit 0}

  if(Test-Path $dest){
    if(Test-Path (Join-Path $dest '.git')){
      Write-Host 'Incomplete ComfyUI checkout found. Reusing it instead of downloading from zero.' -ForegroundColor Yellow
      git -C $dest reset --hard HEAD
      git -C $dest pull --ff-only
    } else {
      Write-Host 'Removing incomplete ComfyUI folder from the previous failed install...' -ForegroundColor Yellow
      Remove-Item $dest -Recurse -Force
    }
  }

  $py313=Ensure-Python313
  Write-Host "Using Python 3.13: $py313"

  if(-not(Test-Path (Join-Path $dest 'main.py'))){
    git clone https://github.com/Comfy-Org/ComfyUI.git $dest
    if($LASTEXITCODE -ne 0){throw 'Could not clone ComfyUI.'}
  }

  $venv=Join-Path $dest '.venv'
  & $py313 -m venv $venv
  if($LASTEXITCODE -ne 0){throw 'Could not create the ComfyUI Python 3.13 environment.'}
  $vpy=Join-Path $venv 'Scripts\python.exe'
  & $vpy -m pip install --upgrade pip
  if($LASTEXITCODE -ne 0){throw 'Could not upgrade pip in the ComfyUI environment.'}

  $gpu=(Get-CimInstance Win32_VideoController|Where-Object{$_.Name -match 'Radeon RX 9060'}|Select-Object -First 1)
  if($gpu){
    Write-Host 'RX 9060-series detected: installing official AMD ROCm 10 / gfx1200 PyTorch packages.' -ForegroundColor Cyan
    & $vpy -m pip install --index-url https://stable.repo.amd.com/rocm/whl-next/ 'torch[device-gfx1200]==2.13.0+rocm10.0.0' 'torchvision[device-gfx1200]==0.28.0+rocm10.0.0' 'torchaudio==2.11.0.2+rocm10.0.0'
    if($LASTEXITCODE -ne 0){throw 'AMD ROCm PyTorch installation failed.'}
  } else {
    Write-Host 'RX 9060 was not detected. Installing ComfyUI requirements without forcing the gfx1200 ROCm package.' -ForegroundColor Yellow
  }

  & $vpy -m pip install -r (Join-Path $dest 'requirements.txt')
  if($LASTEXITCODE -ne 0){throw 'ComfyUI requirements installation failed.'}

  $gguf=Join-Path $dest 'custom_nodes\ComfyUI-GGUF'
  if(-not(Test-Path $gguf)){
    git clone https://github.com/city96/ComfyUI-GGUF.git $gguf
    if($LASTEXITCODE -ne 0){throw 'Could not clone ComfyUI-GGUF.'}
    if(Test-Path (Join-Path $gguf 'requirements.txt')){
      & $vpy -m pip install -r (Join-Path $gguf 'requirements.txt')
      if($LASTEXITCODE -ne 0){throw 'ComfyUI-GGUF requirements installation failed.'}
    }
  }

  Write-Host 'ComfyUI and the GGUF loader are installed. No large video model was downloaded.' -ForegroundColor Green
  exit 0
}
