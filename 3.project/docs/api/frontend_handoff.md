# Claude 화면 담당자용 API 변경 안내

## 연휴 작업 기준 (2026-10-03)

0번은 API가 아니라 [예측 보존·재채점 CLI](../eval/prediction_preservation.md)다. 현재 화면에서 LLM 연결 표시를 숨기고 성과를 수정 저장 횟수·첫 등록부터 첫 대표 확인까지의 대기 포함 경과시간으로 바꾼 수정은 `8e7b2c2`에서 확인했다. 기존 test 134칸과 test2 81칸의 사람 확인은 완료했다. test2의 질문 문구 오류 1칸은 실제 지적을 보존하고 REVIEW로 기록했다. [출처와 절차](../eval/test2/preparation/README.md)를 참고한다.

고도화 순서는 예측 보존 → dev2/test2 정답 준비 → 근거 좌표 → 명시적 재발행 버전 → 성과·LLM 상태 → 사내 맡기기 → 계약 요약 → DB를 변경하지 않는 도우미 미리보기다. 각 API를 추가할 때 JSON 예시·오류 응답·revision 규칙을 이 문서에 기록한다. 기능 동결 기준은 10/5(월) 밤, 팀원 테스트는 10/6(화)다. UI 브랜치 병합이 다른 세션의 기존 지시로 이미 진행된 경우 고도화 종료 시점에 추가 UI 커밋과 전체 흐름을 다시 확인한다.

이번 변경은 백엔드와 평가 도구에 적용했다. 기존 로그인 쿠키와 API 권한·Cache-Control: no-store를 사용한다. API 적용에는 백엔드 재시작이 필요하며, 시작할 때 서류 버전·사내 맡기기·업로드 작업을 포함한 새 운영 기록 테이블을 생성한다. 기존 DB를 덮어쓰거나 기존 필드를 바꾸는 이주는 없다. 새 화면 연결은 Claude 담당이며, 아래 API 테스트 통과와 전체 새 화면 시연 완료를 구분한다.

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
## 근거 좌표 (2026-10-03)

`GET /api/documents/{document_id}/provenance`와 `GET /api/contracts/{contract_id}/review-context`의 evidence에 실제 OCR 단어 상자 또는 PDF 글자 상자를 추가했다. 원본 SHA256을 확인한 뒤에만 좌표를 붙인다. EXIF 방향을 적용한 preview-image의 왼쪽 위가 원점이며 x/y/width/height는 0~1 비율이다. `bbox`는 해당 인용의 외접 상자, `bboxes`는 실제 글자/단어별 상자다. 다중 상자 지원 시 bboxes를 각각 그리면 된다. 좌표 확인 실패·반복 인용·회전된 native PDF·DOCX/TXT는 bbox=null, bboxes=[]로 유지한다.

```json
{"page": 1, "line": 6, "quote": "합계금액: 1100원", "bbox": {"page": 1, "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05}, "bboxes": [{"page": 1, "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05}], "coordinate_space": "preview_image_normalized_top_left", "coordinate_method": "OCR_WORD_BOXES", "source_sha256": "원본의 64자리 SHA256"}
```

evidence.page는 1부터 시작하고 preview-image의 page query는 0부터 시작한다. `GET /api/documents/42/preview-image?page=0&masked=false&revision=7&source_sha256=...`로 같은 근거의 이미지를 요청한다. revision 또는 원본 해시가 다르면 `409 {"detail":"계약 자료가 변경되었습니다. 근거와 미리보기를 새로 불러오세요."}`(원본 충돌도 같은 409), 해당 페이지가 없으면 404, 이미지/마스킹 실패는 503이다. 로그인은 필수(401)다. null일 때 기존 쪽·줄 표시를 사용한다. 이 API는 계약 revision을 증가시키지 않는다.
## 추가 등록과 재발행 버전 (2026-10-03)

기존 `POST /api/contracts/{id}/documents`의 multipart `upload_mode` 기본값은 ADD다. 같은 종류 문서도 서로 독립된 증빙으로 추가한다. 분할 세금계산서 추가는 ADD를 사용한다. 재발행은 파일 한 개와 `upload_mode=REISSUE`, `replaces_document_id=42`, `revision=7`, `change_note=금액 정정 재발행`을 보낸다. 문서 종류는 교체 대상과 같아야 하며 생략하면 이전 종류를 사용한다. 담당자 권한만 등록할 수 있다.

