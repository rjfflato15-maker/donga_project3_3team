# 공통 상태·처리 이력·검색 API

2026-10-05 제품 기반 보강. 기존 추출/가드/평가 스키마와 권한을 유지하고 운영 응답만 확장한다. frontend 담당자는 기존 UX 4건과 함께 연결한다.

## 공통 상태

계약 목록·상세·`GET /api/contracts/{id}/review-context`에 같은 `stage`, `work_state`를 추가했다. 별도 `GET /api/contracts/{id}/work-state?revision=...&fingerprint=...`도 제공한다. 목록의 `fingerprint`, `registered_by_user_id`도 추가 필드다. 전체 예시:

```json
{
  "schema_version": 1,
  "stage": "WAITING",
  "stage_label": "보완",
  "revision": 4,
  "fingerprint": "<current fingerprint>",
  "approval_status": "PENDING",
  "approval_next_step": 1,
  "counts": {
    "check_items": 2,
    "issue_cards": 2,
    "missing_document_types": 2,
    "missing_external_document_types": 1,
    "waiting_requests": 1,
    "pending_ai_documents": 0,
    "immediate_check_items": 1
  },
  "next_actions": [
    {"role": "operator", "code": "REVIEW_CURRENT_EVIDENCE", "label": "현재 서류와 남은 확인 항목 처리"}
  ],
  "waiting_for": ["VENDOR"],
  "payment_already_recorded": false,
  "rule_results_are_human_confirmation": false,
  "basis": "CURRENT_SAVED_FIELDS_AND_CURRENT_REVIEW"
}
```

`stage`는 기존 5단계+끝과 호환한다. 현재 지급 연결이 유효하고 현재 결재가 CONFIRMED이면 DONE, 결재 CONFIRMED이면 PAYMENT, 회신 대기가 있으면 WAITING, 외부 누락이 있으면 RECEIVING, 미확인/판독/반려이면 CHECK, 그 밖은 APPROVAL이다. 검수확인서 누락은 사내 확인으로 취급한다. STALE이더라도 새 현재값 자동 검사가 끝나고 남은 항목이 없으면 APPROVAL이며 **이전 결재가 유효해졌다는 뜻은 아니다**.

`next_actions`는 현재 역할이 할 수 있는 행동이다. 2단계 결재의 실제 next step이 담당자면 operator, 대표면 representative다. 회사 전체 역할의 업무이며 특정 개인에게 맡겨진 업무로 표현하지 않는다. 개인에게 맡긴 업무는 기존 assignment API/검색 assignee 필터를 사용한다.

거래처에 이미 요청한 MISSING/FAIL은 `immediate_check_items`에서 제외하고 대기에 남긴다. 같은 문서의 REVIEW는 사내 확인으로 남긴다. 과거 자유 메모 요청은 항목 매핑이 없어 즉시 확인 수에서 추정 제외하지 않는다. 대기와 직접 확인이 동시에 있으면 둘 다 표시한다. `waiting_requests`는 요청 묶음 수이며 서류 항목 수는 기존 bundle.counts를 쓴다.

자동 검사 통과를 ‘담당자 원문 확인 완료’로 바꾸지 않는다. 실제 필드 확인자는 provenance.human_confirmation, 실제 담당 결재는 approval.history에 있다. 새 표시용 메타데이터는 fingerprint 입력에 넣지 않아 기존 결재·지급이 표시 개선만으로 STALE이 되지 않는다.

지급 재확인이 막혔다면 `payment_blocked_reason`을 표시한다. 원본 해시 확인 불가의 다음 행동은 RESTORE_ORIGINAL, 거래처/금액 변경은 REVIEW_CHANGED_PAYMENT_SCOPE다. 실제로 재확인할 수 있는 경우만 RECONFIRM_PAYMENT로 안내한다. 기존 지급 사실을 또 지급하라는 뜻으로 바꾸지 않는다.

## 처리 이력

`GET /api/contracts/{id}/activity?limit=50&before_event_id=123&masked=true&revision=4&fingerprint=...`

```json
{
  "contract_id": 7,
  "revision": 4,
  "fingerprint": "<current fingerprint>",
  "order": "EVENT_ID_DESC",
  "masked": true,
  "items": [{
    "event_id": 122,
    "type": "DOCUMENT_REISSUED",
    "title": "고친 본 등록",
    "occurred_at": "2026-10-05T07:10:00+00:00",
    "actor_id": 2,
    "actor_name": "담당자",
    "document_id": 18,
    "revision": 4,
    "request_id": null,
    "review_id": null,
    "details_available": true,
    "data": {
      "previous_document_id": 11,
      "logical_document_id": 11,
      "version_number": 3,
      "revision": 4,
      "note": "합계를 다시 발행한 자료로 교체",
      "previous_fields": {"total_amount": 1650000},
      "new_fields": {"total_amount": 1540000}
    }
  }],
  "has_more": true,
  "next_before_event_id": 122,
  "recorded_facts_only": true,
  "limitations": ["과거에 기록되지 않은 사실은 추정해서 채우지 않습니다.", "자동 검사 기록은 원문 사람 확인이나 국세청 진위 조회를 뜻하지 않습니다."]
}
```

