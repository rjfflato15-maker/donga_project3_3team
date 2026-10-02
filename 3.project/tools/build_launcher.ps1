param([switch]$OnlyIfMissing)
$ErrorActionPreference = 'Stop'
$launcherProject = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$launcherSource = Join-Path $PSScriptRoot 'launcher\Program.cs'
$launcherOutput = Join-Path $launcherProject 'C-Pilot.exe'
if ($OnlyIfMissing -and (Test-Path -LiteralPath $launcherOutput) -and ((Get-Item -LiteralPath $launcherOutput).LastWriteTimeUtc -ge (Get-Item -LiteralPath $launcherSource).LastWriteTimeUtc)) { exit 0 }
$launcherCompiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $launcherCompiler)) { throw 'Windows .NET Framework C# 컴파일러가 없습니다. 운영 안내의 실행 파일 빌드 항목을 확인하세요.' }
& $launcherCompiler /nologo /target:exe /platform:anycpu /optimize+ "/out:$launcherOutput" $launcherSource
if ($LASTEXITCODE -ne 0) { throw '실행 파일을 만들지 못했습니다.' }
Write-Host 'C-Pilot.exe 준비 완료. 평소에는 이 파일 하나를 실행하세요.'
