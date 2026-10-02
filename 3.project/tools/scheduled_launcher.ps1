param(
    [Parameter(Mandatory=$true)][ValidateSet('start','backup')][string]$Action,
    [Parameter(Mandatory=$true)][string]$SettingsFile
)
$ErrorActionPreference = 'Stop'
$launcherProject = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$launcherExecutable = Join-Path $launcherProject 'C-Pilot.exe'
& $launcherExecutable $Action --no-browser --settings-file ([System.IO.Path]::GetFullPath($SettingsFile))
if ($LASTEXITCODE -ne 0) { throw '예약된 실행·백업 작업이 실패했습니다. 통합 실행기의 상태 점검을 확인하세요.' }