```json
[{"document_id": 45, "contract_id": 3, "version": {"logical_document_id": 42, "version_number": 2, "is_current": true, "previous_document_id": 42}}]
```

응답은 기존 DocumentResponse 배열이며 위 version 필드가 추가된다. 성공 시 계약 revision이 증가하고 이전 확인·1차 결재·최종 결재가 현재 자료에 적용되지 않는다. 새 문서는 이전 사람 확인 상태를 이어받지 않는다. 최신 상세를 다시 불러온 다음 근거 확인과 재결재를 진행한다. 이전 원문·추출값·수정 기록은 보관하고 검수/목록 완성률/결재 자료에서 제외한다. 이전 문서는 직접 GET/다운로드 가능하다. 버전 이력이 있는 문서의 DELETE나 이전 버전 값 수정은 409로 보호한다.

`GET /api/documents/45/versions`:

```json
{"contract_id": 3, "revision": 8, "versions": [{"document_id":42,"logical_document_id":42,"version_number":1,"is_current":false,"previous_document_id":null,"file_name":"원본.pdf","fields":{"total_amount":111},"source_sha256":"...","change_note":"새 증빙 추가"},{"document_id":45,"logical_document_id":42,"version_number":2,"is_current":true,"previous_document_id":42,"file_name":"재발행.pdf","fields":{"total_amount":110},"source_sha256":"...","change_note":"금액 정정 재발행"}]}
```

`GET /api/documents/45/compare`는 바로 이전 버전과 비교한다. `?previous_document_id=42`로 더 이전 버전을 지정할 수 있다. comparison_basis=CURRENT_SAVED_FIELDS이므로 각 버전에 마지막으로 저장된 사람 수정값도 반영된다.

```json
{"contract_id":3,"revision":8,"logical_document_id":42,"previous_document_id":42,"new_document_id":45,"previous_version":1,"new_version":2,"comparison_basis":"CURRENT_SAVED_FIELDS","changed_field_count":1,"changes":[{"field":"total_amount","previous_value":111,"new_value":110}],"previous_fields":{"total_amount":111},"new_fields":{"total_amount":110}}
```

예시의 fields는 일부만 표기했다. 실제로 모든 AnalysisFields를 반환한다. 읽기 API는 revision을 바꾸지 않는다. 등록 조건 누락/다른 종류는 400, 대상 없음/다른 계약 문서/비교 불가 대상은 404, 오래된 revision·이미 교체된 문서는 `409 {"detail":"분석 중 계약 자료가 변경되었습니다. 새로고침 후 다시 등록하세요."}` 등 충돌 사유를 반환한다. 재발행 OCR 실패는 `422 {"detail":"재발행본을 읽지 못했습니다. 이전 버전은 유지됩니다. 파일을 확인하세요."}`다. 실패 시 이전 활성 문서·값·revision·결재가 그대로 유지된다. 분석은 DB 게시 잠금 밖에서 실행하고 게시 직전에 revision을 다시 검사한다. 기존 자료에 버전 행이 없어도 버전 1로 읽으며 재발행 시 이력을 생성한다. 새 DB 테이블만 추가해 기존 DB를 재생성하지 않는다.
## 성과 수치와 LLM 상태 (2026-10-03)

`GET /api/pilot/performance` 또는 `?contract_id=3`은 다음과 같이 실제 기록만 반환한다. active_review_seconds와 measured_time_saving_seconds는 아직 측정하지 않아 null이다. 사람 수정은 before/after 값 차이를 센다. 같은 값 저장은 저장 횟수 1회, 바뀐 칸 0개다. field_edit_count는 수정마다 바뀐 칸의 합계, unique_field_count는 문서·필드별 중복을 뺀 칸 수다. 이전 버전의 사람 수정도 계약 이력에 포함한다.

