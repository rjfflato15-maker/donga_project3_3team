param([switch]$OnlyIfMissing)
$ErrorActionPreference = 'Stop'
$launcherProject = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$launcherSource = Join-Path $PSScriptRoot 'Program.cs'
$launcherIcon = Join-Path $PSScriptRoot 'assets\cpilot.ico'
$launcherOutput = Join-Path $launcherProject 'C-Pilot.exe'
$launcherInputs = @($launcherSource, $launcherIcon, $PSCommandPath)
foreach ($launcherInput in $launcherInputs) {
    if (-not (Test-Path -LiteralPath $launcherInput)) { throw "실행기 빌드 파일이 없습니다: $launcherInput" }
}
$launcherLatestInput = ($launcherInputs | ForEach-Object { (Get-Item -LiteralPath $_).LastWriteTimeUtc } | Sort-Object -Descending | Select-Object -First 1)
if ($OnlyIfMissing -and (Test-Path -LiteralPath $launcherOutput) -and ((Get-Item -LiteralPath $launcherOutput).LastWriteTimeUtc -ge $launcherLatestInput)) { exit 0 }
$launcherCompiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework\v4.0.30319\csc.exe'
if (-not (Test-Path -LiteralPath $launcherCompiler)) { throw 'Windows .NET Framework C# 컴파일러가 없습니다. 운영 안내의 실행 파일 빌드 항목을 확인하세요.' }
& $launcherCompiler /nologo /target:winexe /platform:anycpu /optimize+ "/win32icon:$launcherIcon" "/out:$launcherOutput" $launcherSource
if ($LASTEXITCODE -ne 0) { throw '실행 파일을 만들지 못했습니다. C-Pilot 실행 창이 열려 있으면 닫고 다시 실행하세요.' }
Write-Host 'C-Pilot.exe 준비 완료. 평소에는 이 파일 하나를 실행하세요.'
