# 처음 설치와 업무함 준비

Git 소스에는 생성된 EXE를 포함하지 않는다. 처음에는 `start_pilot.bat`을 실행하면 `tools/launcher/build_launcher.ps1`이 Windows .NET Framework 컴파일러로 EXE를 만들고 실행한다. 이후에는 EXE 하나를 사용한다. 실행 파일을 다시 만들려면 `tools/launcher/build_launcher.ps1`을 실행한다. 소스가 변경되면 `start_pilot.bat`도 다시 빌드한다.

새 PC에는 Python 3.12와 Node.js·npm을 설치한다. Python은 Windows `py -3.12` 명령으로 찾을 수 있어야 하고 Node.js와 npm은 PATH에서 찾을 수 있어야 한다. 관리 메뉴 3번에서 프로젝트 전용 `backend/.venv` 생성, 필요한 Python 패키지 설치, `npm ci`, 화면 빌드를 진행한다. 설치나 빌드에 실패하면 완료로 표시하지 않는다. 기존 실행 환경이 준비되어 있으면 매번 설치하지 않는다.

환경 준비는 패키지 다운로드가 필요하다. 인터넷이 없는 망에는 IT 담당자가 검증한 설치 프로그램·Python 패키지·Node 패키지·화면 빌드를 반입해 준비한다. 이번 작업에 오프라인 설치 패키지 생성·검증 기능까지 구현하지는 않았다. Ollama와 모델도 별도 설치 항목이며 통합 실행기는 LLM을 활성화하지 않는다.

관리 메뉴 4번의 **빈 업무함 만들기**는 새 회사용이다. **기존 자료 가져오기**는 기존 DB 설정의 자료를 읽어 이주하는 별도 선택이며 자동 실행하지 않는다. 이미 `pilot.db`가 있으면 덮어쓰지 않는다. 초기 계정은 지정 자료 폴더의 `initial-accounts.txt`에서 확인하고 첫 로그인 후 비밀번호를 바꾼다. 이 파일은 공유하거나 Git에 넣지 않는다.

EXE는 Python 프로그램을 호출하는 작은 실행 입구다. 앱 폴더와 실행 환경이 함께 필요하다. EXE만 따로 옮기거나 기존 `.venv` 폴더만 다른 PC에 복사하는 방식은 지원하지 않는다. Python과 모델까지 포함한 단독 설치형 배포는 향후 범위다.

EXE 소스나 아이콘을 바꾸어 다시 컴파일할 때는 먼저 통합 실행기의 콘솔 창을 닫는다. Windows는 실행 중인 EXE를 덮어쓰지 못하게 잠근다. 브라우저만 닫아서는 실행기 콘솔이 종료되지 않는다. 아이콘 원본은 `tools/launcher/assets/cpilot.png`, 다중 크기 Windows 아이콘은 `cpilot.ico`이다. 빌드 스크립트는 소스·아이콘·스크립트 변경을 감지해 다시 빌드한다.

[운영 문서 목록](run_guide.md) · [실행과 설정](startup_settings.md)