```json
{"timing_basis":"계약 등록 → 현재 자료의 최종 대표 확인, 대기 포함","active_work_time_measured":false,"time_savings_measured":false,"contracts":[{"contract_id":3,"revision":8,"approval_status":"CONFIRMED","registration_to_current_final_confirmation_elapsed_seconds":1200,"resubmission_request_count":2,"human_correction_save_count":3,"human_field_edit_count":2,"human_changed_unique_field_count":1,"unknown_correction_event_count":0,"ai_applied_value_field_count":4,"ai_current_matching_value_field_count":3,"active_review_seconds":null,"measured_time_saving_seconds":null}],"totals":{"contract_count":1,"currently_confirmed_contract_count":1,"mean_registration_to_current_final_confirmation_elapsed_seconds":1200}}
```

재발행/기준 변경 등으로 결재가 STALE이면 현재 최종 확인 시간과 경과시간은 null이다. 재결재 전 수치를 평균에서 제외한다. 기존 `/api/pilot/metrics`는 첫 서류 → 첫 대표 확인과 수정 저장 횟수의 기존 의미를 유지한다. 서로 다른 지표의 이름을 섞지 않는다. 재제출 요청 수는 발송 기록이 아닌 앱에 등록한 요청 기록 수다. 특정 계약이 없으면 404. 모든 읽기 API는 revision을 증가시키지 않는다.

`GET /api/pilot/llm-status`는 현재 설정과 로컬 `/api/tags` 연결을 따로 반환한다. 추론을 실행하지 않는다. 상태 조회는 최대 2초 응답 제한, 30초 캐시를 사용한다. 목록/상세는 새 연결 검사를 하지 않고 최근 캐시 또는 UNCHECKED를 사용하므로 화면에서 상태 API를 먼저 호출하고 데이터를 새로 조회한다.

```json
{"configured_enabled":false,"model":"qwen3:latest","prompt_version":"grounded-fields-v3","guard_policy":"v4","cloud_disabled":true,"configuration_valid":true,"connection_state":"CONNECTED","connected":true,"model_installed":true,"ready_for_inference":false,"checked_at":"2026-10-03T01:00:00Z","error":null}
```

설정 꺼짐과 서버 연결은 함께 성립할 수 있다. connected=null은 아직 검사하지 않았다는 뜻이다. 모델 미설치 LOCAL_MODEL_NOT_INSTALLED, 서버 실패 LOCAL_SERVER_UNAVAILABLE, 잘못된 로컬 설정 INVALID_LOCAL_CONFIGURATION은 상태 JSON의 error로 반환한다. 이 조회 자체는 200이며 로그인 실패는 401이다. `/api/pilot/info`의 llm_connected는 이 실제 캐시 값(bool 또는 null)이고 llm 전체 상태도 제공한다.

계약 목록/상세의 `llm.current_state`에 위 현재 상태를 제공한다. `llm.invoked_document_count`, `known_invocation_count`, `failed_document_count`, `unknown_execution_document_count`, `applied_value_field_count`, `current_matching_ai_value_field_count`는 현재 활성 문서의 저장 결과다. 과거 AI 결과는 지금 설정을 꺼도 사라지지 않는다. known_invocation_count는 실제 추론 HTTP 시도 수(재시도 포함), 모르는 레거시는 0이라고 단정하지 않는다.

각 DocumentResponse.llm:

```json
{"configured_enabled_at_analysis":true,"status":"COMPLETED","inference_invoked":true,"invocation_count":1,"error":null,"recorded_at":"2026-10-03T01:00:00Z","applied_value_field_count":2,"current_matching_ai_value_field_count":1,"human_confirmed":true,"manual_review_required":false,"model":"qwen3:latest","prompt_version":"grounded-fields-v3","guard_version":"버전 문자열"}
```

DISABLED/NOT_NEEDED는 호출 0회, FAILED는 실패 이유와 실제 시도 수를 표시한다. 실행 기록이 없는 레거시는 UNKNOWN_LEGACY 또는 저장된 상태, 호출 여부 null일 수 있다. AI 보완 칸은 applied=true인 VALUE 제안만 세며 ABSENT/REVIEW·자동 파생 amount를 중복 집계하지 않는다. current_matching 값은 저장값이 AI 제안과 현재 같은 칸 수이며 사람이 검증했다는 뜻은 아니다. JSON 예시는 일부 필드만 표기했다.
## 사내 담당자에게 맡기기 (2026-10-03)

