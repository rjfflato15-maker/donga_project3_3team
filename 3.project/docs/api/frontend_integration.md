# 현재 화면과 API 연결 규칙

> 상태: 현재 기준
> 확인일: 2026-10-10
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [ContractDashboard.tsx](../../frontend/src/pages/ContractDashboard.tsx) · [ContractStageView.tsx](../../frontend/src/components/review/ContractStageView.tsx) · [DocumentWorkspace.tsx](../../frontend/src/components/review/DocumentWorkspace.tsx) · [useVlmReread.ts](../../frontend/src/hooks/useVlmReread.ts) · [ReviewFieldTable.tsx](../../frontend/src/components/review/ReviewFieldTable.tsx) · [useAutoRefresh.ts](../../frontend/src/hooks/useAutoRefresh.ts) · [documents.py](../../backend/app/api/documents.py)

## 화면 책임

ContractDashboard가 계약 목록·선택·상세 갱신·XLSX 다운로드를 관리한다. ContractStageView는 서류·보완 요청·결재·지급·처리 이력의 현재 차례를 구성한다. ReviewOverviewPanel·reviewTasks는 실제로 처리할 문제 목록을 만들며 서버 상신 조건의 필수 원문 대조도 할 일에 포함한다. DocumentWorkspace는 선택 항목의 원문 대조·확인·수정·보류·분류 정정·재발행과 AI 후보 반영을 연결한다. useVlmReread는 실행·페이지·revision·가림 전환별 취소를 관리한다. 현재 VLM 화면은 DocumentWorkspace 내부에서 ReviewFieldTable과 함께 구성되며 독립 재판독 탭을 사용하지 않는다. 화면·공통 로직·API·테스트의 파일별 책임은 [소스 책임 지도](../architecture/module_map.md)를 따른다.

보완 요청의 자료 기준·타입·문구는 `features/requests/model.ts`, 전송은 `features/requests/api.ts`가 담당한다. 담당자 지정은 `features/assignments`, 업무 목록의 단계·검색 파생값은 `features/contracts/dashboardModel.ts`를 사용한다. 화면 컴포넌트를 다른 기능의 공통 타입·API 제공자로 사용하지 않는다.

서버의 수동 정정과 VLM 후보 저장은 `document_correction_service.apply_correction`, 일반 검토와 결재의 최종 확인은 `contract_review_service.submit_review`를 공유한다. HTTP 경로와 권한 의존성은 각 API에 유지한다.

## 공통 데이터 기준

목록은 표시 중인 탭에서 10초마다 갱신하고 숨김 상태에서는 주기를 멈춘다. 중복 요청·늦은 세대·취소를 처리한다. 계약 상세의 편집값은 자동 목록 응답으로 덮어쓰지 않는다. 자료·결재 상태가 달라지면 사용자가 최신 상세를 불러오도록 안내한다.

수정·보완 동의·결재는 서버의 현재 revision/fingerprint와 연결한다. 계약 전환·재발행·저장 뒤에는 이전 동의와 응답을 폐기한다. 401/403은 인증/권한, 409는 자료 기준 충돌, 422는 입력·페이지·상태 조건을 확인한다.

계약 목록·처리 기록 화면의 확인 정보는 `GET /api/contracts/{id}/review-context?include_evidence=false`로 읽는다. 원문 대조를 열 때는 `evidence_document_id={document_id}`로 해당 서류만 근거를 추출한다. 값·확인·보류·검사·원본 해시 검증은 두 조회 모두 유지하며, 근거를 생략한 응답의 빈 evidence는 근거가 없다는 판정이 아니다. 확인 횟수만 필요한 문서 표는 `/api/documents/{id}/provenance?include_evidence=false`를 사용한다. 매번 모든 PDF를 다시 추출하는 기본 조회는 화면 목록에서 사용하지 않는다. 기존 API의 쿼리를 생략하면 전체 근거를 반환하는 규격은 유지한다.

## 사람 확인과 후보

필드 수정 API는 생략한 값을 유지하고 명시 null을 그 칸의 삭제로 처리한다. 실제 변경한 칸과 confirmed_fields로 명시한 칸만 사람 확인 기록을 만든다. 전체 폼 저장으로 모든 필드를 확인했다고 표시하지 않는다.

