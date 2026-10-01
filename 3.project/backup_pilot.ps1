param([Parameter(Mandatory=$true)][string]$BackupDirectory)
$ErrorActionPreference = 'Stop'
$pilotPython = Join-Path $PSScriptRoot 'backend\.venv\Scripts\python.exe'
$pilotManager = Join-Path $PSScriptRoot 'backend\manage_pilot.py'
$pilotBackupName = 'C-pilot-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.zip'
$pilotBackupTarget = Join-Path ([System.IO.Path]::GetFullPath($BackupDirectory)) $pilotBackupName
& $pilotPython $pilotManager backup --output $pilotBackupTarget
if ($LASTEXITCODE -ne 0) { throw '백업을 완료하지 못했습니다.' }
Write-Host '백업을 생성했습니다. 이 ZIP은 암호화되지 않습니다. 보호된 사외/별도 장치 저장소와 복원 점검이 필요합니다.'