`GET /api/pilot/assignees`는 활성 업무 계정의 user_id/display_name/role만 반환한다. `POST /api/pilot/contracts/3/assignments`:

```json
{"assignee_id":2,"contract_revision":8,"document_id":45,"title":"재발행 견적서 금액 확인","memo":"합계와 원문 근거 확인","due_on":"2026-10-05"}
```

document_id와 due_on은 선택이다. 생성 응답(201):

```json
{"assignment_id":7,"contract_id":3,"document_id":45,"contract_revision":8,"assignment_revision":1,"assigner_id":1,"assigner_name":"담당자 김","assignee_id":2,"assignee_name":"담당자 이","title":"재발행 견적서 금액 확인","memo":"합계와 원문 근거 확인","due_on":"2026-10-05","status":"OPEN","is_stale":false,"overdue":false,"created_at":"2026-10-03T01:00:00Z","updated_at":"2026-10-03T01:00:00Z","completed_at":null}
```

`GET /api/pilot/contracts/3/assignments`는 계약 업무 전체와 contract_revision, `GET /api/pilot/assignments/mine`은 로그인한 사람의 OPEN/IN_PROGRESS만 assignments/count로 반환한다. mine은 `?include_closed=true`로 완료·취소도 볼 수 있다. 업무를 맡긴다고 계정의 자료 수정·결재 권한은 바뀌지 않는다.

`PATCH /api/pilot/contracts/3/assignments/7`:

```json
{"action":"REASSIGN","assignment_revision":1,"assignee_id":4,"contract_revision":8,"note":"담당자 변경","due_on":"2026-10-06"}
```

action은 START/COMPLETE/CANCEL/REASSIGN/UPDATE. START는 현재 맡은 사람, COMPLETE는 현재 맡은 사람 또는 대표, 재배정·취소·내용 변경은 맡긴 사람 또는 대표만 가능하다. 모든 변경은 note와 최신 assignment_revision이 필요하고 성공마다 이 값이 1 증가한다. REASSIGN은 assignee_id와 현재 contract_revision도 필수며 OPEN으로 돌아간다. UPDATE/REASSIGN은 title/memo/due_on 변경 가능, due_on=null은 기한 해제다. 완료·취소는 되돌릴 수 없고 필요하면 새 업무를 생성한다. 변경 이력은 기존 `/api/pilot/audit?contract_id=3`의 ASSIGNMENT_CREATED/ASSIGNMENT_CHANGED에 before/after/note로 남긴다.

계약 자료 revision/fingerprint가 바뀌면 is_stale=true다. 과거 자료의 업무를 START/COMPLETE하면 409다. 계약 단위 업무는 최신 자료로 재배정할 수 있고, 재발행된 이전 문서의 업무는 취소 후 새 문서에 새 업무를 맡긴다. 맡기기는 계약 revision/fingerprint와 결재 상태를 변경하지 않는다. 기한은 KST 날짜로 overdue를 계산한다. 기한을 놓쳤다고 자동 상태 변경하지 않는다.

로그인 실패 401, 권한 부족 403, 다른 계약의 업무/문서·없는 계약은 404, 오래된 assignment_revision/contract_revision·이미 종료/자료 변경은 `409 {"detail":"다른 사용자가 업무를 변경했습니다. 새로 불러오세요."}` 등 구체 사유, 비활성 담당자는 400, 스키마 누락·잘못된 action은 422다. 대표가 다른 사람의 업무를 완료해도 결재가 자동 완료되지 않는다.
## 계약 요약 문장 (2026-10-03)

`GET /api/contracts/3/summary?style=brief&revision=8`은 코드가 채운 요약이다. style은 brief/detail(기본 brief), revision은 선택이다. 등록한 기준금액과 현재 활성 서류 종류 수, 표시되는 확인 항목 수, 현재 결재 상태를 자리표시자로 넣는다. 기준이 UNKNOWN이면 부가세 포함 여부 확인 필요라고 명시한다. 같은 종류의 여러 서류는 제출 종류 수에서 중복 계산하지 않는다.