`POST /api/documents/{id}/confirm-field`는 `{field, revision}`으로 한 항목만 확인한다. 비어 있는 값·이전 본·없는 원본·오래된 revision·중복 확인을 거부한다. `0`은 유효한 값이다. 성공 응답의 field/revision/confirmed_at을 10초 되돌리기 버튼에 사용한다.

`POST /api/documents/{id}/undo-field-confirmation`은 `{field, revision, confirmed_at}`을 받는다. 서버에서는 같은 사용자·같은 EXPLICIT_CONFIRMATION 기록·현재 revision·60초 이내인지 확인한다. 그 항목의 확인만 없애고 값·다른 확인·처리 기록은 유지한다. revision은 증가하며 과거 결재를 되살리지 않는다. 수동 값 수정이나 AI 후보 반영을 취소하는 API가 아니다.

VLM 생성은 후보만 저장하며 검사·결재·추출값을 바꾸지 않는다. 확인 POST는 서버의 run_id 후보를 읽고 원본 SHA·revision·fingerprint를 다시 비교한다. 원문 대조 동의·선택한 필드·확인 사유가 필요하다. 민감 항목만 가림 해제가 필요하고 금액·날짜는 가림 ON에서도 현재 원문 표시 후 확인 가능하다. 저장 중에는 서류·탭·페이지 이동을 막는다.

후보의 `changed`는 서버가 가리기 전에 원래 값과 정규화 비교한 결과다. 프론트엔드는 이 값을 우선하며 `[가림]`을 다시 부분 가림하지 않는다. 후보 반영 후 현재 읽은 값과 VLM_ORIGINAL_CONFIRMED 출처·확인 이력을 보여 준다. 자동 검사와 사람의 원문 확인을 서로 대신 표시하지 않는다.

현재 원문 대조의 기준은 [실제 앱 사용자 흐름](../ux/current_review_flow.md)이다. 4187·4188 같은 포트 번호는 개발 당시 시안 주소이며 실행 환경이나 최신 앱 명세로 사용하지 않는다.

## 반려·요청 초안·수정본

대표 반려는 기존 `api.review`의 RETURNED로 보내고 승인 단계는 approvals API를 사용한다. 실패 시 입력 의견을 보존한다. 서류 종류 정정은 기존 필드 정정 API에 변경할 종류와 사유·현재 revision을 전달한다.

요청 초안은 같은 브라우저 탭의 sessionStorage에 선택 키·원문 확인 여부·revision/fingerprint만 보존한다. 실제 값과 요청 문구는 저장하지 않으며 자료 기준이 바뀌면 이전 선택을 자동으로 재사용하지 않는다. 회신 대기·반려·보류 상태의 다음 행동은 각각 요청 내역·결재 이력·보류 항목으로 연결한다.

수정본 요약은 compare API의 현재 저장 필드 비교 결과를 사용한다. 원본 전체 문장·그림을 비교하는 기능이 아니다. 선택한 값으로 이동할 수 있으며 첫 본에는 이전 본 요약이 없다. 실행된 AI의 값이 모두 같으면 완료·변경 없음 안내를 표시한다.

## 사용자가 실제로 확인할 것

요청 문구 복사는 발송·기록과 구분한다. 받은 항목 선택은 자동 검사와 구분한다. 대표 최종 확인은 회사 정책의 현재 역할과 실제 차례를 따른다. 지급은 은행 송금이 아니라 완료 사실 기록이다. 정산 XLSX는 ERP 전용 업로드 호환을 보장하지 않는다.

화면 검증은 [UI 변경 예시](../development/recipes/change_ui.md), API 변경은 [API 예시](../development/recipes/change_api.md)를 따른다. 세부 응답은 [공통 상태·추가 API](work_system.md)와 날짜별 인계 기록에서 읽는다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)


## 등록 재시도와 계약 복원 (2026-10-09)

