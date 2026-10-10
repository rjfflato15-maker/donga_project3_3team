# 지급 완료 사실 기록 API (2026-10-05)

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: HEAD `54a8841` + 미커밋 작업 트리. 작업 트리 기준. 설치 검증 범위는 고객 패키지 안내 참조.

실제 송금 없이 **계약 전체의 지급을 이미 완료했다는 사실**을 사람이 기록한다. 분할 지급 계약도 모든 회차를 포함한 계약 전체 지급 완료일을 기록한다. 개별 회차·금액·은행 처리 성공을 나타내지 않는다. 담당자와 대표가 기록할 수 있으며 대표 최종 결재 권한은 바뀌지 않는다. 외부 API 호출은 없다.

서버를 재시작하면 `Base.metadata.create_all`이 신규 테이블 `pilot_contract_payments`, `pilot_payment_confirmations`를 만든다. 기존 테이블의 컬럼 변경·평가/추출 스키마 변경은 없다. 지급 등록 요청 키와 본문 해시는 기존 불변 snapshot JSON의 record_request에 저장한다. 과거 snapshot에 이 메타데이터가 없어도 조회·정정·재확인은 유지되므로 별도 DB 마이그레이션은 필요 없다. SQLite 백업은 두 테이블을 포함하고 새 폴더 복원 후 유지한다. 계약 ZIP `history.json`에는 `payments`, `payment_confirmations`가 추가된다. 계약 제외 API는 계약을 숨기고 지급 사실과 연결 이력을 보존한다. 계약 찾기에서 복원할 수 있다.

## 최초 기록

`POST /api/pilot/contracts/{contract_id}/payment`

```json
{
  "paid_on": "2026-10-05",
  "method": "TRANSFER",
  "note": "계약 전체 지급 완료를 거래 내역으로 확인",
  "revision": 8,
  "payment_revision": 0,
  "idempotency_key": "client-generated-unique-request-key",
  "acknowledge_new_payment": false
}
```

`paid_on`은 정확한 `YYYY-MM-DD` 실존 날짜이며 한국 시각 기준 미래일은 거절한다. `method`는 `TRANSFER` 또는 `OTHER`, 메모는 앞뒤 공백 제거 후 최대 2,000자(빈 문자열 허용), `revision`은 1 이상의 정수다. 등록이 아니라 계획일을 넣지 않는다. payment_revision은 0 이상의 정수이며 최초 등록에는 0을 보낸다. idempotency_key는 공백 제거 후 8~100자이며 동일한 요청을 재시도할 때 본문과 함께 유지한다. 두 값이 빠진 이전 클라이언트 요청은 422로 거절하며 기록을 바꾸지 않는다. acknowledge_new_payment는 엄격한 boolean(기본 false)이며 취소 후 새 사실을 등록할 때만 명시 true가 필요하다. 요청에 임의 필드는 허용하지 않는다.

필요 조건은 현재 계약 자료와 동일한 revision/fingerprint의 유효한 대표 최종 `CONFIRMED` 결재다. 최신 결재가 반려되었거나 원본 누락·기준 변경·재발행으로 fingerprint가 달라졌으면 거절한다. 등록할 때 서버가 현재 fingerprint와 최신 최종 결재를 잠금 안에서 다시 확인한다. 현재 원문 바이트의 SHA-256도 등록 당시 receipt와 일치해야 한다. 원본이 사라져 가린 사본으로 경로가 대체되거나 바이트가 변경되거나 등록 해시가 없는 이전 자료이면 409로 거절한다. 원본 복구·재등록 후 재결재가 필요하다.

최초 성공은 **201**, 같은 키와 같은 본문을 재전송하면 **200**과 지급 기록의 현재 상태를 돌려준다. 그 사이 정정·취소된 경우에도 과거 성공 응답을 되살리지 않고 현재 상태(VOIDED 포함)를 반환한다. 재전송도 현재 계약 revision·유효한 최종 결재·원본 해시 검사를 생략하지 않으며, 이 기준이 바뀌면 기존처럼 409다. 같은 키의 본문을 바꾸면 409다. 이미 유효한 지급 기록이 있으면 같은 값이더라도 다른 키의 새 등록은 409이며, 중복 재전송에는 저장에 사용한 키를 유지한다. 현재 지급 버전이 다른 새 요청도 409이며, 취소 후 재등록에는 최신 버전과 별도의 명시 확인이 필요하다. 재시도·동시 요청은 지급 사실과 감사 이벤트를 중복 생성하지 않는다. 다른 내용으로 덮어쓰기는 409다. 지급 기록과 감사 이벤트는 같은 DB 트랜잭션으로 저장한다.