```json
{"contract_id":3,"revision":8,"fingerprint":"...","text":"가상 업체의 ‘외주 계약’ 계약입니다. 등록 기준금액은 1,100원(부가세 포함 합계)입니다. 필수 서류 6종 중 5종이 있고, 확인할 항목은 2건입니다. 결재 상태: 최종 확인 대기.","style":"brief","facts":{"vendor_name":"가상 업체","title":"외주 계약","contract_amount":"1,100","amount_basis":"부가세 포함 합계","required_document_count":"6","submitted_document_count":"5","open_issue_count":"2","approval_status":"최종 확인 대기"},"numeric_placeholders_verified":true,"llm_used":false}
```

화면에는 text를 일반 텍스트로 표시한다. facts/template/sources도 반환해 숫자 출처를 확인할 수 있다. 임의 LLM 문장 대신 검증된 코드 템플릿을 사용하며 LLM 요약은 현재 호출하지 않는다. 자리표시자 누락·중복·다른 금액을 직접 쓴 템플릿은 허용하지 않는다. 재발행 뒤에는 ‘자료 변경으로 재확인 필요’가 된다. 존재하지 않는 계약은 404, 오래된 revision 또는 생성 중 변경은 409, 잘못된 style은 422, 미로그인은 401이다. DB·검수 결과·revision을 변경하지 않는다.
## 검수 도우미 미리보기 (2026-10-03)

`POST /api/pilot/contracts/3/assistant-preview`는 저장된 현재 자료를 읽고 메모리에서 규칙을 재실행한 뒤 확인 항목별 초안을 준비한다. 실제 OCR/LLM을 새로 실행하지 않으며 DB 검수 결과·감사 로그·요청·업무·revision을 변경하지 않는다. 국세청은 DisabledNtsClient를 명시해 외부 호출이 없다.

```json
{"revision":8,"fingerprint":"현재 상세의 64자리 fingerprint"}
```

```json
{"contract_id":3,"revision":8,"fingerprint":"...","preview_only":true,"persisted":false,"automatic_send":false,"llm_used":false,"external_api_calls":0,"item_count":1,"items":[{"issue_id":"현재 항목의 안정 ID","rule_id":"REQUIRED_DOCUMENTS","field":"tax_invoice","status":"MISSING","reason":"세금계산서가 제출되지 않았습니다.","next_action":"DRAFT_REQUEST_AFTER_REVIEW","recheck":{"tool":"LOCAL_RULE_RECHECK","completed":true,"revision":8,"fingerprint":"..."},"request_draft":{"recipient_name":"가상 업체","document_type":"tax_invoice","subject":"외주 계약 · 세금계산서 확인 요청 초안","body":"가상 업체 담당자님, ... 원문을 보내 주세요.","review_before_use":true,"sent":false},"assignment_draft":null,"persisted":false}],"recheck_differences":[],"steps":[{"tool":"READ_CURRENT_STORED_EVIDENCE","status":"COMPLETED"},{"tool":"LOCAL_RULE_RECHECK","status":"COMPLETED","writes":0,"nts_mode":"disabled"},{"tool":"PREPARE_DRAFTS","status":"COMPLETED","saved":0,"sent":0}]}
```

items는 PASS 이외의 항목과 안내를 반환한다. 미연동 BUSINESS_STATUS는 `next_action=INFORMATIONAL_NOTICE`, `actionable=false`이며 request_draft/assignment_draft 모두 null이다. 이 미리보기는 항상 DisabledNtsClient를 사용한다. item_count는 안내를 포함하며 추가된 actionable_item_count는 실제 처리할 항목 수다. AMOUNT_EXTRACTION·DOCUMENT_TYPE·DOCUMENT_PROCESSING·ORIGINAL_FILE과 BUSINESS_NO_MATCH의 REVIEW는 `VERIFY_EXTRACTION_FIRST`로 원문 확인용 assignment_draft만 반환한다. 앱이 못 읽었다는 이유로 거래처 요청 초안을 만들지 않는다. 계약서·검수확인서는 사내 준비용이고, 확인 가능한 누락·차이의 견적서·세금계산서·사업자등록증·통장사본은 원문 검토 뒤 사용할 요청 초안을 준비한다.