배치 등록 multipart에는 파일 순서에 맞는 document_types JSON 배열, idempotency_key, amount_basis, tax_amount, payment_mode를 전송한다. 선택한 서류 종류를 적용하되 자동 분류와 차이가 있으면 분석 경고를 남긴다. 등록을 시도하는 동안 같은 요청 키와 내용을 유지한다. partial 응답도 계약 ID를 반환하며 registration.complete=false, failed_files 목록을 확인한다. 재시도는 같은 계약에서 완료하지 못한 파일만 처리한다. 새 내용을 같은 키로 보내면 409다.

DELETE /api/contracts/{id}는 이제 제외 표시를 만들며 업무 기록은 보존한다. GET /api/contracts/excluded로 목록 조회, POST /api/contracts/{id}/restore와 note(3자 이상)로 복원한다. 일반 목록·검색·맡은 일은 제외한 계약을 숨기며, 제외한 계약의 일반 API는 복원 전 404다. 이전 DELETE로 이미 삭제된 계약을 되살리는 기능은 아니다.


### 판독 실패와 복원 경계 보강

배치 등록은 원본 바이트 저장과 판독 완료를 구분한다. 실제 OCR 예외·빈 본문·읽을 수 없는 PDF는 registration.complete=false와 해당 failed_files를 반환하며 성공 receipt나 새 활성 문서를 만들지 않는다. 원본 바이트는 보관되고 같은 키 재시도에서 실패한 파일만 다시 판독한다. 이미 게시된 성공 문서는 응답 유실·receipt 저장 중단 뒤에도 재사용한다. 이전 버전에서 FAILED 문서를 성공 receipt로 저장한 경우에는 동일 원본을 새 문서 버전으로 판독하고 실패 원본·기존 이력을 보존한다. 그 실패 문서가 이미 사람이 등록한 새 원본으로 대체되었으면 같은 문서 계보의 현재 성공본을 사용하고 이전 파일을 다시 게시하지 않는다.

제외한 계약의 업로드 작업 GET /api/pilot/document-jobs/{job_id}와 POST /api/pilot/document-jobs/{job_id}/retry도 복원 전 404다. 제외 표시 후 새 작업·재시도는 수락하지 않는다. 이미 큐에 있거나 판독 중인 작업은 게시 직전 제외 여부를 다시 확인한다. 제외를 발견하면 FAILED/NOT_FOUND로 남고 원본·job_id는 유지된다. 복원한 뒤 작업을 다시 조회하여 최신 job_revision 및 contract_revision으로 재시도한다. 제외 전에 게시된 문서는 지우지 않으며, 그 작업의 복구는 기존 문서 자동 검사만 다시 수행한다. 일반 직접 업로드도 분석 중 제외되면 게시하지 않고 404를 반환한다.

지급 등록은 별도의 payment_revision·idempotency_key를 포함한다. 취소된 지급을 실제 내역 확인 후 다시 등록할 때만 새 요청 키와 acknowledge_new_payment=true를 보낸다. 세부 오류·재전송 규칙은 [지급 완료 사실 기록 API](payment_record.md)를 따른다.

## 검토 완료·상신의 저장 계약

`POST /api/pilot/contracts/{id}/submission`은 담당자/관리자만 호출한다. 현재 revision·fingerprint·review_cycle, idempotency_key, note를 전달한다. 예외가 있을 때는 전체 exception_items, acknowledge_exception과 10자 이상의 exception_reason을 함께 보낸다. 저장은 기존 AuditEvent의 CONTRACT_SUBMITTED이며 업무 DB 테이블을 추가하지 않는다.

상세 workflow.submission은 상태, current, 상신 이력과 gate를 반환한다. gate에는 원본 해시·처리 실패·전체 판독·필수 서류·현재 필드 확인·보류·회신 대기와 업무상 예외를 구분한다. 목록과 상세의 work_state는 같은 판정을 사용한다. 조회가 OCR/모델을 다시 실행하지 않으며 제출 시 외부 검사가 활성화된 경우 별도로 평가한다.

대표 승인/반려는 현재 review_cycle과 submission_event_id도 보낸다. 단일 대표와 2단계 모두 서버의 현재 상신·회사 차례를 확인한다. 반려 후 값이 같아도 최신 차수의 상신이 필요하다. 동일 요청 키·내용의 상신 재시도는 중복 저장하지 않으며 다른 내용·권한·오래된 자료·차수는 거부한다.
