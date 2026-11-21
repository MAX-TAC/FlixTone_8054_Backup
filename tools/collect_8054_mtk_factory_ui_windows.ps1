# FlixTone 8054 MediaTek Factory Menu: read-only interactive screen inventory.
# Run in Windows PowerShell 5.1 or PowerShell 7 with adb in PATH.
# No remote keypress, setting changes, remount, root, reboot or flash.
param([string]$Adb='adb', [string]$Serial='', [string]$Out='')
$ErrorActionPreference='Stop'
if (-not $Out) { $Out=Join-Path $env:USERPROFILE ('Downloads\MTK_8054_FACTORY_'+(Get-Date -Format 'yyyyMMdd_HHmmss')) }
New-Item -ItemType Directory -Path $Out -Force | Out-Null
$baseArgs=@()
if ($Serial) { $baseArgs+=@('-s',$Serial) }
function AdbText([string[]]$argsToRun) {
  $argsAll=@($baseArgs)+@($argsToRun)
  $data=& $Adb @argsAll 2>&1
  if ($LASTEXITCODE -ne 0) { throw ('ADB failed: '+($argsAll -join ' ')) }
  return ($data -join [Environment]::NewLine)
}
function CapturePng([string]$fileName) {
  $exe=(Get-Command $Adb -ErrorAction Stop).Source
  $psi=New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName=$exe
  $psi.Arguments=if ($Serial) { '-s '+$Serial+' exec-out screencap -p' } else { 'exec-out screencap -p' }
  $psi.UseShellExecute=$false
  $psi.RedirectStandardOutput=$true
  $p=New-Object System.Diagnostics.Process
  $p.StartInfo=$psi
  [void]$p.Start()
  $fs=[IO.File]::Create($fileName)
  try { $p.StandardOutput.BaseStream.CopyTo($fs) } finally { $fs.Dispose() }
  [void]$p.WaitForExit(30000)
  if ($p.ExitCode -ne 0 -or (Get-Item $fileName).Length -lt 1000) { throw 'Screenshot failed' }
}
$devices=(AdbText @('devices')).Split([Environment]::NewLine) | Where-Object { $_ -match '\sdevice$' }
if (-not $Serial -and @($devices).Count -ne 1) { throw 'Select one device with -Serial; run adb devices' }
$id=(AdbText @('shell','getprop','ro.rjpj.machine.id')).Trim()
if ($id -ne '8054') { throw ('STOP: expected 8054, got '+$id) }
@('Machine=8054',('Build='+(AdbText @('shell','getprop','ro.build.display.id'))),'Collector: read-only ADB') |
  Out-File (Join-Path $Out 'DEVICE.txt') -Encoding UTF8
Write-Host 'Navigate menus on projector with remote. Do not modify Factory values, Save, Write or Reset.'
Write-Host 'Type current screen/path, press Enter to capture. Type q to finish.'
$keys=@('picture_mode','picture_gamma','picture_list_hdr','picture_color_temperature',
'picture_brightness','picture_contrast','picture_saturation','picture_sharpness','picture_hue',
'tv_picture_advance_video_mjc_effect','sound_style','sound_bass','sound_treble','sound_sound_surround',
'sound_spdif_type','sound_digital_output','sound_equalizer_detail_120hz','sound_equalizer_detail_500hz',
'sound_equalizer_detail_1500hz','sound_equalizer_detail_5000hz','sound_equalizer_detail_10000hz',
'sound_spdif_delay','sound_speaker_delay')
$index=New-Object System.Collections.Generic.List[object]
$n=0
while ($true) {
  $label=Read-Host 'Factory menu screen (q=exit)'
  if ($label.Trim().ToLowerInvariant() -eq 'q') { break }
  if ([string]::IsNullOrWhiteSpace($label)) { continue }
  $n++
  $num='{0:D3}' -f $n
  $png=Join-Path $Out ('screen_'+$num+'.png')
  $txt=Join-Path $Out ('screen_'+$num+'.txt')
  try {
    CapturePng $png
    $focus=((AdbText @('shell','dumpsys','window')) -split [Environment]::NewLine |
       Where-Object { $_ -match 'mCurrentFocus|mFocusedApp' }) -join [Environment]::NewLine
    $details=New-Object System.Collections.Generic.List[string]
    $details.Add('label='+$label)
    $details.Add('time='+(Get-Date -Format o))
    $details.Add('focus='+$focus)
    foreach ($key in $keys) {
      $value=(AdbText @('shell','settings','get','global',$key)).Trim()
      $details.Add($key+'='+$value)
    }
    $details | Out-File $txt -Encoding UTF8
    $index.Add([pscustomobject]@{number=$num;label=$label;image=[IO.Path]::GetFileName($png);
                 snapshot=[IO.Path]::GetFileName($txt);time=(Get-Date -Format o)})
    Write-Host ('Captured '+$num+' '+$label)
  } catch {
    Write-Warning $_.Exception.Message
    if (Test-Path $png) { Remove-Item $png -Force }
  }
}
$index | Export-Csv -Path (Join-Path $Out 'SCREEN_INDEX.csv') -NoTypeInformation -Encoding UTF8
Write-Host ('Saved '+$index.Count+' screens to '+$Out)
Write-Host 'Inspect screenshots for serial numbers and calibration data before sharing.'
