param(
    [Parameter(Mandatory=$true)][string]$BackupDirectory,
    [string]$DailyTime = '18:00'
)
$ErrorActionPreference = 'Stop'
$pilotBackupScript = Join-Path $PSScriptRoot 'backup_pilot.ps1'
$pilotResolvedBackup = [System.IO.Path]::GetFullPath($BackupDirectory)
if ($pilotResolvedBackup.Contains('"')) { throw '백업 경로에 따옴표를 사용할 수 없습니다.' }
$pilotArguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $pilotBackupScript + '" -BackupDirectory "' + $pilotResolvedBackup + '"'
$pilotAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $pilotArguments -WorkingDirectory $PSScriptRoot
$pilotTrigger = New-ScheduledTaskTrigger -Daily -At $DailyTime
$pilotSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName 'C-Pilot-Daily-Backup' -Action $pilotAction -Trigger $pilotTrigger -Settings $pilotSettings -Description 'C업체 계약 DB와 원본 일일 백업' | Out-Null
Write-Host 'Windows 작업 스케줄러에 일일 백업을 등록했습니다. 저장소 접근 권한, Windows 로그인 조건, 암호화 저장소, 보관 기간과 실패 알림은 운영 담당자가 확인해야 합니다.'
