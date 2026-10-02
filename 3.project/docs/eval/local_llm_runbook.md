# 로컬 LLM 실행과 비교 평가

LLM은 규칙 추출이 비었거나 원문 후보·금액 구성과 모순되는 핵심 필드를 보완한다. 일치·불일치와 PASS/FAIL 판정은 기존 RuleEngine이 한다. 앱 화면은 변경하지 않았고 AI 근거·거부 사유·확인 필요 상태는 백엔드의 `analysis.ai_review`에 준비했다. 화면에서 이를 표시하는 작업은 이미지 시안과 사용자 승인 뒤에 진행한다.

## 로컬 실행 설정

앱은 기본적으로 `APP_LLM_ENABLED=false`이다. AI 추출 표시와 검토 흐름을 화면에서 확인하기 전에는 자동으로 켜지 않는다. 백엔드 동작을 확인하려면 앱 실행 환경에 다음 값을 지정하고 백엔드를 다시 시작한다. `APP_LLM_MODEL`은 아래 비교 결과에서 선택한 모델을 지정한다.

```powershell
$env:APP_LLM_ENABLED='true'
$env:APP_OLLAMA_URL='http://127.0.0.1:11434'
$env:APP_LLM_MODEL='qwen3:latest' # 선택 모델은 model_comparison.json 참고
$env:APP_LLM_TIMEOUT='45'
```

클라이언트는 HTTP loopback 주소, 설치된 qwen3/gemma3 모델만 허용하고 cloud 태그·원격 모델·리디렉션·환경 프록시를 사용하지 않는다. 원문, 모델 답변, HTTP 예외 내용을 로그에 출력하지 않는다. 실제 앱의 근거는 기존 접근 제어가 적용되는 추출 JSON에 저장한다. CLI의 원문 응답 캐시는 이번 합성 평가셋에서만 저장한다.