최신 기록부터 반환한다. 다음 페이지는 `next_before_event_id`를 그대로 전송하며 event_id로 중복을 제거한다. timestamp는 UTC이고 화면은 한국 시간으로 표시한다. 계약 전환/새 조회 세대/자료 기준 변경 시 이전 응답을 버린다.

등록→검사→요청→항목 수령/취소→읽은 값 정정→재발행→재검사→담당 결재→대표 결재/반려→지급 기록을 기존 audit 사건에서 읽는다. 보기/다운로드/로그인 등은 업무 이력 목록에서 제외한다. 이벤트 기록 시각 순이며 과거 업무 사실을 추정해 재배열하지 않는다. RULE_VALIDATION의 `data.checks`는 **그 당시 저장한 검사 snapshot**이다. DOCUMENT_REISSUED의 전후 값은 그 재발행 순간의 저장값 snapshot이며 나중의 필드 수정과 섞지 않는다.

이번부터 새 묶음 요청 기록에는 사유·대상·기한·메모, 회신/취소에는 항목 제목·사유·상태가 보존된다. 대표 사건은 review_id로 `/api/pilot/reviews/{review_id}` 당시 결재 snapshot에 연결한다. 과거 사건에 없는 revision/전후 값/review_id는 null 또는 생략 상태를 유지한다. `details_available=false`이면 상세 기록을 읽을 수 없다는 뜻이다. 현재 요청/문서 정보로 과거 사건을 덮어 쓰지 않는다.

재발행 시 과거 추출 메타데이터를 읽을 수 없으면 previous_fields=null로 보존한다. 기록 보강 때문에 정상 새 원문의 재발행을 막거나 이전 금액을 0원으로 만들지 않는다.

`masked=true`가 기본이며 전후 상호·번호·사유·메모의 개인정보를 재귀 가린다. 현재 값뿐 아니라 같은 계약의 다른 페이지/이전본/과거 수정의 민감값도 가린다. fingerprint와 SHA 등 식별 해시는 유지하고 내부 경로·prompt·response·idempotency_key 등은 노출하지 않는다. masked=false는 기존 회사 원본 접근 권한 안에서만 사용한다.

## 과거 계약 찾기

`GET /api/contracts/search?q=새봄&completion=OPEN&stage=WAITING&date_from=2026-10-01&date_to=2026-10-31&limit=50&offset=0`

```json
{
  "items": [],
  "total": 0,
  "limit": 50,
  "offset": 0,
  "date_basis": "CONTRACT_CREATED_AT_ASIA_SEOUL",
  "id_search_basis": "INTERNAL_CONTRACT_ID",
  "assignee_filter_basis": "ACTIVE_WORK_ASSIGNMENT",
  "registered_by_filter_basis": "CONTRACT_REGISTRANT"
}
```

items는 기존 목록 객체+공통 상태다. 계약명·거래처·앱 계약 ID를 검색하고, 숫자/쉼표/원/공백만인 입력이면 금액도 검색한다. `%`와 `_`는 와일드카드가 아닌 일반 문자다. 계약 ID를 원문에 있는 계약번호라고 표현하지 않는다.

completion은 ALL/OPEN/DONE, stage는 공통 6값이다. DONE은 대표 결재만 끝난 상태가 아니라 유효한 전체 지급 완료 기록까지 있는 상태다. `registered_by_user_id`는 계약 등록자, `assignee_id`는 OPEN/IN_PROGRESS 맡기기가 있는 사람이다. 담당자가 바뀌었다고 등록자까지 바꾸지 않는다. 기간은 **계약 최초 등록일의 한국 날짜**이며 양 끝 날짜를 포함한다. 완료일·회신일 검색이라고 표시하지 않는다. limit은 1~200, offset은 0 이상. 최신 앱 계약 ID 순으로 반환한다.

검색은 현재 회사의 기존 접근 권한 범위다. 새로운 개인별 결재 권한이나 외부 공유 기능을 만들지 않는다. 현재 버전은 시범 업무함 크기에 맞춰 SQL로 먼저 이름/기간/담당 범위를 좁히고 현재 규칙 결과의 상태를 계산한다. 검색을 위해 추출·OCR·LLM·검사 저장을 재실행하지 않는다.

## 오류·기준 변경 규칙

| 상태 | 의미와 화면 처리 |
| --- | --- |
| 401/403 | 기존 회사 인증/권한 조건. 로그인/권한 안내 |
| 404 | 없는 계약. 이전 화면 자료를 남기지 않고 목록으로 안내 |
| 409 | revision/fingerprint 불일치 또는 조회 중 자료 변경. 오래된 입력·동의로 저장하지 않고 다시 조회 |
| 422 | 단계/기간/페이지 범위 오류. 입력 수정 안내 |

JSON 오류는 기존 FastAPI `{"detail":"..."}` 형식이다. 이력·공통 상태는 필요하면 revision과 fingerprint를 함께 보내 기준을 고정한다. 성공 응답의 revision/fingerprint가 현재 화면과 다르면 그 응답을 버린다. 검색은 계약별 응답에 기준이 있으며 회사 전체를 하나의 동시 snapshot으로 보장하는 API는 아니다.
