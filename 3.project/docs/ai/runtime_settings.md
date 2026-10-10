# 실행 모드와 AI 설정 기준

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [config.py](../../backend/app/config.py) · [local_llm.py](../../backend/app/ai/local_llm.py) · [local_vlm.py](../../backend/app/ai/local_vlm.py) · [environment.py](../../backend/launcher/environment.py) · [settings.py](../../backend/launcher/settings.py)

## 실행 경로별 차이

| 경로 | 설정 기준 |
| --- | --- |
| 직접 uvicorn 개발 실행 | 시작 전 지정한 환경 변수와 config의 dotenv 로딩 |
| 소스 폴더의 통합 실행기 | `storage/launcher/settings.json`. 자료·백업 기본값은 소스 아래 |
| 설치형 실행기 소스 | 번들 Python 존재 시 사용자별 `%LOCALAPPDATA%/C-Pilot`. 이번 소스 ZIP에는 설치 EXE 없음. [설치 검증 범위](../operations/customer_package.md) 참조 |

직접 실행에서는 backend/.env, backend/env, 루트 .env를 override=false로 읽는다. pilot DB는 APP_STORAGE_ROOT의 SQLite로 고정된다. 개발·검증에는 [분리 실행 환경](../development/getting_started.md)을 사용한다.

## 직접 실행의 주요 변수

| 변수 | 코드 기본값·의미 |
| --- | --- |
| APP_DEPLOYMENT_MODE | development. 사용자 업무함은 pilot을 명시 |
| APP_STORAGE_ROOT | 모드별 자료 위치. 개발 시 별도 폴더를 명시 |
| APP_NTS_MODE | pilot에서 disabled, 개발에서 demo. 시연·평가에는 disabled 명시 |
| APP_LLM_ENABLED | false. 문서 업로드의 텍스트 보완 활성화 |
| APP_LLM_MODEL | qwen3:latest |
| APP_LLM_TIMEOUT | 읽기 45초, 연결 5초. 재시도 1회 |
| APP_LLM_GUARD_POLICY | v3. v4 고정 평가 결과가 있다고 실행 기본 정책도 v4라는 뜻은 아님 |
| APP_VLM_ENABLED | true. 사용자 버튼으로만 이미지 재판독 |
| APP_VLM_MODEL | qwen2.5vl:7b |
| APP_VLM_TIMEOUT | 읽기 90초, 연결 5초. 입력 범위 1~120초 |
| APP_OLLAMA_URL | http://127.0.0.1:11434. 승인된 로컬 모델·loopback만 허용 |
| APP_ALLOWED_ORIGINS | 기본 localhost/127.0.0.1의 5173·8000 주소. 포트 변경 시 확인 |
| APP_COOKIE_SECURE | false. HTTPS 배포에서 적용 조건 확인 |

현재 통합 실행기는 `llm_enabled`(기본 false), `vlm_enabled`(기본 true)를 환경 변수로 전달한다. 실행기에서는 모델명과 Ollama 주소를 위 기본 모델·loopback 주소로 지정하므로 외부 환경 변수만 바꿔 모델이 바뀌었다고 가정하지 않는다. 설정 파일을 변경할 때는 해당 업무함 서버를 종료하고 다시 시작한다. 직접 uvicorn 실행은 APP_LLM_MODEL/APP_VLM_MODEL 설정을 사용할 수 있다.

[설정 예시](../../backend/.env.example)는 로컬 pilot·외부 조회 없음·AI 비활성 상태에서 시작한다. 실제 `.env`와 DB 계정은 제출하지 않는다. 예시의 직접 실행 설정과 EXE의 settings.json 우선순위를 혼용하지 않는다.

```powershell
# 직접 실행 시 텍스트 보완 활성화 예시
$env:APP_LLM_ENABLED='true'
$env:APP_LLM_MODEL='qwen3:latest'
$env:APP_VLM_ENABLED='true'
$env:APP_VLM_MODEL='qwen2.5vl:7b'
$env:APP_OLLAMA_URL='http://127.0.0.1:11434'
```

설치된 Ollama·모델과 실행 계정의 `~/.ollama/server.json`에 disable_ollama_cloud=true 설정이 필요하다. 설정 변경 뒤 실행 중인 Ollama에 적용하려면 재시작과 실제 상태 확인이 필요하다. 앱 서버 재시작은 Ollama 재시작과 별개다. 원문·모델 답변·HTTP 예외를 로그로 출력하지 않는다. 로컬 실행은 외부 AI 서비스 전송을 줄이는 설계이며 PC 전체의 유출 가능성이 0이라는 보증은 아니다.

## AI 설치 자동화의 검증 범위

관리 메뉴 10번/`setup-ai`는 Ollama·모델 준비 후 활성화를 저장하도록 작성된 초안이다. 부분 단위 테스트만 확인했으며 새 PC의 다운로드·클라우드 설정 적용·재시작·복구 검증은 남았다. 현재 고객용 설치 완료 절차로 사용하지 않는다. 개발자는 승인된 Ollama 설치와 모델 준비를 별도로 확인한다.

시연·회귀 테스트에서는 APP_LLM_ENABLED=false, APP_VLM_ENABLED=false, APP_NTS_MODE=disabled를 명시하여 실시간 추론을 섞지 않는다. 기존 평가의 모델·프롬프트·설정은 [고정 평가 문서](../eval/local_llm_runbook.md)에서 당시 기준으로 보존한다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