```json
{
  "payment_id": 1,
  "scope": "WHOLE_CONTRACT",
  "status": "RECORDED",
  "paid_on": "2026-10-05",
  "recorded_paid_on": "2026-10-05",
  "method": "TRANSFER",
  "note": "계약 전체 지급 완료를 거래 내역으로 확인",
  "actor_name": "담당자",
  "created_at": "2026-10-05T08:30:00",
  "original_snapshot": {
    "contract_amount": 1100000,
    "vendor_name": "가상 업체",
    "business_number": "123-45-67890",
    "amount_basis": "TOTAL",
    "tax_amount": 100000,
    "payment_mode": "FULL",
    "revision": 8,
    "fingerprint": "현재 결재 자료의 64자 해시",
    "review_id": 5
  },
  "current_confirmation": {
    "review_id": 5,
    "revision": 8,
    "fingerprint": "현재 결재 자료의 64자 해시",
    "actor_name": "담당자",
    "created_at": "2026-10-05T08:30:00"
  }
}
```

## 조회 및 자료 변경 후 처리

`GET /api/pilot/contracts/{contract_id}/payment`는 같은 객체를 반환한다. 계약은 있지만 기록이 없으면 `null`이다. `GET /api/contracts`, `GET /api/contracts/{id}`와 계약 생성·수정 응답의 `payment`도 같은 규칙이다.

현재 최종 결재에 연결된 경우에만 `payment.paid_on`에 날짜를 넣는다. 자료 변경·재발행·반려·새 최종 결재 뒤에는 과거 사실을 보존하되 다음처럼 반환한다.

```json
{
  "payment_id": 1,
  "scope": "WHOLE_CONTRACT",
  "status": "RECONFIRMATION_REQUIRED",
  "paid_on": null,
  "recorded_paid_on": "2026-10-05",
  "method": "TRANSFER",
  "note": "계약 전체 지급 완료를 거래 내역으로 확인",
  "current_confirmation": null
}
```

위 예시는 `original_snapshot`, `created_at`, `actor_name`을 생략했다. 원래 전체 지급 사실은 모두 남는다. 화면은 **현재 완료 판정에는 `paid_on`**, 과거 지급 이력 안내에는 `recorded_paid_on`을 사용한다. 변경된 계약을 지난 계약으로 숨기거나 다시 지급하라고 안내해서는 안 된다. 현재 자료 검수·재결재를 먼저 수행하고 기존 지급 사실과의 연결을 확인한다.

`reconfirmation_allowed`는 현재 재결재·원본 해시·동일 거래처와 지급 범위가 모두 충족되고 아직 현재 연결이 없을 때만 `true`다. 불가한 경우 `blocked_reason`은 `FINAL_REVIEW_REQUIRED`, `SOURCE_VERSION_UNVERIFIED`, `PAYEE_OR_AMOUNT_CHANGED`이고, 연결 완료 또는 재확인 가능한 경우에는 `null`이다. 원본 receipt가 검증되지 않으면 현재 결재 상태 표시와 별개로 `payment.paid_on`은 `null`로 반환해 변경된 자료를 완료로 숨기지 않는다.

## 같은 지급 사실 재확인

`POST /api/pilot/contracts/{contract_id}/payment/{payment_id}/reconfirm`

```json
{
  "revision": 10,
  "note": "수정된 자료를 재결재했고 기존 전체 지급 사실이 동일 계약에 해당함을 확인",
  "acknowledge_same_payment": true
}
```

현재 유효한 최종 결재가 필요하며 메모는 공백 제거 후 10~2,000자다. `acknowledge_same_payment`는 반드시 `true`다. 지급일·방법·원래 메모·지급 사실 ID를 수정하거나 새 지급 사실을 만들지 않는다. 새 결재와 같은 과거 지급 사실을 연결하는 이력 및 `PAYMENT_RECONFIRMED` 감사 이벤트를 추가한다. 같은 결재에서 다시 호출하면 200으로 기존 상태를 반환하고 이력을 중복 생성하지 않는다.

