param([int]$Port = 8000, [string]$SettingsFile = '')
$ErrorActionPreference = 'Stop'
$pilotProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$pilotStartScript = Join-Path $PSScriptRoot 'start_pilot.ps1'
$pilotAccount = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$pilotArguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $pilotStartScript + '" -Intranet -KeepRunning -Port ' + $Port
if ($SettingsFile) {
    $pilotResolvedSettings = [System.IO.Path]::GetFullPath($SettingsFile)
    if ($pilotResolvedSettings.Contains('"') -or -not (Test-Path -LiteralPath $pilotResolvedSettings)) { throw '실행 설정 파일을 확인하세요.' }
    if (-not (Test-Path -LiteralPath (Join-Path $pilotProjectRoot 'C-Pilot.exe'))) { throw '통합 실행 파일을 먼저 준비하세요.' }
    $pilotStartScript = Join-Path $PSScriptRoot 'scheduled_launcher.ps1'
    $pilotArguments = '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $pilotStartScript + '" -Action start -SettingsFile "' + $pilotResolvedSettings + '"'
}
$pilotAction = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $pilotArguments -WorkingDirectory $pilotProjectRoot
$pilotTrigger = New-ScheduledTaskTrigger -AtLogOn -User $pilotAccount
$pilotSettings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'C-Pilot-Contract-App' -Action $pilotAction -Trigger $pilotTrigger -Settings $pilotSettings -Description 'C업체 계약 증빙 공동 업무함' | Out-Null
Write-Host '현재 Windows 사용자가 로그인하면 앱을 자동 시작하도록 등록했습니다. 로그인 전 부팅 시 실행되는 서비스는 별도 운영 설정이 필요합니다.'
