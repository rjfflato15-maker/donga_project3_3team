param(
    [switch]$Intranet,
    [int]$Port = 8000,
    [string]$StorageRoot = '',
    [switch]$SecureCookies,
    [switch]$KeepRunning
)
$ErrorActionPreference = 'Stop'
$pilotProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$pilotPython = Join-Path $pilotProjectRoot 'backend\.venv\Scripts\python.exe'
$pilotFrontend = Join-Path $pilotProjectRoot 'frontend\dist\index.html'
if (-not (Test-Path -LiteralPath $pilotPython)) { throw 'backend\.venv 가상환경이 없습니다. 운영 안내의 준비 절차를 진행하세요.' }
if (-not (Test-Path -LiteralPath $pilotFrontend)) { throw '프런트엔드 빌드가 없습니다. frontend에서 npm ci와 npm run build를 실행하세요.' }
if ([string]::IsNullOrWhiteSpace($StorageRoot)) { $StorageRoot = Join-Path $pilotProjectRoot 'storage\pilot' }
$pilotResolvedStorage = [System.IO.Path]::GetFullPath($StorageRoot)
if (-not (Test-Path -LiteralPath (Join-Path $pilotResolvedStorage 'pilot.db'))) { throw '시범 DB가 없습니다. backend\manage_pilot.py migrate 또는 migrate --empty로 먼저 준비하세요.' }
$env:APP_DEPLOYMENT_MODE = 'pilot'
$env:APP_NTS_MODE = 'disabled'
$env:APP_STORAGE_ROOT = $pilotResolvedStorage
$env:APP_COOKIE_SECURE = if ($SecureCookies) { 'true' } else { 'false' }
$pilotBind = if ($Intranet) { '0.0.0.0' } else { '127.0.0.1' }
Write-Host 'C업체 시범환경을 .venv에서 실행합니다. DB와 원본은 지정한 공용 저장소에 보관됩니다.'
Write-Host "현재 PC 접속: http://127.0.0.1:$Port/"
if ($Intranet) { Write-Host '같은 사내망에서는 이 PC의 사내 IP 주소로 접속하세요. 방화벽은 회사 IT 담당자가 사내 대역만 허용해야 합니다.' }
Push-Location $pilotProjectRoot
try {
    do {
        & $pilotPython -m uvicorn backend.app.main:app --host $pilotBind --port $Port --workers 1 --no-access-log
        if (-not $KeepRunning -and $LASTEXITCODE -ne 0) { throw '앱 실행을 완료하지 못했습니다. 실행 로그와 포트 사용 상태를 확인하세요.' }
        if ($KeepRunning) { Start-Sleep -Seconds 5 }
    } while ($KeepRunning)
} finally { Pop-Location }