원래 기록의 거래처 사업자번호(하이픈·공백 제외)·계약 금액·금액 기준·세액·지급 방식이 바뀌었다면 기존 **전체 지급 완료**를 다른 수취업체/총액에 그대로 연결할 수 없어 409다. 같은 사업자번호의 거래처명 변경은 허용하되, 사업자번호가 둘 다 비어 있으면 거래처명도 같아야 한다. 지급 기록 정정·잘못 기록한 지급 완료 취소는 아래 정정 API를 사용한다. 추가 지급·회차별 기록은 지원하지 않는다. 운영 전에 실제 지급 내역을 확인해야 하며 화면에는 남아 있는 지급 사실과 이 제한을 안내해야 한다. 기존 지급 사실은 보존한다. 잘못된 완료 기록을 취소한 뒤 실제 지급 사실을 다시 기록할 수 있다.

## revision 및 오류

지급 사실 등록·재확인은 자료의 revision을 올리지 않는다. 문서/기준 변경은 기존 규칙대로 revision을 올리고 최종 결재 및 현재 지급 연결을 무효화한다. 같은 자료에서도 최신 최종 결재 ID가 바뀌면 재확인이 필요하다. 원래 사실은 불변이고 연결 이력은 추가된다. 감사 작업명은 `PAYMENT_RECORDED` / `PAYMENT_RECONFIRMED`이며 지급 사실·연결 이력·감사가 원자적으로 저장된다.

| 상태 | 조건 | 응답 예시 |
| --- | --- | --- |
| 401 | 미로그인·만료·비활성 계정 | `{"detail":"로그인 시간이 만료되었습니다. 다시 로그인하세요."}` |
| 403 | 업무 권한 없음·초기 비밀번호 미변경 | `{"detail":"등록된 업무 권한이 없습니다."}` |
| 404 | 계약/해당 계약 지급 ID 없음 | `{"detail":"이 계약의 지급 기록을 찾을 수 없습니다."}` |
| 409 | 자료 revision이 오래됨 | `{"detail":"계약 자료가 변경되었습니다. 최신 자료를 다시 확인하세요."}` |
| 409 | 현재 최종 결재 없음 | `{"detail":"현재 자료의 대표 최종 결재 후 지급 사실을 기록하세요."}` |
| 409 | 기존 지급 사실 덮어쓰기·재기록 | `{"detail":"이미 지급 사실이 기록되어 있습니다. 재결재 후에는 기존 지급 사실 재확인을 사용하세요."}` |
| 409 | 원본 해시 확인 불가 | `{"detail":"현재 원본을 등록 당시 해시로 확인할 수 없습니다. 원본을 복구·재등록하고 다시 결재하세요."}` |
| 409 | 전체 지급의 수취업체/금액 조건 변경 | `{"detail":"거래처 식별자·계약 금액·금액 기준·세액·지급 방식이 변경되어 기존 전체 지급 사실을 연결할 수 없습니다."}` |
| 422 | 날짜·방법·revision·길이·명시 확인 값 오류 | 기존 FastAPI 검증 응답의 `detail` 배열(`loc`, `msg`, `type`) |

새 화면은 지급 기록 버튼을 **계약 전체 지급 완료 기록**으로 명시하고, `RECONFIRMATION_REQUIRED`에서는 추가 송금 안내 대신 **기존 지급 사실 재확인**을 연결한다. 지급 저장 요청에는 현재 payment_revision과 idempotency_key를 반드시 포함한다. 네트워크 오류 뒤 재시도는 동일한 키·본문을 유지하고, 409는 최신 계약·지급 상태를 다시 조회한 뒤 확인한다.

## 검증 기록

2026-10-05 가상 자료 테스트: 최초 지급·결재 흐름·재발행·백업복원·계약 ZIP·목록·일반 API 묶음 **84개 통과**(45.99초). 이후 저장소 보강을 반영한 최종 지급 테스트 **22개**, 최종 전체 백엔드 **449개 통과**(75.50초, 기존 폐기 예정 API 경고 3967개). 로그인/역할, 현재 최종 결재/구 revision, 날짜/길이/방법, 동시 중복 요청, 계약 전체 범위, 재발행 후 과거 사실 보존, 수취업체/총액 변경 차단, 원본 receipt 불일치와 현재 결재 표시의 분리, 같은 지급 재확인, 계약 삭제, ZIP 및 새 폴더 복원을 포함한다. 실제 업무함·held-out 자료·LLM/가드를 실행하지 않았다.

