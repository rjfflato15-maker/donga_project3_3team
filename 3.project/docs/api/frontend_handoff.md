# Claude 화면 담당자용 API 변경 안내

## 연휴 작업 기준 (2026-10-03)

0번은 API가 아니라 [예측 보존·재채점 CLI](../eval/prediction_preservation.md)다. 현재 화면의 LLM 연결 표시를 숨기고 성과를 수정 저장 횟수·첫 등록부터 첫 대표 확인까지의 대기 포함 경과시간으로 표시하는 수정은 `8e7b2c2`에서 확인했다. 사람 확인 페이지는 `eval/human_review_page_test/index.html`의 134칸이다.

고도화 순서는 예측 보존 → dev2/test2 정답 준비 → 근거 좌표 → 명시적 재발행 버전 → 성과·LLM 상태 → 사내 맡기기 → 계약 요약 → DB를 변경하지 않는 도우미 미리보기다. 각 API를 추가할 때 JSON 예시·오류 응답·revision 규칙을 이 문서에 기록한다. 기능 동결 기준은 10/5(월) 밤, 팀원 테스트는 10/6(화)다. UI 브랜치 병합이 다른 세션의 기존 지시로 이미 진행된 경우 고도화 종료 시점에 추가 UI 커밋과 전체 흐름을 다시 확인한다.

이번 변경은 백엔드와 평가 도구에만 적용했다. `frontend/`는 수정하지 않았다. 기존 로그인 쿠키와 API 권한·Cache-Control: no-store를 그대로 사용한다. 다른 설치 환경에서 API 적용에는 백엔드 재시작이 필요하며, 시작할 때 새 운영 기록 테이블 두 개를 생성한다. 기존 DB를 덮어쓰거나 기존 필드를 바꾸는 이주는 없다. 현재 로컬 환경은 백업 후 통합 실행기로 적용하고 서버 응답과 인증 차단을 확인했다.

## 읽기 API

| 메서드·경로 | 화면에서 사용할 값 |
| --- | --- |
| GET `/api/contracts` | 기존 목록 필드 + `action_summary`, `open_issue_count`, `waiting_request_count`, `earliest_due_on`, `approval_next_step` |
| GET `/api/contracts/{id}/review-context` | `checks`, `documents`, `action_summary`, `follow_up`, `approval`, `revision`, `fingerprint` |
| GET `/api/documents/{id}/provenance` | `fields.{필드명}`의 값·출처·근거·AI 제안 사유, 원본 버전 확인 상태 |
| GET `/api/pilot/contracts/{id}/resubmission-requests` | 재제출 요청 기록 목록, 최근 기록부터 |
| GET `/api/pilot/contracts/{id}/approvals` | 결재 단계·완료 단계 수·다음 단계·1단계 검토 이력 |
| GET `/api/pilot/company-policy` | 회사 유형, 필수 서류, 역할 표시 이름, 결재 단계 |
| GET `/api/pilot/company-policy/presets` | 개인사업자·중소·중견의 선택 가능한 기본 설정 |

검사마다 `rule_id`, `status`, `expected`, `actual`, `reason`, `evidence`가 있다. `reason`은 기존 규칙 검사의 설명이다. `action_summary`는 코드가 만든 한 줄 요약이며 LLM 요약이 아니다. 기존 `/report`, 계약 상세, `/reviews`, 문서 `/fields` API도 유지한다.

### 대시보드 계약 목록

기존 `/api/contracts`의 배열 구조·필드·정렬 순서를 유지한다. 한 줄 요약은 `review-context`와 같은 함수로 만들며, 목록 조회에는 상세 원문 읽기·OCR·LLM 호출이 추가되지 않는다.

| 추가 필드 | 반환 기준 |
| --- | --- |
| `action_summary` | 결재 상태·회신 대기·검사 상태·AI 확인 필요를 반영한 한 줄 문장 |
| `open_issue_count` | FAIL + MISSING + REVIEW 검사 수. NTS disabled의 BUSINESS_STATUS REVIEW는 제외. 없으면 `0` |
| `waiting_request_count` | `WAITING_RESPONSE` 요청 수. 없으면 `0` |
| `earliest_due_on` | 대기 요청 중 기한이 있는 요청의 최솟값(`YYYY-MM-DD`). 없으면 `null` |
| `approval_next_step` | 현재 자료에서 다음 결재 단계 `1` 또는 `2`. 최종 확인 완료면 `null` |

회신 완료·취소된 요청은 건수와 기한에서 제외한다. 기한을 넘긴 미회신 요청도 대기 건수에 남는다. 자료 변경·반려로 이전 결재가 무효가 되면 다시 필요한 단계가 표시된다. 회신 대기 건수·기한은 목록 전체를 한 번에 집계하며 결재 이력과 원문 근거를 목록 응답에 싣지 않는다.

목록·상세 `review-context`의 두 `action_summary` 모두 NTS 미연동 알림을 “미확인 N건”에 세지 않는다. `open_issue_count`에도 같은 기준을 쓴다. 상세 `checks`, 원래 `summary`와 `review_status`, 검사·평가 판정은 그대로이므로 미연동이 PASS로 바뀐 것은 아니다. API 조회 실패·데모 조회의 REVIEW와 BUSINESS_STATUS FAIL, 다른 REVIEW는 제외하지 않는다. 회신 대기·결재·AI 추가 확인 문서 수는 `open_issue_count`에 더하지 않고 각각 표시한다.

