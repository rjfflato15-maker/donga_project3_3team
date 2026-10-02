# 최종 test 실행 조건

**2026-10-03 변경:** 사용자의 연휴 고도화 합의에 따라 [예측 1회 보존·별도 재채점](prediction_preservation.md)을 적용한다. 현재 고정 버전으로 예측을 먼저 보존하고, 사람 정답 확정 뒤 `rescore_locked.py`로만 재채점한다. 아래 기존 `--final` 명령은 종전 결합 실행 절차이며 새 예측 시도 기록이 있으면 차단된다. v3 예측을 v4 가드로 재처리하지 않는다.

test의 독립 판독·사람 확인·정답 확정은 별도 단계다. 그것을 마친 뒤에만 아래 명령을 사용한다. `--final`과 dev에서 고정한 모델 없이 test 실행을 요청하면 test 정답이나 문서를 읽기 전에 거부한다. 모델 이름·설치 digest·프롬프트·가드 버전·LLM 설정·관련 코드 해시도 고정 기록과 비교한다. 코드 해시는 Git의 줄바꿈 변환을 고려하여 CRLF를 LF로 정규화한다. test에서 모델 비교나 프롬프트 튜닝은 허용하지 않는다.

v3 고정 기록은 아래 dev 전용 명령으로 만들었다. 기존 qwen3 선택은 v2 가드의 8문서 비교에서 결정한 것이며 v3로 모델을 다시 선택하지 않았다. 생성 명령은 이미 있는 고정 파일을 덮어쓰지 않는다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/compare_llm_modes.py --selected-model qwen3:latest --freeze-release docs/eval/dev/guard_v3/release_lock.json
```

```powershell
backend/.venv/Scripts/python.exe backend/scripts/compare_llm_modes.py --split test --final --selected-model qwen3:latest --selection-record docs/eval/test/preparation/release_lock.json
```

사용자 승인에 따라 test 정답 초안·독립 판독 묶음·사람 확인 페이지를 준비했다. 실제 test 원본은 이 정답 준비에만 사용했으며, 모델 추출·튜닝·성능 측정은 실행하지 않았다. Claude 독립 판독과 사람 정답 확정은 대기 중이다. [정답 준비 절차](test_review_preparation.md)를 먼저 따른다.

dev 전용이던 표본 검수 출처 검증을 test에도 허용하도록 평가 정답 검증기만 확장했다. AI·검수·모델·프롬프트·가드는 그대로이며, 기존 dev 고정 기록을 보존하고 원래 기록의 해시와 변경 범위를 `docs/eval/test/preparation/release_lock.json`에 남겼다. 위 최종 명령은 이 파생 기록을 사용한다.

결과 기본 경로는 `docs/eval/test/final/`이다. 확정 test 정답과 고정 버전을 확인한 다음, 평가용으로 test 문서를 읽기 전에 자료 폴더에 `final_evaluation_attempt.json`을 독점 생성한다. 출력 폴더를 바꾸어도 재실행을 차단한다. 실패·중단도 시도 기록을 남기며 자동 재실행하지 않는다. 실제 최종 시도는 아직 없다.

[LLM·평가 문서 목록](local_llm_runbook.md)
