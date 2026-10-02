# 로컬 LLM 설정

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

[LLM·평가 문서 목록](local_llm_runbook.md)
