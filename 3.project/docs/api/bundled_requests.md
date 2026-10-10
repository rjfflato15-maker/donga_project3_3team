# 계약별 묶음 보완 요청과 부분 회신

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: HEAD `54a8841` + 미커밋 작업 트리. 작업 트리 기준. 설치 검증 범위는 고객 패키지 안내 참조.

2026-10-05 사용자가 합의한 개선은 **같은 계약의 거래처 요청을 한 곳에서 선택하고 한 번 기록하며, 받은 서류와 남은 요청은 항목별로 유지하는 것**이다. 사내 메신저나 자동 발송은 추가하지 않는다. 현재 화면은 BundleRequestPage·BundleReplyPanel에서 연결한다.

## 화면 흐름

1. 계약 상단에 `필요 6종 · 받은 3종 · 빠진 3종`처럼 전체 상황을 먼저 보여 준다. 받은 수는 현재 서류의 종류 수이며 파일 개수가 아니다.
2. 거래처에 요청할 서류는 체크 목록 한 개로 모은다. 외부 누락 서류는 기본 선택할 수 있다. 금액·번호 불일치는 원문에서도 문제인지 확인한 뒤 선택한다. 앱 판독 실패·원본 유실·사내 납품 검수확인서는 거래처 요청에서 제외하고 별도 확인 목록에 둔다.
3. `선택한 N건 요청 문구 만들기`를 누르면 선택한 서류와 사유를 한 문구로 보여 준다. 연락 방법과 회신 기한도 한 번만 입력한다. 문구 복사는 요청 기록이나 발송이 아니다.
4. 사용자가 평소 연락 방법으로 실제 요청한 뒤 `요청했어요 · 기록하기`로 요청 한 건과 선택 항목을 저장한다. 요청 건수와 포함 항목 수를 구분한다.
5. 회신 대기에는 `3건 요청 · 1건 받음 · 2건 기다림`처럼 항목 상태를 표시한다. 파일을 올린 뒤 실제 받은 항목을 선택해서 기록한다. 일부만 받았으면 나머지 항목과 회신 대기를 유지한다.
6. 전부 회신을 받았어도 금액 불일치 등이 남으면 사람 확인·새 보완이 필요하다. **회신 수령과 검사 통과는 다른 상태**다. 업로드나 항목 수령 기록으로 검수·결재를 자동 완료하지 않는다.

개별 큰 카드와 반복 요청 버튼을 기본 화면에서 줄이고 근거·상세 검사는 해당 항목을 펼칠 때 보여 준다. 원문 대조와 개별 파일 업로드·재발행은 기존 기능을 사용한다.

## 기존 기록과 호환

- 기존 단일 요청은 그대로 보존한다. 기존 메모에서 요청 대상을 추측하거나 모두 요청 중이라고 표시하지 않는다.
- 새 묶음의 같은 항목이 이미 대기 중이면 기존 요청을 보여 주고 중복 요청을 막는다. 재발행되어 현재 문서 ID가 바뀌어도 같은 논리 문서의 대기 항목을 연결한다. 같은 종류의 별도 추가 서류와는 구분한다.
- 새 묶음은 항목별 API로 회신을 기록한다. 기존 전체 `답 받음` API로 일부 수령을 전체 완료로 바꾸지 않는다.
- 대기 요청 수와 성과의 요청 횟수는 묶음 부모 기록 수다. 누락 종류 수·요청 항목 수·받은 항목 수는 별도 숫자다.
- 안내문·측정용 커밋은 새 화면 병합과 사용자 확인 뒤 확정한다. 이전 화면의 검사 결과는 새 화면의 완료 근거로 쓰지 않는다. 기존 과제 원문·정답·ZIP·고정 예측은 바꾸지 않는다.

## 화면 완료 확인

- 6종 중 3종만 올렸을 때 빠진 종류가 한 번에 보이고 선택한 외부 서류로 문구 하나·요청 기록 한 건이 만들어진다.
- 외부 누락과 사내 작성·원문 판독 문제가 섞여도 거래처 요청에는 선택한 외부 항목만 들어간다.
- 세 항목 중 하나만 받으면 `1건 받음 · 2건 기다림`과 대기 단계가 유지된다.
- 금액 불일치 서류를 받았다는 기록만으로 검수 PASS나 대표 결재가 되지 않는다.
- 동일 요청 재전송·두 번 누르기·같은 항목 추가 요청으로 중복 기록이 생기지 않는다.
- 자료 변경·다른 사용자의 항목 처리 뒤에는 오래된 선택/동의/상태를 저장할 수 없고 새 정보를 불러온다.
- 요청 창의 Tab 순환·Esc·원래 버튼 포커스 복귀, 빈 선택·저장 오류·재시도에서도 같은 규칙을 유지한다.
- 개인정보 ON에서는 목록·기록에 가림을 적용한다. 거래처에 보낼 문구에 실제 이름을 쓰는 기존 정책은 그대로 명시한다.

