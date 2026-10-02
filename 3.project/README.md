# 계약 증빙 자동검수

계약 대금 지급 전에 증빙서류의 누락과 불일치를 확인하는 C업체 시범 앱이다.

**평소에는 C-Pilot.exe만 실행한다.** Git 소스를 처음 받았다면 **start_pilot.bat**으로 EXE를 만든다. 새 PC는 Python 3.12·Node.js를 준비하고 관리 메뉴 **3 환경 준비 → 4 업무함 준비 → 1 실행** 순서로 진행한다. 실행 창에서 **M**을 입력하면 설정·백업·복원 메뉴가 열린다.

EXE는 앱 폴더와 준비된 Python 환경이 필요한 실행 입구다. EXE만 다른 PC로 옮겨 사용하는 단독 설치형 배포는 아직 아니다. 기본은 현재 PC 접속·외부 조회와 LLM 비활성이다.

| 찾는 내용 | 시작 문서 |
| --- | --- |
| 설치·설정·계정·백업 | [운영 문서 목록](docs/operations/run_guide.md) |
| 무엇이 완료됐고 남았는지 | [진행 요약](docs/progress/development_report.md) |
| 어느 소스를 수정할지 | [소스 역할 표](docs/architecture/module_map.md) |
| 수정 후 확인·업데이트 절차 | [개발자 작업 안내](docs/development/maintenance.md) |
| LLM 설정·성능 평가 | [LLM·평가 문서 목록](docs/eval/local_llm_runbook.md) |
| 나머지 설계·참고 문서 | [전체 문서 목록](docs/README.md) |

고객 업무 자료·계정 안내·설정·백업은 Git에 올리지 않는다. 개발자는 기존 start_dev.bat 또는 npm run dev를 사용한다. 화면 변경은 계획과 이미지 시안을 승인받은 뒤 적용한다.