원문 TXT 유실 시 `resolve_path`가 가린 사본으로 대체하던 기존 오류는 raw/masked/text 경로를 구분하도록 수정했다. Windows의 이전 절대경로를 같은 종류 경로로 복원하는 호환성은 유지한다. 새 저장소 검사 12개와 저장소·동시성·복원 묶음 30개가 통과했다. 원문 유실은 이제 fingerprint 변경·결재 `STALE`·`FINAL_REVIEW_REQUIRED`·원문 다운로드404다. 원문 파일이 존재하지만 bytes가 등록 SHA와 다른 경우에는 현재 결재 표시가 유지되어도 지급 검증이 `SOURCE_VERSION_UNVERIFIED`·409로 막는다. 두 경우 모두 과거 지급 사실은 보존한다. 최종 검사 로그는 로컬 시각화 폴더 `backend-payment-storage-verified-20261005.log`에 보존했다.

8041 별도 가상 DEV 업무함을 새 백엔드로 재시작했다. 담당자 계정에서 이미 대표 결재한 계약 6번의 지급 완료 사실을 기록했고, ⑤가 완료되어 `끝났어요`로 표시됐다. 할 일 목록에서는 빠지고 지난 계약 목록에 `끝`으로 남는 것을 직접 브라우저에서 확인했다. 증거는 로컬 시각화 폴더 `payment-api-871d277-ui-recorded.jpg`다. 실제 송금은 없었다. **재발행 후 기존 지급 사실 재확인 화면은 아직 Claude 연결 대상**이며 API 테스트 통과를 그 화면의 완료로 세지 않는다. ZIP 파일 내용 검사와 사용자의 실제 브라우저 저장 완료는 별도다.


## 지급 기록 정정 (2026-10-09)

`POST /api/pilot/contracts/{id}/payment/{payment_id}/corrections`를 사용한다. `action`은 `CORRECT` 또는 `VOID`, `revision`과 `fingerprint`는 현재 계약 기준, `payment_revision`은 조회한 `correction_revision`(최초 0), `reason`은 공백 제외 3~2,000자다. CORRECT에는 `paid_on`, `method`, `note`를 함께 보낸다. 미래일은 거절한다.

최초 지급 row는 불변이며 정정 내용과 이전/이후 값은 새 테이블·감사 이벤트에 보존한다. 자료 기준과 지급 정정 버전이 바뀌면 409다. VOID는 실제 송금을 취소하지 않고 잘못된 지급 완료 기록을 취소한다. 상태는 `VOIDED`, `paid_on=null`이고 완료 목록에서 지급 기록 단계로 돌아온다. 실제 지급 내역 확인 후 기존 등록 API로 새 사실을 기록할 수 있다. 이때 조회한 correction_revision을 payment_revision으로, 새 idempotency_key와 acknowledge_new_payment=true를 함께 보낸다. 이전 키 재전송은 현재 VOIDED 상태를 반환할 뿐 새 RECORD를 만들지 않는다. 최신 버전 없이 보내거나 명시 확인이 없으면 409다. 계약 ZIP의 `history.payment_corrections`에도 정정 이력이 포함된다. 화면은 더보기 → 지급 기록 정정에서 처리한다.


## 취소 후 새 지급 사실 등록 예시 (경계 복구 보강)

```json
{
  "paid_on": "2026-10-05",
  "method": "TRANSFER",
  "note": "취소 후 실제 지급 내역을 다시 확인",
  "revision": 8,
  "payment_revision": 12,
  "idempotency_key": "new-intent-after-void-unique-key",
  "acknowledge_new_payment": true
}
```

예시의 12는 실제로 조회한 payment.correction_revision으로 바꾼다. 최초 row와 모든 VOID/CORRECT/RECORD 이력은 보존한다. 재등록 성공 후 같은 요청 키를 다시 보내도 RECORD 이력은 한 번만 생긴다. 이후 다시 취소해도 이전 최초 등록 또는 재등록 요청을 재전송하여 취소 상태를 되돌릴 수 없다. 과거 버전 클라이언트에는 새 필수 입력 누락을 422로 알린다. 지급 버전은 계약 자료 revision과 별도이며 최초 등록·재등록으로 계약 자료 revision을 올리지 않는다.
