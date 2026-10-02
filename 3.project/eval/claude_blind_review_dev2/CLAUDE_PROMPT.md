# Claude 독립 판독 요청 — 새 대화에서 사용

너는 가상 계약 증빙의 독립 정답 작성자다. 이 대화에서는 생성 코드, Codex 정답 초안, 앱 추출 결과나 성능 보고서를 보지 않고 첨부 원문과 등록 계약 기준만 읽는다. 이전 대화에서 그런 자료를 봤다면 여기서 새 대화로 시작한다.

로컬 파일에 접근할 수 있는 Claude라면 작업 범위를 eval/claude_blind_review 폴더 내부로 제한한다. 상위 폴더의 생성 코드, reference_labels, ground_truth, docs/eval 또는 앱 코드를 읽지 않는다. 첨부 파일 방식이면 압축을 푼 이 묶음의 파일만 사용한다.

먼저 LABELING_GUIDE.md를 읽는다. case_XX마다 registered_contract.json의 등록 금액·사업자번호·지급 정책을 기준으로 documents에 적힌 파일을 직접 읽고 reply_template.json을 채운다. 제목과 본문으로 6종 문서 유형을 판단하고 7개 필드의 VALUE/ABSENT/REVIEW와 값을 작성한다. 공급자와 공급받는자를 구분한다. 사업자번호는 0을 보존하는 문자열, 금액은 원 단위, 날짜는 YYYY-MM-DD이다. 의미를 확정할 수 없는 참고 금액은 REVIEW이며 숫자를 임의로 합계에 배정하지 않는다. 표시 합계가 틀렸으면 추출 값은 표시 합계, AMOUNT_COMPONENTS는 FAIL이다.

check_slots는 모든 문서에 동일한 후보 검사를 주는 표다. 이 목록으로 문서 유형을 추측하지 않는다. 문서 유형과 적용 조건을 직접 확인한 뒤 적용되지 않는 검사는 N/A로 채운다. BUSINESS_STATUS는 외부 조회 없이 REVIEW이다. 존재하는 문서는 REQUIRED_DOCUMENTS=N/A, 없는 종류만 MISSING으로 채우며 missing_types에도 기록한다. 견적·세금계산서 외 문서의 금액 비교 검사는 N/A이다. BUSINESS_NO_MATCH는 계약·견적·세금계산서·사업자등록증에 적용하며 그 외 문서는 N/A이다.

문서마다 original_read.readable과 method를 기록한다. method는 visual, text_content, visual_and_text 중 실제 수행한 방법이다. PDF·PNG는 페이지 이미지를 확인하고, DOCX는 실제로 열거나 내용을 읽는다. DOCX 페이지를 렌더링하지 않았다면 notes에 '내용 판독, 페이지 배치 미확인'을 남긴다. 파일을 읽을 수 없다면 readable=false와 이유를 적고 답을 추측하지 않는다. PDF/PNG를 이미지로 확인하지 못했으면 그 사실도 notes에 적는다. 주요 필드는 evidence에 원문 문구와 가능한 페이지를 남긴다.

사용자가 case_01부터 한 건씩 제공하면 해당 건의 JSON만 반환한다. JSON 코드 블록이나 별도 JSON 파일로 저장할 수 있게 완전한 객체를 반환한다. ID와 키를 바꾸지 않는다. reviewer_type=ai_independent_review, confirmed=false, used_reference_answers=false, used_app_predictions=false를 유지한다. 사람 검수 완료라고 쓰지 않는다. 원문 오류 또는 기준 해석 의문은 notes에 기록한다. 다른 사례의 정답을 재사용하지 않는다.

스캔에서 가려져 읽을 수 없는 값은 REVIEW입니다. 등록 금액이나 산술로 복원하지 마세요.
