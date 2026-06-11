# Tier-D 本地串行驱动(P3-A 作业 x4):preprocess -> Explicit -> postprocess
$abq = 'D:\ABAQUS\2023\Commands\abaqus.bat'
$root = 'D:\ARTC\ARTC-Auto-Script\atlas\reports\tier_d_jobs'
$jobs = @(
  @{dir='dual_column_web';   name='dual_column_web_5_0p5_4_StaCompre'},
  @{dir='mid_braced_column'; name='mid_braced_column_5_0p5_4_StaCompre'},
  @{dir='twin_offset_web';   name='twin_offset_web_5_0p5_4_StaCompre'},
  @{dir='pscz_lpbf';         name='PSCZ_pillar_steepcross_5_0p588_4_StaCompre'}
)
foreach ($j in $jobs) {
  $d = Join-Path $root $j.dir
  Set-Location $d
  $log = Join-Path $d 'runlocal.log'
  "=== $($j.name) start $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" | Tee-Object $log -Append
  "[1/3] preprocess" | Tee-Object $log -Append
  & $abq cae "noGUI=$($j.name)_preprocess.py" 2>&1 | Out-File $log -Append -Encoding utf8
  if (-not (Test-Path (Join-Path $d "$($j.name).inp"))) {
    "ERROR: no .inp generated, skip job" | Tee-Object $log -Append
    continue
  }
  "[2/3] solver (cpus=8)" | Tee-Object $log -Append
  & $abq job=$($j.name) cpus=8 interactive 2>&1 | Out-File $log -Append -Encoding utf8
  "[3/3] postprocess" | Tee-Object $log -Append
  & $abq cae "noGUI=$($j.name)_postprocess.py" 2>&1 | Out-File $log -Append -Encoding utf8
  $ok = (Test-Path (Join-Path $d 'feature_data.txt')) -and (Test-Path (Join-Path $d 'energy_data.txt'))
  "=== $($j.name) done $(Get-Date -Format 'HH:mm:ss') | results: $ok ===" | Tee-Object $log -Append
}
"ALL JOBS FINISHED $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"