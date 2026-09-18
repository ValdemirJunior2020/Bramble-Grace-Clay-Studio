$ErrorActionPreference='Stop'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$LogDir=Join-Path $Root 'logs';New-Item -ItemType Directory -Force $LogDir|Out-Null
$DataDirs=@('data\projects','data\characters','data\voices','data\models','data\cache','data\temp','logs','runtime');foreach($d in $DataDirs){New-Item -ItemType Directory -Force (Join-Path $Root $d)|Out-Null}
$env:HF_HOME=Join-Path $Root 'data\models\huggingface'
Write-Host '=== Bramble & Grace Clay Studio Installer ==='
function Need($cmd,$label){if(-not(Get-Command $cmd -ErrorAction SilentlyContinue)){throw "$label is required but was not found."}}
Need git 'Git';Need node 'Node.js';Need npm 'npm';Need ffmpeg 'FFmpeg'
$py=& py -3.11 -c "import sys;print(sys.executable)" 2>$null;if($LASTEXITCODE -ne 0){$py=& python -c "import sys;print(sys.executable)" 2>$null;if($LASTEXITCODE -ne 0){throw 'Python 3.11 is required.'}}
$venv=Join-Path $Root '.venv';if(-not(Test-Path (Join-Path $venv 'Scripts\python.exe'))){& $py.Trim() -m venv $venv}
$vpy=Join-Path $venv 'Scripts\python.exe';& $vpy -m pip install --upgrade pip;& $vpy -m pip install -r (Join-Path $Root 'backend\requirements.txt')
Push-Location (Join-Path $Root 'frontend');if(-not(Test-Path 'node_modules')){npm install}else{npm install --prefer-offline};npm run build;Pop-Location
& $vpy -c "import sys;sys.path.insert(0,r'$Root\backend');from app.storage import init_db,ensure_default_characters;init_db();ensure_default_characters();print('Application data ready')"
& $vpy (Join-Path $Root 'demo\create_demo.py')
if(-not(Test-Path (Join-Path $Root 'data\models\rhubarb\rhubarb.exe'))){$a=Read-Host 'Install small Rhubarb Lip Sync tool now? [Y/n]';if($a -notmatch '^[Nn]'){& (Join-Path $Root 'scripts\install_optional.ps1') -Component rhubarb}}
if(-not(Test-Path (Join-Path $Root 'runtime\chatterbox-venv\Scripts\python.exe'))){$a=Read-Host 'Install Chatterbox Multilingual TTS and cache its model for offline use? This is a larger download. [y/N]';if($a -match '^[Yy]'){& (Join-Path $Root 'scripts\install_optional.ps1') -Component chatterbox}}
if(-not(Test-Path (Join-Path $Root 'data\models\comfyui\main.py'))){$a=Read-Host 'Install optional ComfyUI engine now? Large video models are NOT downloaded automatically. [y/N]';if($a -match '^[Yy]'){& (Join-Path $Root 'scripts\install_optional.ps1') -Component comfyui}}
Write-Host '';Write-Host 'Installation complete. Running check...'; & (Join-Path $Root 'scripts\check.ps1')