응답의 summary는 이번 메모리 재검사 결과다. recheck_differences는 저장된 규칙 결과와 이번 결과의 차이를 보여 주며 저장하지 않는다. `issue_ids`에 이전 응답의 특정 항목 ID 배열을 주면 그 항목만 준비한다. 없는 ID는 422다. 오래된 revision/fingerprint 또는 처리 중 자료 변경은 409, 없는 계약은 404, 미로그인은 401이다. 생성된 초안은 별도 저장 버튼을 통해 기존 요청 기록/맡기기 API를 호출할 때만 저장하며, 이 API에는 저장·발송 옵션이 없다. 예시는 일부 필드만 표기했다.
## 긴 업로드의 상태 조회와 중복 없는 재시도 (2026-10-03)

기존 동기 업로드는 유지한다. 새 화면은 `POST /api/pilot/contracts/3/document-jobs` multipart로 파일 1개를 보내면 202를 받고 상태를 조회할 수 있다. 필수 필드: file, revision, idempotency_key(8~100자, 클라이언트가 파일 선택 시 생성한 UUID 권장). 선택: upload_mode=ADD/REISSUE, target_document_type, replaces_document_id, change_note. 재발행 조건은 기존 버전 API와 같다.

```json
{"job_id":"uuid","contract_id":3,"file_name":"견적서.pdf","status":"QUEUED","stage":"QUEUED","job_revision":1,"attempt_count":0,"document_id":null,"document_available":false,"document_is_current":false,"error_code":null,"error_message":null,"replayed":false}
```

`GET /api/pilot/document-jobs/{job_id}`를 약 1초 간격으로 조회한다. stage는 QUEUED → ANALYZING(OCR·추출·LLM 포함) → VALIDATING → COMPLETED 또는 FAILED다. 완료하면 document_id로 문서를 읽고 계약 상세를 갱신한다. 처리 중 같은 파일/조건/사용자의 같은 키를 다시 보내면 replayed=true로 동일 작업만 반환한다. 키에 다른 파일·조건·사용자를 넣으면 409다. 계약 revision이 바뀌어도 원래 요청 그대로의 재전송은 기존 작업을 반환한다.

실패 사유는 SOURCE_UNREADABLE(원문 인식/보관 문제), DATA_CHANGED(자료·실행권 변경), ACTOR_INACTIVE(등록 권한 변경), NOT_FOUND, PROCESSING_FAILED로 나누며 error_message에 확인 방법을 반환한다. 새 상태 조회/등록 응답에는 원문 텍스트·서버 경로·LLM 응답을 넣지 않는다. 이 새 비동기 경로는 인식에 실패한 문서를 게시하지 않는다.

`POST /api/pilot/document-jobs/{job_id}/retry`:

```json
{"job_revision":4,"contract_revision":8}
```

처음 요청한 담당자만 최신 두 revision으로 명시적으로 재시도한다. 아직 실행 중이거나 이미 완료했으면 409다. 재시도는 같은 job_id를 유지한다. 문서 게시 완료 영수증을 문서와 같은 DB 트랜잭션에 저장하므로, 게시 뒤 검수 실패/중단은 기존 document_id의 규칙 검수만 재개하고 OCR/LLM을 다시 호출하거나 새 문서를 만들지 않는다. 게시 전 실패는 같은 보관 원본으로 다시 분석한다. 서버 재시작으로 실행이 끊겼으면 10분 실행권 만료 뒤 재시도할 수 있다. 이전 작업이 늦게 돌아와도 실행권이 달라져 중복 게시하지 못한다. 자동 재시도는 하지 않는다.

상태 변경마다 job_revision이 증가한다. 계약 revision은 실제 문서 게시 때만 증가한다. 오류 스키마는 다른 API와 같이 detail이다: 미로그인 401, 담당자 권한/다른 요청자 재시도 403, 없는 작업/계약 404, 키 재사용·오래된 revision·진행/완료 중 재시도 409, 형식 검증 400/413/422. job 상태의 FAILED는 조회 200으로 원인을 보여 준다. 완료한 문서가 나중에 재발행되면 document_is_current=false이며 작업 이력은 유지한다. 동기 업로드가 반환한 결과에도 동일한 버전/LLM 메타데이터가 있다.
### v4 라벨·값이 다른 줄인 근거