```json
{
  "action_summary": "2단계 결재 대기 · 회신 대기 2건 · 미확인 1건",
  "open_issue_count": 1,
  "waiting_request_count": 2,
  "earliest_due_on": "2026-10-05",
  "approval_next_step": 2
}
```

### 서류 출처와 근거

필드의 `source`는 `RULE`, `AI_SUPPLEMENT`, `HUMAN_CONFIRMATION`, `UNAVAILABLE`이다. `ai_decision`에는 제안값과 `accepted`, `applied`, `reasons`, `warnings`, 원래 근거가 남는다. 거부된 AI 제안은 현재 채택값과 구분해 표시한다. `original_source`는 사람 확인 이전의 규칙/AI 출처다. 사람 확인은 기존 수동 필드 확인 API의 기록이며 대표의 계약 최종 결재와 구분한다.

`evidence`는 문서 ID·필드·페이지·줄·문구·문자 위치를 담는다. PDF/PNG 페이지와 줄은 1부터 센다. 기존 이미지 미리보기 API의 `page` 쿼리는 0부터 시작하므로 `page-1`로 연결한다. DOCX는 `page=null`이며 문단·표 위치와 `page_layout_verified=false`를 제공한다. TXT는 물리 페이지를 만들지 않고 `location_kind=text_line`, `page=null`로 글자 위치만 제공한다.

원문 또는 라벨을 확인하지 못하면 근거 배열이 비고 `evidence_status=UNAVAILABLE`이다. 후보가 여러 개면 `AMBIGUOUS`다. 없는 페이지·문구를 표시하지 않는다. 파일 해시가 달라지면 `ORIGINAL_VERSION_CHANGED`로 현재 근거를 제공하지 않는다. 근거 읽기에는 LLM을 호출하지 않으며 원문 OCR의 오독까지 해결한 것은 아니다. 사용자 메모와 근거 문구는 화면에서 HTML로 실행하지 말고 텍스트로 표시한다.

## 재제출 요청 기록

POST `/api/pilot/contracts/{id}/resubmission-requests`는 담당자·대표가 **실제로 연락한 내역을 기록**하는 API다. 카카오톡·문자·이메일을 발송하지 않는다.

```json
{
  "contact_method": "KAKAO",
  "requested_on": "2026-10-02",
  "due_on": "2026-10-05",
  "memo": "통장사본 보완 요청을 전달함"
}
```

연락 방법은 `KAKAO`/`SMS`/`EMAIL`/`PHONE`/`OTHER`다. 요청일은 생략하면 한국 날짜로 기록하며 기한은 선택이다. 메모는 1~2,000자다. 생성하면 `WAITING_RESPONSE`가 되고 계약의 `follow_up`와 한 줄 요약에 회신 대기가 표시된다. 검수 PASS/FAIL 및 기존 결재 상태와는 별도 상태다.

회신 수신 또는 취소는 PATCH `/api/pilot/contracts/{id}/resubmission-requests/{request_id}`에 아래 값을 보낸다. 이력은 삭제하지 않는다. 파일을 새로 올렸다는 이유만으로 모든 요청을 회신 완료 처리하지 않는다.

```json
{"status":"RECEIVED","note":"보완 서류 회신을 확인함"}
```

`status`는 `RECEIVED` 또는 `CANCELLED`다. 이미 종료한 요청을 다시 종료하면 409, 다른 계약의 요청 ID면 404다. 대표가 반려하는 기존 `/reviews`의 `RETURNED` 기록과 연락 내역은 각각 보존한다.

## 회사 설정과 결재

PUT `/api/pilot/company-policy`는 대표만 사용할 수 있다. GET 응답 또는 presets의 한 항목을 수정해 보낸다. `company_type`은 `SOLE_PROPRIETOR`/`SMALL_BUSINESS`/`MID_SIZED`다. 필수 서류는 법정 기준을 자동 판단하지 않고 회사가 선택한다. 기본값은 기존 여섯 종류다.

`roles`는 기존 담당자(`operator`)·대표(`representative`)의 표시 이름이다. 권한 종류를 임의로 늘리지는 않는다. `approval_steps`는 1~2개이며 마지막 역할은 대표다. 중견 기본값은 담당 검토→대표 결재이고 다른 유형은 대표 1단계다. 회사 규모와 무관하게 허용 범위에서 변경할 수 있다. 설정이 바뀌면 기존 계약 revision이 증가해 이전 확인·결재를 그대로 재사용하지 않는다. 기존 PUT `/api/pilot/settings`의 필수 서류 설정과도 같은 값을 사용한다.

POST `/api/pilot/contracts/{id}/approvals` 요청은 기존 최종 확인 요청에 `step`을 더한다.

```json
{
  "step": 1,
  "decision": "CONFIRMED",
  "revision": 3,
  "fingerprint": "review-context에서 받은 최신 값",
  "note": "미확인 항목을 원문과 등록 기준으로 직접 검토함",
  "acknowledge_unverified": true
}
```

2단계 설정에서는 1단계 기록이 있어야 최종 결재가 가능하며 같은 사람이 두 단계를 처리할 수 없다. 기존 `/reviews`로도 이 조건을 건너뛸 수 없다. 자료 변경·반려 후에는 현재 자료를 1단계부터 다시 검토한다. 누락 서류·원본은 먼저 보완해야 하고, 불일치·미확인 항목이 있으면 명시적인 확인과 10자 이상의 근거가 필요하다. revision/fingerprint가 오래되면 409로 최신 자료를 다시 요청한다.

[진행 요약](../progress/development_report.md) · [소스 담당 영역](../architecture/module_map.md)
