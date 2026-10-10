# 개발·운영·문서 도구

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [lint_docs.py](docs/lint_docs.py) · [package.json](../package.json)

| 폴더 | 책임 | 상태 |
| --- | --- | --- |
| launcher/ | C# EXE 입구·아이콘·빌드 | 소스 실행기 |
| ops/ | 시작·백업·예약 작업 | 설정 파일과 대상 업무함 확인 후 사용 |
| dev/ | 개발 BAT·Node 명령 도우미 | 실제 종료 코드·바인딩·실행 위치 확인 |
| docs/ | 문서 링크·출처·탐색·ERD 검사 | 문서 유지보수 도구 |
| installer/ | 실행 환경 payload·Inno Setup 빌드 소스 | 이전 버전의 Windows 격리 설치 기록 보존. 현재 소스의 EXE 재빌드·Windows 실행은 미검증 |
| submission/ | 소스 ZIP 허용 목록·문서 사본·비밀 검사·해시 | [제출 범위](../docs/submission/source_package.md) 기준. 고객 설치 payload와 별개 |
| docker/ | Dockerfile·Compose | 별도 경로. 현재 고객 배포 검증 범위 아님 |

프로젝트 루트의 npm test는 백엔드만 실행한다. frontend 테스트는 npm.cmd --prefix frontend test를 사용한다. Node 개발 도우미의 설치 완료 문구만으로 환경 준비 성공을 판단하지 않는다. 실행 환경과 명령은 [개발 환경](../docs/development/getting_started.md)을 따른다.

```powershell
& .\backend\.venv\Scripts\python.exe tools/docs/lint_docs.py
& .\backend\.venv\Scripts\python.exe tools/docs/lint_docs.py --all --report build/docs-lint.json
```

문서 명령을 lint가 자동 실행하지 않는다. 보존 자료의 문제는 별도 보고하며 수정하지 않는다. 사용법은 [문서 유지보수](../docs/development/documentation.md)에 있다. 설치기 빌드·예약 작업·고객 복원은 사용자 작업 범위를 확인한 뒤 별도로 진행한다.


[전체 문서](../docs/README.md) · [현재 구현 상태](../docs/progress/current_status.md)
