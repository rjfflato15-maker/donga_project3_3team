# 화요일 자료 준비·초기화 — 진행자용

자료 버전은 **team-test-dev-v1**, 앱 조건은 **규칙만 / LLM 꺼짐 / 캐시 없음 / NTS disabled**다.
[자료 폴더](../../sample-data/team-test-dev-v1/README.md)의 참가자 ZIP 5개를 사용한다.
이 문서·정답표·검증 결과는 참가자에게 배포하지 않는다.

## 만든 자료와 확인 결과

| 참가자 이름 | 초기 원문 | 실제 앱 검수 결과 | 회신 반영 후 |
| --- | --- | --- | --- |
| 연습 | 6종 | 추가 문제 0건 | 측정 제외 |
| 과제 1 · A | 5종 | 통장사본 MISSING 1건만 | 회신 대기 기록까지 |
| 과제 1 · B | 5종 | 통장사본 MISSING 1건만 | 회신 대기 기록까지 |
| 과제 2 · A | 6종 | 견적 3,520,000원 / 등록 3,410,000원 차이 1건만 | 3,410,000원 수정본 → 차이 0건 |
| 과제 2 · B | 6종 | 견적 3,740,000원 / 등록 3,630,000원 차이 1건만 | 3,630,000원 수정본 → 차이 0건 |

모든 경우 NTS 미연동 BUSINESS_STATUS REVIEW는 별도 안내로 남아 있다. 위 ‘문제’ 수에서만 제외했으며 판정 로직은 변경하지 않았다.
재발행 두 건 모두 이전본 보존·새 현재본·이전 문서 연결을 확인했다. 자동 결재를 검증했다는 뜻은 아니다.

원문 28개 + 수정 견적서 2개 + 등록 정보표 5개 = **PDF 35개, 각 1쪽**.
35쪽을 Poppler로 렌더링해 글자 잘림·깨짐 없이 AI가 육안 확인했다. 사람 전수 확인으로 기록하지 않는다.
실제 업로드 파이프라인·규칙 검수 서비스에서 원문 28개와 수정본 2개를 처리했다.
검증 근거: [실행 결과 JSON](team_test_materials_verification.json). 모델·가드 실행, 외부 접속, 보호 자료 접근 시도 모두 0건.
이번 결과는 자료의 의도 확인이며 새로운 판독 정확도 평가나 시간 절감 실측값이 아니다.

## 배포와 안내문 일치

- [참가자 안내 사본](../../sample-data/team-test-dev-v1/participant_guide.md)은 `feat/ui-polish`의 `681df4f` 시점 안내와 과제 이름·절차가 같다. 진행자 체크·진행자 문서 링크만 배포본에서 제외했다. UI 브랜치 원문은 수정하지 않았다.
- `packages/`에서 현재 배정된 ZIP 하나만 전달한다. A/B 전체·진행자 폴더는 공개하지 않는다. 파일명은 연속 `document_01.pdf` 형식으로 문제 종류·누락 번호 힌트를 넣지 않았다.
- 과제마다 등록 금액·공급자 사업자번호 정보표(PDF/JSON), 같은 업무 기준표, 빈 CSV 기록표를 제공한다. 앱에서도 `originals/`만 업로드한다.
- [진행자 정답표](../../sample-data/team-test-dev-v1/facilitator/answers.md)와 수정본은 `facilitator/`에만 있다. 과제 2에서 올바른 요청을 받으면 해당 `replies/task_2_A` 또는 `task_2_B` 파일을 즉시 준다.
- 연락 방법 카카오톡, 회신 기한 10/8을 양쪽 방식에 동일 적용한다. 실제 연락은 하지 않는다. 진행자는 [빈 시간 기록표](../../sample-data/team-test-dev-v1/facilitator/timing_record.csv)를 사용한다.
- 안내의 ‘약 50분’은 표 합계로는 최대 55분이다. 진행 일정은 55분 여유를 두고, 과제별 상한은 그대로 10분이다. 병합 전 안내 담당자가 제목 시간을 맞추면 된다.

## 과제별 빈 업무함 만들기

프로젝트 `3.project` 폴더에서 실행한다. 저장 경로는 `storage/demo/team-test/` 아래의 **새 이름**만 허용한다.

```powershell
# 연습용 / 다음 참가자의 과제 1 A / 과제 2 B 예시
backend/.venv/Scripts/python.exe backend/scripts/prepare_team_test_inbox.py --case practice --output storage/demo/team-test/p01-practice --intranet
backend/.venv/Scripts/python.exe backend/scripts/prepare_team_test_inbox.py --case task_1_A --output storage/demo/team-test/p01-task1-app --intranet
backend/.venv/Scripts/python.exe backend/scripts/prepare_team_test_inbox.py --case task_2_B --output storage/demo/team-test/p01-task2-app --intranet
```

선택값은 `practice`, `task_1_A`, `task_1_B`, `task_2_A`, `task_2_B`다. 기본 포트는 8030이다.
**등록 계약 1건·업로드 0개·요청/수정/결재 이력 없는 상태**로 만든다. 업로드와 분석 대기도 시간에 포함하기 위해서다.
`storage/demo/team-test/practice-ready/`는 이미 준비했으며 서버는 아직 시작하지 않았다.

1. 앞 과제가 끝나면 그 업무함의 `stop.bat`으로 종료한다. 실제 업무 서버는 종료하지 않는다.
2. 위 명령으로 새 폴더를 만든다. 같은 이름 재사용은 오류로 중단하며 기존 DB·기록을 지우지 않는다.
3. 새 폴더의 `start.bat`으로 실행한다. `http://127.0.0.1:8030/` 또는 [사내망 접속 안내](team_test_network.md)의 서버 IP로 접속한다.
4. `storage/initial-accounts.txt`에서 담당자 `operator@team.local`, 대표 `representative@team.local`의 임시 비밀번호를 확인한다. 로그인·비밀번호 변경을 **타이머 시작 전에** 끝낸다. 비밀번호는 문서·Git·팀 공유 파일에 넣지 않는다.
5. 계약 상세의 빈 업로드 구역까지 준비하되 원문은 타이머 시작과 함께 전달한다. 다른 업무함 로그인 쿠키가 섞이지 않도록 별도 브라우저 프로필을 쓰거나 새 업무함 전환 때 로그아웃한다.
6. 종료 뒤 기록 CSV와 해당 업무함 폴더를 보존한다. 다음 과제는 새 폴더로 반복한다. 기존 방식도 ZIP을 새 작업 폴더에 풀어 기록표·이전본 흔적이 없는 사본에서 시작한다.

자료 자체를 다시 만들 필요는 없다. 생성기 `prepare_team_test_materials.py`는 한글 폰트·ReportLab이 있는 개발용 Python에서만 사용하며 기존 자료를 덮어쓰지 않는다. 이번 생성에는 Codex 번들 Python을 사용했고 앱 의존성은 추가하지 않았다. 같은 버전으로 다른 내용을 재생성하지 않는다.

## 병합 뒤 확인할 것

10/5 병합 후 새 이름으로 아래 검증을 실행하고, 동일한 네 문제와 재발행 해소를 확인한다. **규칙만 실행**하며 모델·가드·캐시는 쓰지 않는다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/prepare_team_test_inbox.py --output storage/demo/team-test/verify-after-merge --verify
```

검증 업무함(`verification-v1-final`, `verify-after-merge`)에는 분석 결과가 있으므로 참가자 측정에 사용하지 않는다.
이후 [병합 체크리스트](team_test_merge_checklist.md)에 따라 전체 화면 확인을 마치고 측정 커밋을 고정한다.
