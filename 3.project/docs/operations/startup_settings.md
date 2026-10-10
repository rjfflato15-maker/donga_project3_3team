# 실행·종료·설정·코드 적용

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: HEAD `54a8841` + 미커밋 작업 트리. 작업 트리 기준. 설치 검증 범위는 고객 패키지 안내 참조.

관련 소스: [cli.py](../../backend/launcher/cli.py) · [settings.py](../../backend/launcher/settings.py) · [server.py](../../backend/launcher/server.py)

C-Pilot.exe를 더블클릭하면 CMD 창 없이 서버 준비를 확인하고 브라우저를 연다. 성공 후 실행기는 자동으로 끝나며, 시작에 실패한 경우에만 오류 안내 창이 뜬다. 같은 설정으로 다시 실행하면 기존 서버를 재사용한다. 브라우저를 닫아도 서버는 계속 실행되므로 관리 메뉴 9번으로 종료한다. 분석·저장을 마친 뒤 종료한다.

관리 메뉴는 앱 폴더에서 `C-Pilot.exe manage`로 따로 연다. 이 메뉴와 명시적으로 호출한 `setup`·`setup-ai`만 필요할 때 콘솔을 사용한다. 예약 실행·백업은 콘솔 창 없이 완료를 기다리고 종료 코드를 확인한다.

PowerShell에서 관리 메뉴를 사용할 때는 아래처럼 완료를 기다린다. GUI EXE를 직접 호출하면 PowerShell 프롬프트가 먼저 돌아올 수 있다.

```powershell
Start-Process -FilePath '.\C-Pilot.exe' -ArgumentList 'manage' -Wait -NoNewWindow
```

| 메뉴 | 기능 |
| --- | --- |
| 1 | 서버 시작·브라우저 열기 |
| 2 | 실행 환경·화면·업무함·서버 상태 |
| 3 | 소스 실행의 최초 환경 준비 |
| 4 | 빈 업무함 또는 기존 자료 이주 |
| 5 | 포트·자료·백업 위치·사내망 설정 |
| 6 / 7 | 지금 백업 / 새 폴더 복원 |
| 8 | 사용자 선택 시 자동 실행·백업 등록 |
| 9 / 0 | 서버 종료 / 관리 창만 닫기 |
| 10 | 로컬 AI 자동 준비 초안. 고객 환경 검증 전 |

## 설정 기준

소스 실행의 기본은 8000 포트, 현재 PC 접속, storage/pilot 자료, storage/backups 백업이다. 설정·로그·서버 실행 기록은 storage/launcher 아래에 있다. 계정·회사·필수서류·결재 정책은 업무 DB에 저장된다. AI 설정은 [설정 기준](../ai/runtime_settings.md)에 있다. 설치형 사용자별 경로는 아직 배포 검증 전이다.

설정 변경·복원·환경 준비 전에는 같은 설정 파일의 서버를 종료한다. 다른 프로그램이 포트를 사용하면 그 프로그램을 재사용·종료하지 않는다. 실행기는 PID·생성 시각·실행 경로와 앱 고유 식별자를 비교해 자기 서버를 확인한다.

<a id="코드-교체병합-뒤에는-서버도-재시작"></a>

## 코드 변경 후에는 종료→시작

새 Python 코드가 기존 서버에 자동 적용된다고 가정하지 않는다. EXE 재실행도 기존 서버를 재사용할 수 있다. 화면 빌드와 백업을 마친 뒤 대상 업무함의 설정 파일로 종료→시작한다.

```powershell
# 프로젝트 루트, 기본 소스 업무함의 서버
Start-Process -FilePath '.\C-Pilot.exe' -ArgumentList 'stop' -Wait -NoNewWindow
Start-Process -FilePath '.\C-Pilot.exe' -ArgumentList 'start', '--no-browser' -Wait -NoNewWindow
```

사용자 지정 업무함이면 두 명령에 같은 `--settings-file` 경로를 명시한다. 공백이 있는 설정 경로는 인수 안에서도 따옴표로 감싼다. 자동화에서 성공 여부를 확인하려면 `-PassThru`로 받은 프로세스의 `ExitCode`를 검사한다. 운영 업무함을 개발 테스트 대상으로 선택하지 않는다. 시작 뒤 health·로그인·계약·문서 조회를 확인한다. 새 테이블 생성은 기존 컬럼 이주·백업 호환 검증을 대신하지 않는다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
