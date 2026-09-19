$Root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$env:PATH=(Join-Path $Root 'data\models\rhubarb')+';'+$env:PATH
function Mark($name,$ok,$detail=''){if($ok){Write-Host ("{0}: OK {1}" -f $name,$detail) -ForegroundColor Green}else{Write-Host ("{0}: MISSING {1}" -f $name,$detail) -ForegroundColor Yellow}}
$py=Test-Path (Join-Path $Root '.venv\Scripts\python.exe');Mark 'Python environment' $py
Mark 'Node' ([bool](Get-Command node -ErrorAction SilentlyContinue))
Mark 'npm' ([bool](Get-Command npm -ErrorAction SilentlyContinue))
Mark 'Git' ([bool](Get-Command git -ErrorAction SilentlyContinue))
Mark 'FFmpeg' ([bool](Get-Command ffmpeg -ErrorAction SilentlyContinue))
Mark 'Rhubarb' ([bool](Get-Command rhubarb -ErrorAction SilentlyContinue))
Mark 'Chatterbox runtime' (Test-Path (Join-Path $Root 'runtime\chatterbox-venv\Scripts\python.exe'))
Mark 'ComfyUI' (Test-Path (Join-Path $Root 'data\models\comfyui\main.py'))
$gpus=Get-CimInstance Win32_VideoController|Where-Object{$_.Name -and $_.Name -notmatch 'Microsoft'}
foreach($g in $gpus){Write-Host ('GPU: '+$g.Name)}
$mem=$null
Get-ChildItem 'HKLM:\SYSTEM\CurrentControlSet\Control\Video' -ErrorAction SilentlyContinue|ForEach-Object{Get-ChildItem $_.PSPath -ErrorAction SilentlyContinue|ForEach-Object{try{$v=(Get-ItemProperty $_.PSPath -Name 'HardwareInformation.qwMemorySize' -ErrorAction Stop).'HardwareInformation.qwMemorySize';if($v -and [uint64]$v -gt [uint64]$mem){$mem=[uint64]$v}}catch{}}}
if($mem){Write-Host ('GPU VRAM: '+[math]::Round($mem/1GB,1)+' GB')}
$rootPath=[IO.Path]::GetPathRoot($Root)
if($rootPath){
  $driveName=$rootPath.Substring(0,1)
  $drive=Get-PSDrive -Name $driveName -ErrorAction SilentlyContinue
  if($drive){Write-Host ('Disk: '+[math]::Round($drive.Free/1GB,1)+' GB free')}
}
if(Test-Path (Join-Path $Root 'frontend\dist\index.html')){Mark 'Frontend build' $true}else{Mark 'Frontend build' $false}
