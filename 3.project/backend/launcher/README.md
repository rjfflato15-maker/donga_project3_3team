# 통합 실행기 소스 안내

`C-Pilot.exe`는 기존 `backend/pilot_launcher.py`를 호출한다. 이 파일은 실행 입구만 유지하고 아래 모듈로 연결한다. 관리 메뉴·CLI 명령과 앱의 동작은 그대로다.

| 파일 | 책임 | 수정할 때 |
| --- | --- | --- |
| [environment.py](environment.py) | 프로젝트 경로·Python·필수 모듈·서브프로세스 환경 | 실행 환경·환경 준비 점검 변경 |
| [settings.py](settings.py) | 실행 설정 읽기·검증·저장·작업 잠금 | 설정 항목·경로 정책 변경 |
| [server.py](server.py) | 서버 식별·준비 확인·중복 방지·실행·종료 | 서버 생명주기 변경 |
| [operations.py](operations.py) | 환경 준비·업무함 준비·백업·복원 위임 | 설치 또는 기존 관리 도구 연결 변경 |
| [cli.py](cli.py) | 명령행 인자·한국어 관리 메뉴 | 관리 메뉴·명령 추가 |

호출 방향은 `pilot_launcher → cli → settings/server/operations → environment`다. `operations`는 서버 종료 상태를 확인하고 기존 `manage_pilot.py`를 호출한다. 다른 모듈에서 `cli`를 불러오지 않는다. DB·AI·계정 업무 로직은 실행기에 추가하지 않는다.

확인은 프로젝트 루트에서 `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_pilot_launcher.py -q`로 한다. 실제 실행·복원은 고객 업무함 대신 별도 임시 폴더에서 확인한다.

[개발자 작업 안내](../../docs/development/maintenance.md) · [운영 안내](../../docs/operations/run_guide.md)