v4 AI 근거가 값 줄과 라벨 줄을 연결한 경우 evidence의 값 bbox에 더해 `label_anchor.bbox`도 제공한다. 같은 원문 값을 사람이 명시적으로 확인한 뒤에도 두 위치를 유지하고 source는 HUMAN_CONFIRMATION으로 표시한다. 사람이 값을 바꿨으면 현재 값과 일치하지 않는 과거 AI 근거는 붙이지 않는다. label_anchor도 실제 쪽·줄·인용을 다시 확인한 뒤에만 좌표를 제공한다.

## 사람이 확인한 칸의 범위 (2026-10-03)

`PUT /api/documents/12/fields`는 전체 fields 또는 바뀐 칸만 받는다. 생략한 칸은 저장된 값을 유지하고, 명시한 null은 해당 값만 지운다. 실제 값이 바뀐 칸만 사람 수정으로 기록한다. 전체 폼 저장만으로 나머지 칸까지 확인 완료로 바꾸지 않는다. 원문과 비교해 같은 값이 맞음을 확인한 칸은 선택 배열 `confirmed_fields`에 넣는다.

```json
{"fields":{"total_amount":1100},"document_type":"estimate","revision":8,"note":"합계 수정, 업체명 원문 확인","confirmed_fields":["company_name"]}
```

이번에 변경된 total_amount와 명시한 company_name을 확인한 것으로 기록하고, 이전에 확인한 칸의 확인자·시각은 유지한다. 확인 버튼만 누를 때는 `fields:{}`, `confirmed_fields:["company_name"]`도 가능하다. 이 배열을 생략하는 기존 화면도 값 수정은 정상 처리한다. amount_scope는 FULL/PARTIAL/UNKNOWN이며 amount_basis의 TOTAL/SUPPLY/UNKNOWN과 구분한다.

`GET /api/documents/12/provenance`의 예:

```json
{"human_confirmed_fields":["company_name","total_amount"],"legacy_confirmation_scope_unknown":false,"fields":{"company_name":{"source":"HUMAN_CONFIRMATION","human_confirmation":{"actor_name":"담당자","at":"2026-10-03T00:00:00+00:00","value":"가상 업체","method":"EXPLICIT_CONFIRMATION"}},"total_amount":{"source":"HUMAN_CONFIRMATION","human_confirmation":{"actor_name":"담당자","at":"2026-10-03T00:00:00+00:00","value":1100,"method":"CHANGED_VALUE"}}}}
```

미확인 칸은 RULE/AI_SUPPLEMENT 등의 원래 출처와 `human_confirmation:null`을 유지한다. analysis.ai_review는 원래 호출 실패·거절 사유를 보존하면서 human_confirmed_fields / human_unconfirmed_fields를 추가한다. 아직 확인하지 않은 AI 대상이 있으면 human_confirmed=false, manual_review_required=true다. 각 decisions에도 해당 칸의 human_confirmed를 제공한다. 과거 저장의 범위를 모르면 legacy_confirmation_scope_unknown=true이며 감사 기록에서 실제 바뀐 칸만 복원한다. 문서 전체의 과거 MANUALLY_CONFIRMED 상태만으로 모든 칸을 확인했다고 표시하지 않는다.

확인 필드 이름이 없거나 중복이면 400, 잘못된 타입은 422, 오래된 계약 revision은 409, 미로그인은 401, 수정 권한이 없으면 403이다. 성공한 저장은 기존처럼 계약 revision이 1 증가하고 자료 변경에 따른 재확인·재결재 규칙을 적용한다. 값·revision·확인 범위·감사 기록은 같은 트랜잭션으로 저장한다. confirmed_fields는 앱 검수 화면에서 사용하며 평가용 사람 결과 JSON의 답을 변경하지 않는다.

## 계약 한 건 자료 묶음

