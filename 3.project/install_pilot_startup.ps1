param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$pilotStartScript = Join-Path $PSScriptRoot 'start_pilot.ps1'
$pilotAccount = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$pilotArguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $pilotStartScript + '" -Intranet -KeepRunning -Port ' + $Port
$pilotAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $pilotArguments -WorkingDirectory $PSScriptRoot
$pilotTrigger = New-ScheduledTaskTrigger -AtLogOn -User $pilotAccount
$pilotSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'C-Pilot-Contract-App' -Action $pilotAction -Trigger $pilotTrigger -Settings $pilotSettings -Description 'C업체 계약 증빙 공동 업무함' | Out-Null
Write-Host '현재 Windows 사용자가 로그인하면 앱을 자동 시작하도록 등록했습니다. 로그인 전 부팅 시 실행되는 서비스는 별도 운영 설정이 필요합니다.'
