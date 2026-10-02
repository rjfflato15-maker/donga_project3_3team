# 로컬 LLM 구현 작업 기록

이 문서는 해당 작업 당시의 기록이다. 현재 상태는 [진행 요약](../development_report.md)을 확인한다.

## 로컬 LLM 보완과 근거 검증 구현

2026년 10월 2일 Ollama 로컬 클라이언트와 보수적인 근거 검증을 추가했다. 설치 qwen3:latest는 8.2B Q4_K_M 약 5.23GB, gemma3:latest는 4.3B Q4_K_M 약 3.34GB이며 RTX 4070 Laptop 8GB 환경에서 비교했다. 약 9.61GB인 gemma4는 제외했다. Ollama 0.35.0의 클라우드 설정을 비활성화하고 실제 재시작 서버 로그의 cloud disabled=true를 확인했다. HTTP loopback와 설치된 허용 모델만 사용하며 문서의 외부 API 전송은 추가하지 않았다. 원문이나 응답 내용을 로그에 출력하지 않는다. 기존 WinOCR 실패 출력도 예외 본문을 빼고 고정 실패 메시지만 남겨 문서 정보가 예외를 통해 출력되지 않게 했다.

최종 프롬프트는 grounded-fields-v3다. 첫 dev 시도에서 상태·근거 문구 누락과 페이지 번호를 줄 번호로 답하는 문제가 나와, 필드 의미와 VALUE/REVIEW 정의를 명시하고 각 원문 줄에 page/line을 함께 붙였다. v2 비교와 버전별 원본 응답도 보관했다. 이는 dev를 사용한 프롬프트 개선이며 test 성능을 확인한 것이 아니다. qwen3와 gemma3의 사전 지정 dev 8문서를 같은 v3로 비교했다. qwen3의 가드 없는 필드 정확도는 46/48(95.83%), 가드를 적용한 LLM만 추출은 36/48(75.00%), 최초 호출 평균은 10.430초였다. gemma3는 각각 37/48(77.08%), 25/48(52.08%), 8.132초였으며 1문서의 형식 오류가 있었다. 가드 적용 정확도, 원본 정확도, 시간 순 기준으로 qwen3를 선택했다. 이 작은 8문서 결과는 모델의 일반적인 우열이나 전체 dev 성능이 아니다. DOCX 페이지 미확인과 잘못된 근거 위치 때문에 실제 값도 거부될 수 있으며, LLM만 가드 결과에는 규칙 보존이 없다.

설정은 읽기 타임아웃 45초·연결 5초·재시도 1회, temperature 0·seed 42·num_ctx 4096·num_predict 1600·keep_alive 5분이며 qwen3는 think=false다. JSON 스키마와 응답 타입을 검사한다. 모델 digest·설정·프롬프트 버전도 저장한다. 최초 로딩과 재시도 시간은 원래 호출시간에 포함한다. 실행법과 한계는 `docs/eval/local_llm_runbook.md`에 기록했다. [Ollama 구조화 출력](https://docs.ollama.com/capabilities/structured-outputs), [클라우드 비활성화](https://docs.ollama.com/faq), [thinking 설정](https://ollama.com/blog/thinking)을 확인했다.

규칙값이 비었거나 원문 후보·당사자·산술과 모순인 필드에만 LLM을 호출한다. 성공한 규칙 필드 전체를 LLM으로 덮어쓰지 않는다. VALUE 제안은 실제 페이지·줄·원문 오프셋, 값의 존재, 필드 라벨, 공급자 구역, 후보 모호성, 형식과 사업자번호 체크섬을 검사한다. 채택·거부 사유는 `analysis.ai_review`와 기존 추출 JSON에 저장해 API에서 제공한다. 원문 존재·위치는 PDF 텍스트와 OCR 문자열을 기준으로 확인하며 이미지의 OCR 오독과 픽셀 좌표 강조는 검증하지 않는다. 모든 AI 채택은 사람 확인 전이며 기존 담당자 추출 확인 API 이후에만 사람 확인 상태를 기록한다. 타임아웃·서버 중단·형식 오류는 규칙값과 실패 코드를 남기고 수동 확인으로 이어진다.

참고값 A/B는 REVIEW로 보류한다. 원문에 잘못 계산된 합계가 있으면 표시값을 보존하고 SOURCE_ARITHMETIC_MISMATCH를 기록한다. 기존 RuleEngine이 산술과 계약 일치를 판정하며 LLM은 PASS/FAIL을 정하지 않는다. DOCX는 실제 페이지를 확인할 렌더러가 없어 VALUE 제안을 PAGE_UNVERIFIED로 거부하고 규칙값을 유지한다. 이 가드가 기존 규칙값까지 검증했거나 모든 의미·OCR 오류를 해결했다고 주장하지 않는다.

Qwen3-8B의 Apache-2.0 라이선스와 상업적 사용·배포 조건은 [공식 LICENSE](https://huggingface.co/Qwen/Qwen3-8B/blob/main/LICENSE)에서 확인했다. Gemma3는 별도의 [이용 약관](https://ai.google.dev/gemma/terms)과 [금지 사용 정책](https://ai.google.dev/gemma/prohibited_use_policy)에 따른다. 상업적 사용도 이 조건을 따라야 하며 배포 시 약관·제한·수정 표시·해당 Notice 조건이 있다. Gemma4 라이선스를 Gemma3에 적용하지 않는다. 모델 가중치는 제출 소스나 커밋에 넣지 않았다.

이번 단계에서도 프런트 화면과 디자인은 변경하지 않았다. AI 근거 표시 화면을 승인받기 전이므로 APP_LLM_ENABLED는 기본 false다. 비교 CLI는 앱 활성화와 별개로 실제 로컬 추출을 실행한다.

[진행 요약](../development_report.md)
