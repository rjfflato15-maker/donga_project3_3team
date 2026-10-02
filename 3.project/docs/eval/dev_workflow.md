# dev 비교와 동일 응답 감사

프로젝트 루트에서 실행한다. 모델 선택은 dev의 사전 지정 8문서(6개 기본 형식·종류와 모호 금액·산술 오류 사례)로 비교하며 전체 59문서 비교가 아니다. 원문만 프롬프트에 넣고 정답 값이나 등록 계약 값은 넣지 않는다. 프롬프트 v1·v2의 출력 문제를 dev에서 확인해 v3에 줄마다 page/line 번호와 필드 의미를 명시했다. 최종 선택과 네 조건 비교에는 같은 v3를 사용한다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/compare_llm_modes.py
```

선택 기준은 가드 적용 필드 정확도, 가드 없는 필드 정확도, 최초 실제 호출시간 순이다. 결과와 선택 모델은 `docs/eval/dev/comparison/model_comparison.json`에 남는다. 네 조건은 규칙만, LLM만, 규칙+LLM 가드 없음, 규칙+LLM 가드 있음이다. LLM만은 핵심 7개 필드의 추출만을 뜻하며 분류와 최종 검수 엔진은 모든 조건에서 같다. 규칙 필드가 성공한 경우 hybrid는 다시 요청하지 않는다.

③과 ④는 같은 문서별 response_id의 응답을 재사용한다. 캐시 키는 OCR 원문, 요청 필드, 모델 digest, 설정, 프롬프트 버전에 의존하며 응답 해시 변조를 차단한다. 다른 모드의 재실행도 캐시를 재사용한다. `four_modes.json`, `four_modes.md`, `four_modes.csv`와 문서별 `extraction_evidence.json`에 결과를 저장한다. 최초 LLM 호출시간과 캐시 재실행시간은 따로 기록한다. 표의 문서 시간은 공통 분류·OCR·원문 페이지 확보 시간+최초 LLM 호출시간+해당 가드 시간이며 계약 검수와 사람 확인 시간은 제외한다. 가드 없는 조건에서도 사후 분석을 위해 거부 사유를 계산하지만 그 진단 비용은 해당 운영 조건의 시간에서 제외한다.

핵심 필드 정확도는 VALUE+REVIEW 정답 337칸을 분모로 유지한다. ABSENT 76칸의 거짓 추출률은 별도로 남긴다. 검수 정확도는 정답·출력의 적용 항목 합집합으로 계산하고 양쪽 N/A는 제외한다. 누락·추가 검수 결과는 오답이다. 가드 거부는 제안 수이고 사유 수는 한 제안의 여러 사유로 더 클 수 있다. 산술 경고도 제안별 기록이며 서로 다른 오류 문서 수와 다르다.

정답은 사람 확인 113칸(해석 26칸+일치 항목 10% 표본 87칸)과 두 AI 초안 일치 781칸을 구분한 확정 dev 자료다. 이 결과는 예비 정답에 대한 수치가 아니지만 dev 개발 평가이며 최종 test 성능이 아니다. test 문서·정답은 개발과 모델 선택에 사용하지 않았다.

### v3의 동일 응답 감사 재생

다음 명령은 새 LLM 추출을 호출하지 않는다. v2의 원문·요청 필드·프롬프트·모델 digest·설정 및 응답 해시가 같아야 재생하며, 캐시가 없으면 중단한다. DOCX의 구조 위치는 모델에게 보이는 문자열을 바꾸지 않는다. 이번 dev 59문서는 현재 v3 대상 선정과 기존 요청 대상도 같았다. 원래 호출시간은 유지하고 가드 시간만 다시 측정한다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/compare_llm_modes.py --selected-model qwen3:latest --cache docs/eval/dev/comparison/llm_cache --replay-evidence docs/eval/dev/comparison/extraction_evidence.json --output docs/eval/dev/guard_v3
backend/.venv/Scripts/python.exe backend/scripts/audit_guard_replay.py
```

`guard_audit.{json,md,csv}`는 기존 맞는 값 거부 27건의 원인, 기존 오답 2건의 계속 거부 여부, 이전에 채택됐던 불일치도 함께 기록한다. 채택 VALUE 정답 일치율은 68/69(98.55%), 요청 필드 추가 확인 비율은 11/80(13.75%), 기계 근거 검증 완료율은 69/80(86.25%)다. 전체 문서 추가 확인 비율은 5/59(8.47%)이며, LLM 호출 문서에서 추가 확인 없이 근거 검사가 완료된 비율은 23/28(82.14%)다. LLM을 호출하지 않은 31문서를 가드가 검증했다고 주장하지 않는다. 거부 11건 중 6건은 정답과 일치하지만 근거가 부족하고, 5건은 값·상태가 정답과 불일치한다. 운영 시에는 모두 사람 추가 확인으로 넘긴다. 기존에 채택된 OCR 회사명 오독 1건은 남아 있다.

[LLM·평가 문서 목록](local_llm_runbook.md)
