$ErrorActionPreference='SilentlyContinue'
$Root=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PidFile=Join-Path $Root 'runtime\owned-pids.txt'
if(-not(Test-Path $PidFile)){Write-Host 'No Clay Studio-owned local processes are recorded.';exit 0}
$lines=Get-Content $PidFile
foreach($line in $lines){
  $parts=$line -split '\|'
  if($parts.Count -lt 3){continue}
  $pidValue=[int]$parts[0];$ticks=[int64]$parts[1];$label=$parts[2]
  $proc=Get-Process -Id $pidValue -ErrorAction SilentlyContinue
  if($proc){
    try{
      if($proc.StartTime.ToFileTimeUtc() -eq $ticks){Stop-Process -Id $pidValue -Force -ErrorAction Stop;Write-Host "Stopped $label (PID $pidValue)"}
    }catch{}
  }
}
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
