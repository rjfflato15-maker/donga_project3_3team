# 소스 배포의 최초 설치와 업무함 준비

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [start_pilot.bat](../../start_pilot.bat) · [build_launcher.ps1](../../tools/launcher/build_launcher.ps1) · [operations.py](../../backend/launcher/operations.py) · [settings.py](../../backend/launcher/settings.py)

## 현재 사용할 수 있는 방식

앱 소스 폴더와 준비된 Python 환경을 함께 사용한다. Windows의 Python 3.12, Node.js/npm을 준비하고 PATH와 `py -3.12`를 확인한다. `start_pilot.bat`이 .NET Framework 컴파일러로 C-Pilot.exe를 만들고 실행한다. 이후에는 같은 앱 폴더 안의 EXE를 더블클릭하면 CMD 창 없이 앱을 연다. BAT는 개발·빌드용이라 CMD가 열릴 수 있다. 실행기와 관리 작업이 끝난 뒤 다시 빌드한다.

## 처음 준비

앱 폴더에서 `C-Pilot.exe manage`로 관리 메뉴를 연다. 관리 메뉴 3번은 backend/.venv 생성·requirements 설치·frontend의 npm ci·빌드를 진행한다. 실패하면 완료로 처리하지 않는다. 환경이 준비되어 있으면 매번 설치하지 않는다. 최초 준비는 인터넷 다운로드가 필요하며 폐쇄망의 런타임·패키지·모델 반입은 IT 담당자의 별도 준비가 필요하다.

관리 메뉴 4번에서 **빈 업무함 만들기**를 선택한다. 기존 자료 가져오기는 별도 선택이며 원본 DB 설정을 확인한 뒤 명시적으로 실행한다. 이미 pilot.db가 있으면 덮어쓰지 않는다. 초기 계정은 지정 자료 폴더의 initial-accounts.txt에 생성되며 첫 로그인에서 비밀번호를 바꾼다. 이 파일을 공유·커밋하지 않는다.

기본 자료·설정·백업 경로는 [실행 설정](startup_settings.md)에서 확인한다. 기존 .venv만 다른 PC로 복사하거나 EXE 하나만 복사하는 방식은 지원하지 않는다.

## AI와 Windows Setup

기본 텍스트 AI는 꺼져 있고 이미지 재판독은 사용자가 호출한다. Ollama·모델·실행 계정의 클라우드 비활성 설정이 있어야 동작한다. 설정은 [AI 설정](../ai/runtime_settings.md)이 기준이다.

이번 배포는 소스 전용이며 Setup EXE를 포함하지 않는다. 이전 버전의 격리 설치·업데이트·제거 기록은 [Windows 설치 범위](customer_package.md)에 보존한다. 현재 소스의 Windows 실행·Setup 재빌드·실제 AI 다운로드는 이번 구조 정리에서 검증하지 않았다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
