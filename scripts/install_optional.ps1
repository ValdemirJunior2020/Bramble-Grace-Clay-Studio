param([Parameter(Mandatory=$true)][ValidateSet('rhubarb','chatterbox','comfyui')][string]$Component)
$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Models=Join-Path $Root 'data\models'; New-Item -ItemType Directory -Force -Path $Models | Out-Null
$env:HF_HOME=Join-Path $Models 'huggingface'
function Py311 { $x=& py -3.11 -c "import sys;print(sys.executable)" 2>$null; if($LASTEXITCODE -eq 0){return $x.Trim()} ; $x=& python -c "import sys;print(sys.executable)" 2>$null; if($LASTEXITCODE -eq 0){return $x.Trim()}; throw 'Python 3.11 is required.' }
if($Component -eq 'rhubarb'){
  $dest=Join-Path $Models 'rhubarb'; if(Test-Path (Join-Path $dest 'rhubarb.exe')){Write-Host 'Rhubarb already installed.';exit 0}
  $zip=Join-Path $env:TEMP 'rhubarb-1.14.0.zip';$url='https://github.com/DanielSWolf/rhubarb-lip-sync/releases/download/v1.14.0/Rhubarb-Lip-Sync-1.14.0-Windows.zip'
  Write-Host 'Downloading Rhubarb Lip Sync 1.14.0...';Invoke-WebRequest -UseBasicParsing $url -OutFile $zip
  $tmp=Join-Path $env:TEMP ('rhubarb-'+[guid]::NewGuid());Expand-Archive $zip $tmp -Force;New-Item -ItemType Directory -Force -Path $dest|Out-Null
  $exe=Get-ChildItem $tmp -Recurse -Filter rhubarb.exe|Select-Object -First 1;if(-not $exe){throw 'rhubarb.exe was not found in the downloaded archive.'}
  Copy-Item (Join-Path $exe.Directory.FullName '*') $dest -Recurse -Force;Remove-Item $tmp -Recurse -Force;Remove-Item $zip -Force;Write-Host 'Rhubarb installed.';exit 0
}
if($Component -eq 'chatterbox'){
  $py=Py311;$venv=Join-Path $Root 'runtime\chatterbox-venv';if(-not(Test-Path (Join-Path $venv 'Scripts\python.exe'))){& $py -m venv $venv}
  $vpy=Join-Path $venv 'Scripts\python.exe';& $vpy -m pip install --upgrade pip;& $vpy -m pip install chatterbox-tts fastapi uvicorn
  & $vpy (Join-Path $Root 'scripts\download_chatterbox.py');Write-Host 'Chatterbox runtime installed and model cached.';exit 0
}
if($Component -eq 'comfyui'){
  $dest=Join-Path $Models 'comfyui';if(Test-Path (Join-Path $dest 'main.py')){Write-Host 'ComfyUI already installed.';exit 0}
  $py313=& py -3.13 -c "import sys;print(sys.executable)" 2>$null
  if($LASTEXITCODE -ne 0){throw 'ComfyUI AMD Windows ROCm currently requires 64-bit Python 3.13. Install Python 3.13, then run this installer again.'}
  git clone https://github.com/Comfy-Org/ComfyUI.git $dest
  $venv=Join-Path $dest '.venv';& $py313.Trim() -m venv $venv;$vpy=Join-Path $venv 'Scripts\python.exe'
  & $vpy -m pip install --upgrade pip
  $gpu=(Get-CimInstance Win32_VideoController|Where-Object{$_.Name -match 'Radeon RX 9060'}|Select-Object -First 1)
  if($gpu){
    Write-Host 'RX 9060-series detected: installing AMD ROCm 10 / gfx1200 packages.'
    & $vpy -m pip install --index-url https://stable.repo.amd.com/rocm/whl-next/ 'torch[device-gfx1200]==2.13.0+rocm10.0.0' 'torchvision[device-gfx1200]==0.28.0+rocm10.0.0' 'torchaudio==2.11.0.2+rocm10.0.0'
  } else {
    Write-Host 'GPU-specific ROCm package was not selected automatically. Installing ComfyUI requirements only; CHECK.bat will report acceleration status.'
  }
  & $vpy -m pip install -r (Join-Path $dest 'requirements.txt')
  $gguf=Join-Path $dest 'custom_nodes\ComfyUI-GGUF';if(-not(Test-Path $gguf)){git clone https://github.com/city96/ComfyUI-GGUF.git $gguf;if(Test-Path (Join-Path $gguf 'requirements.txt')){& $vpy -m pip install -r (Join-Path $gguf 'requirements.txt')}}
  Write-Host 'ComfyUI and the GGUF loader are installed. No large video model was downloaded.';exit 0
}