`GET /api/contracts/3/export?masked=true&revision=8` → ZIP 다운로드. masked 기본 true, revision 선택(현재 상세의 값을 권장). 담당자·대표·관리자의 로그인과 회사 접근 권한을 검사한다. 화면 버튼은 Claude가 연결한다.

| ZIP 항목 | 내용 |
| --- | --- |
| documents/current, documents/previous | 현재·이전 원본 모두. 문서 ID·버전으로 중복 파일명을 구별 |
| contract.json | 등록 계약·금액 정책·문서별 필드·AI/사람 확인 기록·버전 |
| validation_results.json | 현재 저장된 검사 상태·기대값·실제값·이유. 다운로드 중 재검사 없음 |
| history.json | 요청(종료 포함), 수정 등 감사 이벤트, 대표 확인, 결재, 맡기기 및 변경 이력 |
| manifest.json | 문서 ID·버전·현재 여부·ZIP 경로·원본/내보낸 본 SHA-256·변환 방식 |
| README.txt | 묶음 구성·가림 범위·본문 TXT의 배치 미보존 안내 |

가림 ON은 PDF/이미지에 가림을 적용하고, DOCX 등은 저장된 본문을 가린 TXT로 제공한다. 원본 DOCX/PDF의 숨은 텍스트를 동봉하지 않는다. 등록 값·알려진 민감값·인식한 원문 근거로 가리며 OCR 누락까지 완전 제거한다고 주장하지 않는다. metadata와 이력의 알려진 과거 업체명·번호·확인자명도 가리되 SHA-256/fingerprint는 식별용 원래 값을 유지한다. 가린 파일명은 문서 ID와 버전만 쓴다. masked=false는 개인정보가 있는 원본이다.

인증 실패 401, 접근 권한 부족 403, 없는 계약 404, 오래된 revision·생성 중 자료 변경·원본 누락/해시 불일치 409, 원본 100개/총 250MB 또는 변환·이력을 포함한 묶음 250MB 초과 413, 가림/변환 실패 503이다. 실패 시 일부 ZIP 또는 원본을 자동 반환하지 않는다. 전송 후 임시 파일을 정리하며 no-store/nosniff 헤더를 사용한다. 계약 revision·검수·결재는 바뀌지 않고, 준비 성공 시 `CONTRACT_BUNDLE_EXPORT_REQUEST` 감사 이벤트만 남긴다(사용자의 완전 수신을 증명하는 이벤트는 아님).

## 표시용 PNG 가림·요약 집계 보완

PNG 미리보기·가린 이미지 다운로드·ZIP은 미리보기 전용 가림 정책을 공유한다. OCR의 여러 단어에 나뉜 상호를 라벨·알려진 문자열로 함께 가린다. 발행일을 사업자번호로 오인하던 짧은 `3자리-2자리` 패턴을 없앴다. AI 판독·프롬프트·가드·평가 코드는 변경하지 않는다. 수정창/요청 문구의 업무상 원래 값 안내는 frontend 담당 범위다.

`GET /api/contracts/3/summary`의 facts.open_issue_count는 화면과 같은 **문제 카드 수**다. 같은 문서 ID의 여러 검사 → doc-ID 한 장, 누락 → missing-문서종류, 계약 수준 문제 → contract-rule_id로 묶는다. 국세청 미연동 REVIEW 안내는 제외한다. 추가 필드:

```json
{"open_issue_count_unit":"ISSUE_CARD","counts":{"issue_card_count":2,"check_item_count":3},"issue_groups":[{"key":"doc-12","checks":[{"rule_id":"BUSINESS_NO_MATCH","field":"12","status":"FAIL"},{"rule_id":"AMOUNT_MATCH_ESTIMATE","field":"12","status":"FAIL"}]},{"key":"missing-tax_invoice","checks":[{"rule_id":"REQUIRED_DOCUMENTS","field":"tax_invoice","status":"MISSING"}]}]}
```

목록 API의 open_issue_count와 기존 action_summary는 이전 계약대로 **검사 항목 수**다. 이번 변경은 요약 문장의 카드 수와 검사 수를 명시적으로 구분하며 원래 규칙 결과·평가 수치는 변경하지 않는다.
