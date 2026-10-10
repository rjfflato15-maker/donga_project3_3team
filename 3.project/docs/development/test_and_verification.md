# 테스트·빌드·확인과 오류 대응

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: HEAD `54a8841` + 미커밋 작업 트리. 작업 트리 기준. 설치 검증 범위는 고객 패키지 안내 참조.

관련 소스: [package.json](../../package.json) · [package.json](../../frontend/package.json) · [conftest.py](../../backend/tests/conftest.py) · [lint_docs.py](../../tools/docs/lint_docs.py)

## 프로젝트 루트에서 실행

```powershell
# 백엔드 전체. 고객 DB 대신 테스트 fixture의 임시 DB를 사용
& .\backend\.venv\Scripts\python.exe -X utf8 -m pytest backend/tests -q

# 프론트엔드 테스트와 타입·배포 빌드
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build

# 문서 검사와 검사 도구의 회귀 검증
& .\backend\.venv\Scripts\python.exe tools/docs/lint_docs.py
& .\backend\.venv\Scripts\python.exe -m unittest tools.docs.test_lint_docs -v
```

프로젝트 루트의 `npm test`는 현재 백엔드 pytest만 호출한다. 프론트엔드 검증은 `--prefix frontend`를 명시한다. 테스트가 통과해도 실제 모델 호출·배포 설치·사용자 클릭을 모두 확인한 것은 아니다. 최신 실행 결과는 [검증 기록](verification_latest.md) 한 곳에서 관리한다.

의존성을 새로 설치한 뒤에는 버전 차이를 [검증 환경](verification_environment.json)과 비교한다. backend requirements는 최소 버전 범위이며 frontend는 package-lock으로 고정한 설치를 사용한다. 과거 통과 숫자를 새 환경의 결과로 복사하지 않는다.

## 영향에 맞는 검증

| 변경 | 최소 확인 |
| --- | --- |
| 표시·버튼 | 해당 component test, TypeScript/Vite 빌드, 화면·모바일·콘솔 |
| API·권한 | 성공/오류 응답, 로그인·역할, 오래된 revision, 프론트 타입 |
| 필드·검수 | 0/null, 당사자, 의미 불명확, 정정·재발행·후속 결재 |
| VLM | 후보만 생성, 선택 저장, 실패·권한·원본/자료 변경 |
| 내보내기 | 가림/실제값, 복수 문서, 0/null, ID 앞자리, 현재 결재 |
| 실행기 | 같은 서버 재사용, 다른 프로세스 보호, 초기화·백업·복구 |
| 문서 | 링크·앵커·출처·탐색·ERD·보존 범위 |

작은 문구 수정마다 전체 기능을 흉내 내는 새 테스트를 작성할 필요는 없다. 동작·권한·저장 정책을 바꾸면 필요한 회귀 사례를 확인한다. 관련 실패를 해결한 뒤 범위를 넓히며, 고정 평가 정답을 기대값에 맞춰 고치지 않는다.

## 자주 만나는 실패

| 증상 | 확인과 대응 |
| --- | --- |
| npm.ps1 실행 정책 오류 | `npm.cmd` 사용. 시스템 실행 정책을 무작정 낮추지 않음 |
| 모듈을 못 찾음 | backend/.venv의 Python 경로와 requirements 설치 확인 |
| pytest 임시 폴더 권한 오류 | 현재 사용자에게 쓰기 가능한 TEMP/TMP 사용 |
| Vite realpath EPERM | 저장소·상위 폴더 권한과 도구 실행 환경 확인. 앱 코드 오류와 구분 |
| 409 기준 변경 | 최신 계약 자료 조회 후 입력·원문 동의 다시 확인 |
| 서버 변경 미반영 | 대상 설정 파일로 종료→시작. 브라우저 새로고침만으로 처리하지 않음 |
| port 사용 중 | 다른 서비스를 종료하지 말고 확인 후 개발 포트 변경 |

임시 폴더 문제는 현재 터미널에서만 다음처럼 적용할 수 있다.

```powershell
$taskTestTemp=Join-Path (Get-Location) 'build/test-temp'
New-Item -ItemType Directory -Path $taskTestTemp -Force | Out-Null
$env:TEMP=$taskTestTemp
$env:TMP=$taskTestTemp
$env:TMPDIR=$taskTestTemp
& .\backend\.venv\Scripts\python.exe -X utf8 -m pytest backend/tests -q -p no:cacheprovider
```

자동 테스트의 경고도 검증 기록에 남기되 경고가 있다는 사실과 테스트 실패를 구분한다. 고객 적용은 [운영 업데이트](../operations/maintenance.md)와 [복구](recipes/recovery.md) 절차를 따른다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
