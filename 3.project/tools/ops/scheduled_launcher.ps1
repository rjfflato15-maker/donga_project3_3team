param(
    [Parameter(Mandatory=$true)][ValidateSet('start','backup')][string]$Action,
    [Parameter(Mandatory=$true)][string]$SettingsFile
)
$ErrorActionPreference = 'Stop'
$launcherProject = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$launcherExecutable = Join-Path $launcherProject 'C-Pilot.exe'
$launcherSettingsPath = [System.IO.Path]::GetFullPath($SettingsFile)
$launcherProcess = Start-Process -FilePath $launcherExecutable -ArgumentList @($Action, '--no-browser', '--settings-file', ('"' + $launcherSettingsPath + '"')) -WorkingDirectory $launcherProject -WindowStyle Hidden -Wait -PassThru
if ($launcherProcess.ExitCode -ne 0) { throw '예약된 실행·백업 작업이 실패했습니다. 통합 실행기의 상태 점검을 확인하세요.' }