현재 문서의 화면 흐름은 연결 기준이며 새 화면이 구현되었다는 뜻은 아니다.

## API: 최신 요청 후보

`GET /api/pilot/contracts/3/resubmission-bundle-context`

응답 예시의 fingerprint는 형식을 설명하기 위한 예시다. 저장할 때는 최신 응답의 실제 fingerprint를 그대로 사용한다. 아래는 주요 필드만 표시한 예시다.

```json
{
  "contract_id": 3,
  "revision": 7,
  "fingerprint": "0000000000000000000000000000000000000000000000000000000000000000",
  "document_counts": {"required": 6, "received": 3, "missing": 3},
  "received_document_types": ["contract", "estimate", "business_registration"],
  "vendor_candidates": [
    {
      "issue_key": "missing:bank_account",
      "title": "통장사본 제출 요청",
      "document_type": "bank_account",
      "document_id": null,
      "reason": "통장사본 제출이 필요합니다.",
      "requires_original_review": false,
      "already_requested": false,
      "pending_items": []
    },
    {
      "issue_key": "missing:tax_invoice",
      "title": "세금계산서 제출 요청",
      "document_type": "tax_invoice",
      "document_id": null,
      "reason": "세금계산서 제출이 필요합니다.",
      "requires_original_review": false,
      "already_requested": false,
      "pending_items": []
    }
  ],
  "internal_items": [{"issue_key": "missing:inspection_confirmation", "title": "검수확인서 제출 요청"}],
  "reading_items": [],
  "notices": [{"rule_id": "BUSINESS_STATUS", "message": "국세청 진위 조회는 미연동입니다.", "requires_action": false}],
  "pending_items": [],
  "legacy_pending_request_count": 0
}
```

- `vendor_candidates`만 거래처 요청 후보로 사용한다. `internal_items`와 `reading_items`는 사내 확인 목록이다. 국세청 미연동은 `notices`에 있으며 할 일에 넣지 않는다.
- `requires_original_review=true`면 원문 대조 확인 없이 저장할 수 없다. 문서가 원본과 다르거나 인식 실패·미분류 상태이면 사내 확인으로 이동한다.
- `already_requested=true`는 해당 후보에 대해 새 구조화 요청이 대기 중이라는 뜻이다. 기존 요청과 항목 ID를 보여 주고 새 요청 선택에서 뺀다. 누락 서류를 올려 후보 목록에서 사라져도 대기 요청은 수령 기록 전까지 유지되므로 `pending_items`/요청 목록을 따로 표시한다.
- `issue_key`는 서버가 제공하는 식별자 그대로 사용한다. `document:` 뒤의 값은 논리 문서 ID이며 현재 `document_id`와 다를 수 있다. 숫자를 해석해서 현재 문서를 열면 안 된다. 원문 열기는 후보의 `document_id`를 사용한다.
- 같은 종류 ADD 문서는 별도 논리 문서다. REISSUE는 같은 논리 문서라 이전 요청과 연결된다.
- `legacy_pending_request_count`가 있으면 기존 요청 기록을 함께 보여 준다. 그 메모를 분석해 항목별 대기 상태를 만들어 내지 않는다.

화면의 서류명은 기존 `DOCUMENT_TYPE_KO` 표시명을 사용해 다른 화면과 맞출 수 있다. 요청 창은 같은 계약의 후보 배열로 문구를 만들고 서버에 기록은 한 번만 보낸다. 새 context API를 사용할 수 없는 서버에서는 새 버전 재시작 안내를 보여 주며 기존 자유 메모 API로 묶음 기록을 우회하지 않는다. context revision/fingerprint가 바뀌면 원문 확인 동의와 선택을 다시 확인하게 하고, 회신 폼은 request_revision 변경도 같은 방식으로 처리한다.

## API: 한 번 요청한 사실 기록

`POST /api/pilot/contracts/3/resubmission-bundles`

