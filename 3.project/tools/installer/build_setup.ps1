param([string]$Version='1.0.0', [string]$Compiler='')
$ErrorActionPreference='Stop'
$packageProject=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
if (-not $Compiler) { $Compiler=Join-Path $packageProject 'build\installer-tools\InnoSetup\ISCC.exe' }
if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Inno Setup 6 컴파일러의 ISCC.exe 경로를 -Compiler로 지정하세요.' }
$packagePython=Join-Path $packageProject 'backend\.venv\Scripts\python.exe'
& (Join-Path $packageProject 'tools\launcher\build_launcher.ps1') -OnlyIfMissing
if ($LASTEXITCODE -ne 0) { throw '실행기 빌드 실패' }
$packageOutput=& $packagePython -X utf8 (Join-Path $PSScriptRoot 'build_package.py') --version $Version
if ($LASTEXITCODE -ne 0) { throw '실행 환경 패키징 실패' }
$packageStage=[string]($packageOutput | Select-Object -Last 1)
$packageRelease=Join-Path $packageProject 'dist'
New-Item -ItemType Directory -Path $packageRelease -Force | Out-Null
& $Compiler /Q (Join-Path $PSScriptRoot 'C-Pilot.iss') "/DPayloadDir=$packageStage" "/DReleaseDir=$packageRelease" "/DAppVersion=$Version"
if ($LASTEXITCODE -ne 0) { throw 'Setup 설치 파일 빌드 실패' }
$packageSetup=Join-Path $packageRelease "C-Pilot-Setup-$Version.exe"
$packageHash=(Get-FileHash -LiteralPath $packageSetup -Algorithm SHA256).Hash
[IO.File]::WriteAllText(($packageSetup+'.sha256'),($packageHash+'  '+[IO.Path]::GetFileName($packageSetup)+[Environment]::NewLine))
Write-Output $packageSetup
