# 코드·고객 자료·평가·배포 경계

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [build_package.py](../../tools/installer/build_package.py) · [.gitignore](../../.gitignore)

| 구분 | 경로·취급 |
| --- | --- |
| 앱 소스 | backend/app, backend/launcher, pilot_launcher.py, manage_pilot.py. 현재 코드와 고정 평가 snapshot 구분 |
| 화면 | frontend/src 개발 소스, frontend/dist 빌드 결과 |
| 실행 도구 | tools/launcher·tools/ops·tools/installer의 소스. 현재 ZIP에 설치 EXE는 포함하지 않음 |
| 실행 환경 | .venv·node_modules는 개발 환경. .venv 폴더 복사 배포를 지원하지 않음 |
| 고객 자료 | DB·원본·가린 파일·텍스트. 앱 업데이트와 분리 |
| 설정·비밀 | 환경 설정·초기 계정·서버 기록. 공용 Git/배포에 포함하지 않음 |
| 백업 | 지정 백업 폴더. 소스·설치 payload와 분리 |
| 평가 | eval·docs/eval·sample-data·release lock. 원본 경로/해시 보존 |
| 연구·시안·임시 작업 | 고객 실행에 필요한 자료와 분리. 필요 확인 없이 삭제하지 않음 |
| 모델 | Ollama 저장소. 별도 모델 라이선스·설치/반입 확인 |

설치 payload 빌더는 허용 목록으로 앱·화면·Python 의존성을 수집한다. 이전 버전의 격리 설치 기록과 현재 소스 전용 배포는 별개다. 이번 작업은 EXE 재빌드나 Windows 실행 검증을 포함하지 않는다. 설치형 배포 시 필요한 확인 범위는 [설치 상태](../operations/customer_package.md)를 따른다. 소스 ZIP은 작업 트리와 파일별 해시로 고정하며 과거 HEAD만 압축하지 않는다.

고객 제공 범위는 실제 import·화면 로딩·파일 판독·백업/복구와 라이브러리 고지를 확인한 뒤 정한다. HWP의 pyhwp AGPL 조건은 판매 전 검토 대상으로 남아 있다. 배포 전 검사에서 평가 원본·실제 고객 DB·환경 변수 파일·초기 비밀번호를 제외한다. 검증한 허용 목록을 사용하며 프로젝트 전체를 무조건 ZIP으로 묶지 않는다.

업데이트는 [운영 절차](../operations/maintenance.md), 원본·캐시 보관은 [폴더 안내](folder_guide.md)를 따른다. 소스 공개 범위나 판매 계약은 이번 문서 정리로 변경하지 않는다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
