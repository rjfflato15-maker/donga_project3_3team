# 대시보드 문제 수와 국세청 미연동 표시

GET `/api/contracts`에 `open_issue_count`를 추가했다. FAIL·MISSING·REVIEW 검사 수를 더하되 NTS disabled의 BUSINESS_STATUS REVIEW는 제외한다. 목록과 `review-context`의 두 `action_summary`도 같은 표시 집계를 사용한다. API 실패·데모 조회 REVIEW, BUSINESS_STATUS FAIL 및 다른 미확인 항목은 계속 센다.

상세 원래 `summary`, 모든 `checks`, `review_status`와 검수 판정은 변경하지 않았다. 미연동을 PASS로 처리한 것은 아니다. 회신 대기·결재·AI 확인은 원래 별도 수를 유지하며 문제 수에 중복 합산하지 않는다. 목록 조회의 원문 읽기·OCR·LLM 호출과 고정 평가 스키마 변경도 없다.

관련 API **34개 테스트 통과**. 두 요약의 일치·목록 문제 수, 미연동 제외와 다른 REVIEW 유지, API/데모 모드·BUSINESS_STATUS FAIL 유지, 상세 검사 보존을 검증했다. `frontend/`는 직접 수정하지 않았다.

[API 인계](../../api/frontend_handoff.md)
