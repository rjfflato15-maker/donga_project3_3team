# 문서 유지보수와 lint

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [lint_docs.py](../../tools/docs/lint_docs.py) · [test_lint_docs.py](../../tools/docs/test_lint_docs.py)

## 하나의 내용에 하나의 기준

[문서 목록](../documentation_manifest.json)에 목적·상태·담당 내용·관련 소스를 등록한다. 현재 문서는 상태·확인일·코드 기준을 처음에 표시하고 [문서 포털](../README.md)에서 찾아갈 수 있도록 연결한다. 같은 설정·평가 수치의 사본을 늘리기보다 담당 문서에 링크한다.

현재 문서는 구현과 실행 결과를 설명한다. 초안은 미검증 계획을 완료처럼 표현하지 않는다. 과거 기록은 당시 설명을 보존한다. 고정 평가 원본·정답·예측·receipt는 문서 정리로 바꾸지 않는다. 포털에서 네 분류를 나누되 원본 디렉터리를 일괄 이동하지 않는다.

## 수정할 때

1. 바뀐 기능의 담당 문서와 관련 소스를 찾는다.
2. 소스 경로·명령 실행 위치·응답·실제 동작을 확인한다.
3. 설명과 관련 링크를 고친다. 새 문서는 manifest와 포털에 등록한다.
4. 검증 결과와 확인일을 갱신한다. HEAD와 작업 트리 변경을 구분한다.
5. lint와 관련 기능 검증을 실행하고 보존 대상을 비교한다.

```powershell
& .\backend\.venv\Scripts\python.exe tools/docs/lint_docs.py
& .\backend\.venv\Scripts\python.exe tools/docs/lint_docs.py --all --report build/docs-lint.json
& .\backend\.venv\Scripts\python.exe -m unittest tools.docs.test_lint_docs -v
```

기본 검사는 유지보수 대상 문서의 로컬 링크·앵커·참조 링크, 메타데이터, 관련 소스 존재, 포털 연결, 기준 내용의 중복 담당, 선택한 코드 기준과 ERD 일치를 검사한다. 코드를 import하지 않고 DB 모델 선언을 AST로 읽는다. 외부 웹 주소의 생존 여부와 문장의 의미는 자동 검사 대상에 포함되지 않는다. 문서 속 셸 명령을 자동 실행하지 않는다.

`--all`은 보존 문서·참고 자료의 링크 문제를 별도 보고한다. 현재 문서 오류는 종료 코드 1이며 과거 기록 문제는 참고 결과로 구분한다. 과거 깨진 링크를 숨기거나 현재 검사 성공을 전체 역사 문서 무결성으로 표현하지 않는다.

이 저장소의 Git 루트는 `3조 색인`, 앱 루트는 그 아래 `3.project`다. manifest의 workspace_root_is_parent는 상위 README와 앱 문서 사이의 링크를 검사하기 위한 명시적 범위다. 다른 저장소 구조로 옮기면 문서 경로·검사 범위도 함께 확인한다.

## ERD 갱신

DB 변경 뒤 아래 Python 출력을 [현재 ERD](../architecture/erd.md)의 기존 Mermaid 블록과 비교해 갱신한다. 자동 생성 범위는 Column과 명시 ForeignKey다. JSON 내부 참조·복합 제약·이주 정책은 별도 설명을 확인한다.

```powershell
& .\backend\.venv\Scripts\python.exe -c "from tools.docs.lint_docs import ROOT,erd_block; print(erd_block(ROOT))"
```

문서 lint는 문서와 소스의 정적 연결을 검사하며 실행 동작이나 배포 안정성을 보증하지 않는다. [관련 검증](test_and_verification.md)과 실제 읽기·작업 예시를 함께 확인한다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
