# 최종 test 실행 조건

test의 독립 판독·사람 확인·정답 확정은 별도 단계다. 그것을 마친 뒤에만 아래 명령을 사용한다. `--final`과 dev에서 고정한 모델 없이 test 실행을 요청하면 test 정답이나 문서를 읽기 전에 거부한다. 모델 이름·설치 digest·프롬프트·가드 버전·LLM 설정·관련 코드 해시도 고정 기록과 비교한다. 코드 해시는 Git의 줄바꿈 변환을 고려하여 CRLF를 LF로 정규화한다. test에서 모델 비교나 프롬프트 튜닝은 허용하지 않는다.

v3 고정 기록은 아래 dev 전용 명령으로 만들었다. 기존 qwen3 선택은 v2 가드의 8문서 비교에서 결정한 것이며 v3로 모델을 다시 선택하지 않았다. 생성 명령은 이미 있는 고정 파일을 덮어쓰지 않는다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/compare_llm_modes.py --selected-model qwen3:latest --freeze-release docs/eval/dev/guard_v3/release_lock.json
```

```powershell
backend/.venv/Scripts/python.exe backend/scripts/compare_llm_modes.py --split test --final --selected-model qwen3:latest --selection-record docs/eval/dev/guard_v3/release_lock.json
```

현재 실제 test 문서와 정답은 열지 않았고 최종 평가도 실행하지 않았다. 결과 기본 경로는 `docs/eval/test/final/`이다. 확정 test 정답과 고정 버전을 확인한 다음, test 문서를 처음 열기 전에 자료 폴더에 `final_evaluation_attempt.json`을 독점 생성한다. 출력 폴더를 바꾸어도 재실행을 차단한다. 실패·중단도 시도 기록을 남기며 자동 재실행하지 않는다. 독립 정답 준비는 별도 절차이며 평가 코드를 개발할 때 test를 열어 보지 않는다.

[LLM·평가 문서 목록](local_llm_runbook.md)