```json
{
  "revision": 7,
  "fingerprint": "0000000000000000000000000000000000000000000000000000000000000000",
  "idempotency_key": "521a59e5-3b8e-4939-8e8a-2b8410909333",
  "contact_method": "KAKAO",
  "due_on": "2026-10-08",
  "memo": "통장사본과 전자세금계산서를 함께 요청함",
  "items": [
    {"issue_key": "missing:bank_account", "reviewed_original": false},
    {"issue_key": "missing:tax_invoice", "reviewed_original": false}
  ]
}
```

`items`는 1~30개이며 중복 키는 허용하지 않는다. `memo`는 1~2,000자다. 넘으면 저장 전에 안내하고 수정하게 한다. `slice(0, 2000)`으로 뒤 항목을 조용히 잘라 버리지 않는다. 요청 항목의 사유·검사·문서 버전·원본 SHA·추출값은 서버가 현재 후보에서 읽어 스냅샷으로 보존한다. 클라이언트가 임의 사유나 문서 ID를 전송하지 않는다.

`requested_on`은 생략하면 한국 날짜다. `due_on`은 선택이며 새 요청의 요청일보다 앞설 수 없다. 연락 방법은 기존 KAKAO/SMS/EMAIL/PHONE/OTHER다. 생성은 **201**, 같은 사용자·계약·키로 같은 내용 재전송은 **200**이며 같은 요청 ID를 반환한다. 재전송 키는 요청 창에서 한 번 만들고 네트워크 실패 재시도에 재사용한다. 문구·선택·기한을 바꿔 새 요청을 만들 때는 새 키를 사용한다.

응답 주요 필드:

```json
{
  "request_id": 12,
  "contract_id": 3,
  "status": "WAITING_RESPONSE",
  "memo": "통장사본과 전자세금계산서를 함께 요청함",
  "bundle": {
    "contract_revision": 7,
    "contract_fingerprint": "0000000000000000000000000000000000000000000000000000000000000000",
    "request_revision": 1,
    "counts": {"total": 2, "waiting": 2, "received": 0, "cancelled": 0},
    "items": [
      {"item_id": 21, "issue_key": "missing:bank_account", "title": "통장사본 제출 요청", "status": "WAITING_RESPONSE"},
      {"item_id": 22, "issue_key": "missing:tax_invoice", "title": "세금계산서 제출 요청", "status": "WAITING_RESPONSE"}
    ]
  }
}
```

전체 요청 목록은 기존 `GET /api/pilot/contracts/3/resubmission-requests`를 사용한다. 새 요청은 `bundle`에 항목·집계가 있고 기존 요청은 `bundle=null`이다. `GET /api/contracts/3/review-context`의 `follow_up.requests`에도 같은 구조를 제공한다.

## API: 받은 항목만 기록

`PATCH /api/pilot/contracts/3/resubmission-bundles/12/items`

```json
{
  "revision": 8,
  "fingerprint": "0000000000000000000000000000000000000000000000000000000000000000",
  "request_revision": 1,
  "items": [{"item_id": 21, "status": "RECEIVED", "note": "통장사본만 받았고 나머지 서류는 기다림"}]
}
```

업로드 이후의 **현재 계약** revision/fingerprint와 최신 **요청** request_revision을 보낸다. 수령 기록이 성공하면 request_revision은 1 증가한다. 위 예시는 부모 status가 WAITING_RESPONSE이고 counts는 total=2, waiting=1, received=1, cancelled=0이다. 나머지 항목을 받기 전에는 요청 전체를 닫지 않는다.

항목 status는 RECEIVED/CANCELLED이며 `note`는 1~2,000자다. 대기 항목이 0이 되었을 때 받은 항목이 하나라도 있으면 부모 RECEIVED, 전부 취소했으면 CANCELLED다. 취소 건수도 숨기지 않는다. 종료한 항목은 재변경할 수 없다. 회신 기록과 계약 자료 수정의 revision은 서로 다르며 요청 기록은 계약 revision이나 결재를 변경하지 않는다.

## 오류·권한·저장 범위

오류는 기존 API와 같이 `{"detail":"안내 문구"}`다. 형식 오류 422는 FastAPI의 필드별 detail 배열이며 새 요청의 날짜 순서 검증 422는 안내 문자열이다.

