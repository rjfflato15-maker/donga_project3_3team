# 개발·운영 도구

일반 사용자는 프로젝트 루트의 **C-Pilot.exe**를 사용한다. Git 소스를 처음 받으면 루트의 **start_pilot.bat**이 EXE를 만든다.

| 폴더 | 들어 있는 도구 | 담당 |
| --- | --- | --- |
| `launcher/` | EXE 진입점·build_launcher.ps1 | 실행기 개발 |
| `ops/` | 고급 실행·백업·예약 작업 PowerShell | 운영 담당 |
| `dev/` | 개발용 BAT와 `node/`의 npm 명령 스크립트 | 개발 담당 |
| `docker/` | 기존 Dockerfile·Compose | 별도 컨테이너 개발 |

개발 BAT는 현재 작업 폴더와 관계없이 프로젝트 루트로 이동한다. 기존 `npm run dev`, `npm test`, `npm start` 명령은 같은 이름으로 유지한다. Python 의존성은 `backend/requirements.txt` 한 곳에서 관리한다.

컨테이너는 프로젝트 루트에서 `docker compose -f tools/docker/docker-compose.yml up --build`를 사용한다. Windows 시범 실행기의 기본 사용 경로와는 별도다. 폴더 정리에서는 Compose 경로·빌드 문맥만 확인했으며 실제 컨테이너 설치·빌드는 검증하지 않았다.

[운영 문서 목록](../docs/operations/run_guide.md) · [개발자 작업 안내](../docs/development/maintenance.md)