2026년 10월 2일 Ollama 0.35.0의 기존 클라우드 설정이 켜져 있음을 확인했다. 사용자 요청 범위에서 `%USERPROFILE%/.ollama/server.json`의 기존 항목을 보존하며 `disable_ollama_cloud`를 true로 설정하고 재시작했다. Ollama 데스크톱 감독 프로세스가 서버를 재시작했으며 실제 서버 로그의 `Ollama cloud disabled: true`를 확인했다. 백엔드도 실행 계정의 이 설정이 true가 아니면 추출 요청을 거부한다. 다른 실행 계정·서비스 계정을 사용하면 해당 계정의 설정을 별도로 확인해야 한다. 설정과 재시작 확인 방법은 [Ollama 공식 FAQ](https://docs.ollama.com/faq)에 있다.

```json
{"disable_ollama_cloud": true}
```

단순히 설정 파일을 바꾸는 것만으로 실행 중인 서버가 바뀌지는 않는다. Ollama를 재시작하고 실제 서버 로그를 확인한다. 이 확인은 클라우드 기능 비활성화의 근거이며 PC 전체 네트워크를 감사한 기록은 아니다.

요청당 읽기 타임아웃 45초, 연결 타임아웃 5초, 재시도 1회(총 2회), temperature 0, seed 42, num_ctx 4096, num_predict 1600, keep_alive 5분을 사용한다. qwen3는 think=false다. 필드별 상태·값·페이지·줄·원문을 JSON 스키마로 요청하고 응답 타입도 검사한다. 원문 10,000자 초과는 `INPUT_TOO_LONG`으로 넘긴다. 타임아웃·형식 오류·설정 오류 시 규칙 결과를 보존하고 실패 코드와 수동 확인 필요 상태를 남긴다. 최초 모델 로딩은 타임아웃과 처리시간에 영향을 줄 수 있다. 이러한 설정은 재현을 돕지만 하드웨어·모델 버전이 달라져도 같은 출력이 나온다는 보증은 아니다. [구조화 출력](https://docs.ollama.com/capabilities/structured-outputs), [thinking 설정](https://ollama.com/blog/thinking)을 참고했다.

## 근거 검증의 범위

각 제안에 실제 페이지, 줄, 원문 문자 오프셋과 문구를 연결한다. 여기서 존재 확인은 PDF 텍스트·OCR 문자열 기준이며 이미지 자체의 OCR 오독 검증이나 픽셀 좌표 강조는 구현하지 않았다. 금액·날짜·사업자번호의 정규화, 필드 라벨, 공급자 구역, 복수 후보, 사업자번호 체크섬을 검사한다. 단순 원문 포함만으로 채택하지 않는다. 참고값 A/B는 의미를 확정하지 않고 REVIEW로 둔다. DOCX는 문서 내용만 읽을 수 있어 실제 페이지를 검증할 수 없으며 VALUE 제안을 `PAGE_UNVERIFIED`로 거부한다. 규칙 결과까지 검증된 것으로 바꾸지는 않는다.

원문 합계가 공급가액+세액과 다를 때는 `SOURCE_ARITHMETIC_MISMATCH`를 남긴다. 원문에 적힌 합계를 추출 정답으로 보존하며 산술 불일치의 FAIL은 RuleEngine에 맡긴다. 검증기는 원문 오류를 올바른 금액으로 고치는 도구가 아니다. OCR 자체 오류, 복잡한 표·라벨, 의미 판단에는 한계가 남는다. AI 채택값도 `human_confirmed=false`, `manual_review_required=true`로 저장한다. 기존 담당자 추출 수정 API로 사람이 확인한 뒤에만 사람 확인 상태를 기록한다.

## 확정 dev 평가

프로젝트 루트에서 실행한다. 모델 선택은 dev의 사전 지정 8문서(6개 기본 형식·종류와 모호 금액·산술 오류 사례)로 비교하며 전체 59문서 비교가 아니다. 원문만 프롬프트에 넣고 정답 값이나 등록 계약 값은 넣지 않는다. 프롬프트 v1·v2의 출력 문제를 dev에서 확인해 v3에 줄마다 page/line 번호와 필드 의미를 명시했다. 최종 선택과 네 조건 비교에는 같은 v3를 사용한다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/compare_llm_modes.py
```

선택 기준은 가드 적용 필드 정확도, 가드 없는 필드 정확도, 최초 실제 호출시간 순이다. 결과와 선택 모델은 `docs/eval/dev/comparison/model_comparison.json`에 남는다. 네 조건은 규칙만, LLM만, 규칙+LLM 가드 없음, 규칙+LLM 가드 있음이다. LLM만은 핵심 7개 필드의 추출만을 뜻하며 분류와 최종 검수 엔진은 모든 조건에서 같다. 규칙 필드가 성공한 경우 hybrid는 다시 요청하지 않는다.

③과 ④는 같은 문서별 response_id의 응답을 재사용한다. 캐시 키는 OCR 원문, 요청 필드, 모델 digest, 설정, 프롬프트 버전에 의존하며 응답 해시 변조를 차단한다. 다른 모드의 재실행도 캐시를 재사용한다. `four_modes.json`, `four_modes.md`, `four_modes.csv`와 문서별 `extraction_evidence.json`에 결과를 저장한다. 최초 LLM 호출시간과 캐시 재실행시간은 따로 기록한다. 표의 문서 시간은 공통 분류·OCR·원문 페이지 확보 시간+최초 LLM 호출시간+해당 가드 시간이며 계약 검수와 사람 확인 시간은 제외한다. 가드 없는 조건에서도 사후 분석을 위해 거부 사유를 계산하지만 그 진단 비용은 해당 운영 조건의 시간에서 제외한다.

핵심 필드 정확도는 VALUE+REVIEW 정답 337칸을 분모로 유지한다. ABSENT 76칸의 거짓 추출률은 별도로 남긴다. 검수 정확도는 정답·출력의 적용 항목 합집합으로 계산하고 양쪽 N/A는 제외한다. 누락·추가 검수 결과는 오답이다. 가드 거부는 제안 수이고 사유 수는 한 제안의 여러 사유로 더 클 수 있다. 산술 경고도 제안별 기록이며 서로 다른 오류 문서 수와 다르다.

정답은 사람 확인 113칸(해석 26칸+일치 항목 10% 표본 87칸)과 두 AI 초안 일치 781칸을 구분한 확정 dev 자료다. 이 결과는 예비 정답에 대한 수치가 아니지만 dev 개발 평가이며 최종 test 성능이 아니다. test 문서·정답은 개발과 모델 선택에 사용하지 않았다.

## 최종 test 실행 준비

test의 독립 판독·사람 확인·정답 확정은 별도 단계다. 그것을 마친 뒤에만 아래 명령을 사용한다. `--final`과 dev에서 고정한 모델 없이 test 실행을 요청하면 test 정답이나 문서를 읽기 전에 거부한다. 모델 이름·설치 digest·프롬프트·가드 버전도 dev 선택 기록과 비교한다. test에서 모델 비교나 프롬프트 튜닝은 허용하지 않는다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/compare_llm_modes.py --split test --final --selected-model <dev에서_선택한_모델>
```

현재 이 명령으로 실제 test는 실행하지 않았다. 결과 기본 경로는 `docs/eval/test/final/`이다.

## 모델과 라이선스

설치 모델은 qwen3:latest 8.2B Q4_K_M(파일 약 5.23GB)과 gemma3:latest 4.3B Q4_K_M(약 3.34GB)이다. GPU는 RTX 4070 Laptop 8GB이며 설치된 gemma4 약 9.61GB 모델은 이번 비교 대상에서 제외했다. 선택 모델은 qwen3:latest다. 모델 파일 크기와 실제 GPU 메모리 사용량은 다르다. 태그가 바뀔 수 있어 선택 결과에 모델 digest를 저장한다.

Qwen3-8B는 Apache-2.0으로 상업적 사용이 가능하며 배포 시 라이선스·고지 등 해당 조건을 지켜야 한다. [Qwen 공식 LICENSE](https://huggingface.co/Qwen/Qwen3-8B/blob/main/LICENSE)를 확인했다. Gemma3-4B는 Apache-2.0으로 단정하지 않는다. 상업적 사용을 포함한 사용·수정·배포는 Gemma 이용 약관과 금지 사용 정책 조건에 따른다. 배포 시 약관 제공, 사용 제한 전달, 수정 표시 및 해당되는 Notice가 필요하다. 이번 제출 저장소에는 모델 가중치를 포함하지 않는다. [Gemma3 공식 모델 카드](https://huggingface.co/google/gemma-3-4b-it), [이용 약관](https://ai.google.dev/gemma/terms), [금지 사용 정책](https://ai.google.dev/gemma/prohibited_use_policy)를 확인했다. Gemma4의 별도 라이선스를 Gemma3에 적용하지 않는다.
