param([Parameter(Mandatory=$true)][ValidateSet('rhubarb','chatterbox','comfyui','wan22','motionity')][string]$Component)

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
  # Robust detection for both the modern Python Install Manager and legacy launcher.
  # The user's machine may have Python 3.13 installed even when "py list --format=exe"
  # is unavailable or returns a path format that Test-Path cannot validate.
  $probes=@(
    @{Exe='py'; Args=@('-3.13','-c','import sys; print(sys.executable)')},
    @{Exe='py'; Args=@('-V:3.13','-c','import sys; print(sys.executable)')},
    @{Exe='python3.13'; Args=@('-c','import sys; print(sys.executable)')},
    @{Exe='python3.13.exe'; Args=@('-c','import sys; print(sys.executable)')}
  )

  foreach($probe in $probes){
    $cmd=Get-Command $probe.Exe -ErrorAction SilentlyContinue
    if(-not $cmd){ continue }

    try {
      $output=& $probe.Exe @($probe.Args) 2>$null
      if($LASTEXITCODE -eq 0){
        $value=("$output").Trim()
        if($value -and (Test-Path -LiteralPath $value)){
          # Verify this executable is really Python 3.13 before returning it.
          $version=& $value -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>$null
          if($LASTEXITCODE -eq 0 -and ("$version").Trim() -eq '3.13'){
            return $value
          }
        }
      }
    } catch {
    }
  }

  # Last fallback: ask the launcher for the version first, then query sys.executable.
  try {
    $version=& py -3.13 --version 2>&1
    if($LASTEXITCODE -eq 0 -and ("$version") -match 'Python 3\.13'){
      $value=& py -3.13 -c 'import sys; print(sys.executable)' 2>$null
      $value=("$value").Trim()
      if($value -and (Test-Path -LiteralPath $value)){
        return $value
      }
    }
  } catch {
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

if($Component -eq 'motionity'){
  $tools=Join-Path $Root 'data\tools'
  $dest=Join-Path $tools 'motionity'
  New-Item -ItemType Directory -Force -Path $tools | Out-Null

  if(Test-Path (Join-Path $dest '.git')){
    Write-Host 'Updating Motionity...' -ForegroundColor Cyan
    git -C $dest pull --ff-only
    if($LASTEXITCODE -ne 0){throw 'Could not update Motionity.'}
  } elseif(Test-Path $dest){
    Remove-Item $dest -Recurse -Force
    git clone https://github.com/alyssaxuu/motionity.git $dest
    if($LASTEXITCODE -ne 0){throw 'Could not clone Motionity.'}
  } else {
    git clone https://github.com/alyssaxuu/motionity.git $dest
    if($LASTEXITCODE -ne 0){throw 'Could not clone Motionity.'}
  }

  $src=Join-Path $dest 'src'
  $bridge=Join-Path $src 'bramble-bridge.js'
  @'
(function(){
  function qs(name){return new URLSearchParams(window.location.search).get(name)}
  async function boot(){
    if(typeof window.jQuery==='undefined' || typeof saveFile!=='function' || typeof createThumbnail!=='function' || typeof saveAudio!=='function'){
      return setTimeout(boot,250);
    }
    try{
      var w=parseInt(qs('width')||'0',10), h=parseInt(qs('height')||'0',10);
      if(w){ $('#canvas-w input').val(w).trigger('change'); }
      if(h){ $('#canvas-h input').val(h).trigger('change'); }
      var dur=parseFloat(qs('duration')||'0');
      if(dur){ $('#canvas-duration input').val(dur.toFixed(2)).trigger('change'); }

      var image=qs('image');
      if(image && !sessionStorage.getItem('bramble-image-'+image)){
        var blob=await fetch(image).then(function(r){if(!r.ok)throw new Error('Scene image fetch failed');return r.blob()});
        var file=new File([blob],'bramble-scene.'+(blob.type.split('/')[1]||'png'),{type:blob.type||'image/png'});
        var thumb=await createThumbnail(file,250);
        await saveFile(dataURItoBlob(thumb),file,'image','Bramble & Grace Scene',true,false);
        sessionStorage.setItem('bramble-image-'+image,'1');
      }

      var audio=qs('audio');
      if(audio && !sessionStorage.getItem('bramble-audio-'+audio)){
        var ablob=await fetch(audio).then(function(r){if(!r.ok)throw new Error('Scene audio fetch failed');return r.blob()});
        var afile=new File([ablob],'scene-audio.wav',{type:ablob.type||'audio/wav'});
        await saveAudio(afile);
        sessionStorage.setItem('bramble-audio-'+audio,'1');
      }

      document.title='Bramble & Grace Scene Animator';
    }catch(err){
      console.error('Bramble Motionity bridge:',err);
    }
  }
  window.addEventListener('load',function(){setTimeout(boot,700)});
})();
'@ | Set-Content -Encoding UTF8 $bridge

  $index=Join-Path $src 'index.html'
  $html=Get-Content $index -Raw
  if($html -notmatch 'bramble-bridge\.js'){
    $html=$html -replace '</body>','<script src="bramble-bridge.js"></script></body>'
    Set-Content -Encoding UTF8 $index $html
  }

  Write-Host 'Motionity Scene Animator installed locally.' -ForegroundColor Green
  Write-Host 'Restart Clay Studio. Each scene will have an Animate Scene button.' -ForegroundColor Green
  exit 0
}

if($Component -eq 'wan22'){
  $comfy=Join-Path $Models 'comfyui'
  if(-not(Test-Path (Join-Path $comfy 'main.py'))){
    throw 'ComfyUI is not installed yet. Run INSTALL.bat first, then run INSTALL-WAN22.bat.'
  }

  $items=@(
    @{
      Url='https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors'
      Path=Join-Path $comfy 'models\diffusion_models\wan2.2_ti2v_5B_fp16.safetensors'
    },
    @{
      Url='https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors'
      Path=Join-Path $comfy 'models\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors'
    },
    @{
      Url='https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files/vae/wan2.2_vae.safetensors'
      Path=Join-Path $comfy 'models\vae\wan2.2_vae.safetensors'
    }
  )

  foreach($item in $items){
    $dir=Split-Path $item.Path -Parent
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    if(Test-Path $item.Path){
      Write-Host "Already installed: $(Split-Path $item.Path -Leaf)" -ForegroundColor Green
      continue
    }
    $partial=$item.Path+'.partial'
    Remove-Item $partial -Force -ErrorAction SilentlyContinue
    Write-Host "Downloading $(Split-Path $item.Path -Leaf)..." -ForegroundColor Cyan
    try{
      if(Get-Command Start-BitsTransfer -ErrorAction SilentlyContinue){
        Start-BitsTransfer -Source $item.Url -Destination $partial -DisplayName 'Bramble Grace Wan 2.2 model'
      } else {
        Invoke-WebRequest -UseBasicParsing -Uri $item.Url -OutFile $partial
      }
      Move-Item $partial $item.Path -Force
    } catch {
      Remove-Item $partial -Force -ErrorAction SilentlyContinue
      throw
    }
  }
  Write-Host ''
  Write-Host 'Wan 2.2 TI2V 5B is installed for AI Clay Performance.' -ForegroundColor Green
  Write-Host 'Restart Clay Studio, choose AI Clay Performance, and select the Wan 2.2 5B workflow.' -ForegroundColor Green
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