| HTTP | 조건 | 화면 처리 |
| --- | --- | --- |
| 400 | 현재 거래처 후보가 아닌 항목, 불일치 원문 확인 누락 | 선택/원문 확인 수정, 사내 확인 항목 자동 요청 금지 |
| 401/403 | 미로그인·비활성/미등록 역할·초기 비밀번호 변경 필요 | 기존 로그인/계정 안내 사용 |
| 404 | 계약 없음·다른 계약의 요청·그 요청에 속하지 않은 항목 | 최신 계약/요청 목록 확인 |
| 409 | 자료 revision/fingerprint 변경·원본 변경·이미 대기 중·같은 키 다른 내용·요청 revision 변경·종료 항목 변경 | 오류를 보여 주고 후보/요청 재조회, 기존 선택·수령 동의를 자동 재사용하지 않음 |
| 409 | 새 묶음을 기존 전체 요청 PATCH로 닫으려 함 | 항목별 회신 화면 사용 |
| 422 | 빈/중복/30개 초과 항목·길이·날짜·잘못된 타입 | 폼에서 수정, 자동 재시도하지 않음 |

기존 사내 담당자·대표·관리자 업무 API 권한을 유지한다. 요청 생성·부분 수령은 부모·항목·감사 기록을 한 트랜잭션에 저장한다. 기존 대기/성과 집계는 부모 요청 건수 그대로라 항목을 이중으로 세지 않는다.

새 테이블 두 개를 추가하며 기존 요청 열과 기록을 수정하지 않는다. 서버 시작의 create_all로 기존 DB에 테이블을 생성한다. 운영 업무함을 직접 변경하거나 기존 요청을 자동 전환하지 않는다. 백업은 새 테이블을 포함한 DB 전체를 보존한다. 계약 ZIP의 history.requests.bundle에 요청 당시 근거와 부분 수령 상태를 보존하고 기존 JSON 가림을 적용한다. 재전송 키는 ZIP에서 제외한다. 자동 발송·LLM 호출·추출/평가 재실행은 없다.

이번 서버 구현은 격리된 가상 자료·TestClient 업무함에서 검사한다. 사용자가 접속 중인 8030/8041과 실제 업무함은 초기화·재시작하지 않는다. 새 화면을 병합한 뒤 테스트 전용 서버를 명시적으로 재시작해서 함께 확인해야 한다.

## 실행한 검증 (2026-10-05)

- 새 묶음 요청 28개와 ZIP·복원 3개, 합계 31개 통과. 후보 분리·혼합 판독 사유 제외·SHA·논리 문서 중복·부분 대기·요청/계약 revision·동시 저장·원자적 rollback·자정 이후 재시도·권한·계약 삭제 cascade를 확인했다.
- 기존 요청/검토 workflow 17개 통과. 새 ZIP·기존 ZIP·백업 관련 24개도 통과했다. 이 수는 전체 검사와 겹치므로 더해서 시행 수로 표현하지 않는다.
- 마지막 전체 `python -m pytest backend/tests -q --disable-warnings`: **480개 통과**, 106.57초. 기존 폐기 예정 API 경고 4,961개, 실패 없음. 로그 `backend-bundled-requests-full-20261005.log`와 JUnit XML을 로컬 시각화 폴더에 보존했다.
- 원문 ZIP에 요청 당시 v1 문서·SHA·부분 수령 상태가 있고 재발행 v2와 구분된다. 가림 ZIP의 제목·사유·회신 메모에서 가상 업체/번호가 제거되고 금액이 유지됐다. 새 폴더 복원 후 항목 상태·이전본/현재본·원문 해시가 보존됐다.
- 독립 코드·문서 대조를 완료했다. 새 UI 연결·브라우저 클릭·실제 ZIP 저장은 아직 확인 전이다. frontend 변경이 없으므로 이전 28개/빌드 기록을 새 화면 검증으로 표시하지 않는다.


## 회신 기록 정정 (2026-10-09)

기존 items PATCH는 대기 항목의 첫 수령·취소 처리만 한다. 잘못 기록한 닫힌 항목은 `POST /api/pilot/contracts/{id}/resubmission-bundles/{request_id}/corrections`로 정정한다. 계약 revision/fingerprint와 request_revision을 전송하며 각 items 항목은 item_id, status(WAITING_RESPONSE/RECEIVED/CANCELLED), note(3~2,000자)를 가진다. 이전 상태·메모·처리 시각은 감사 기록에 남는다. 같은 항목의 다른 요청이 이미 대기 중이면 중복 회신 대기를 만들지 않고 409로 안내한다. 자동 검사 결과나 원문 확인 기록은 바꾸지 않는다. 회신 화면의 해당 서류 ‘회신 기록 정정’을 사용한다.
