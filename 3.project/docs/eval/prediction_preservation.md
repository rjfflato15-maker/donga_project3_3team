# v3 예측 1회 보존과 독립 재채점

10/3 합의로 기존의 정답 확정 후 추론·채점 결합 절차를 분리한다. AI 추출·분류·프롬프트·가드·규칙·기존 평가기는 변경하지 않았다. 새 실행기는 현재 합성 test에만 적용한다. 국세청은 disabled이며 운영 DB를 사용하지 않는다.

## 실행 전 점검

```powershell
backend/.venv/Scripts/python.exe backend/scripts/predict_locked.py --preflight
```

고정 코드·모델 digest·설정·자료 해시·클라우드 비활성 설정을 확인하고, test와 무관한 `견적서 / 합계금액: 1100원` 입력으로 연결·형식·모델 로딩을 점검한다. 사람 정답·초안·Claude 응답을 읽지 않는다. 이 점검은 test 시도를 예약하지 않는다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/predict_locked.py
```

자료 폴더의 기존 `final_evaluation_attempt.json`을 독점 생성한다. 기존 최종 평가기도 같은 표시가 있으면 새 추론을 거부한다. 출력 폴더만 바꾸어 재실행할 수 없다. 네 조건의 문서별 값·계약별 검사 결과, OCR 입력, 원래 LLM 응답, 채택·거부 근거, 구현 사본, 환경 버전, 자료·코드·출력 해시를 `docs/eval/test/v3_predictions/`에 보존한다. 가드 유무 두 조건은 같은 LLM 응답을 사용한다. 가드 시간과 최초 LLM 호출 시간을 보존하며 사람 작업시간을 포함하지 않는다.

## 중단 복구 정책

- 완료된 OCR 입력·문서 예측·LLM 응답은 검증 후 재사용한다.
- 요청을 시작했다고 기록했는데 응답 파일이 없으면 `INTERRUPTED_RESPONSE_UNKNOWN` 실패로 확정한다. 이미 실행됐을 수 있는 모델 요청은 다시 보내지 않는다.
- 아직 시작하지 않은 요청만 같은 시도의 복구에서 실행할 수 있다. 같은 출력 폴더·자료·고정 버전으로 `--resume`을 사용한다. 모델이나 프롬프트를 바꾼 복구는 거부한다.
- 연결 실패·형식 오류도 원래 응답으로 보존하며 좋은 출력이 나올 때까지 재실행하지 않는다. v3 클라이언트에 이미 고정된 전송 재시도 설정은 그대로 기록한다.
- 프로세스가 강제 종료되면 `prediction_process.lock`이 남을 수 있다. 기록의 PID가 실제로 종료됐는지 확인한 뒤 해당 파일만 제거하고 복구한다. 실행 중인 잠금을 지우지 않는다.
- 예측 receipt 저장 후 종료 표시만 누락됐다면 복구는 receipt 해시를 확인하고 완료 표시만 수리한다. OCR·LLM을 호출하지 않는다.

## 예비 점수와 사람 확정 뒤 재채점

```powershell
backend/.venv/Scripts/python.exe backend/scripts/rescore_locked.py --labels eval/dataset/reference_labels_test.json --preliminary
backend/.venv/Scripts/python.exe backend/scripts/rescore_locked.py --labels eval/dataset/ground_truth_test.json
```

예비 점수는 `preliminary_unconfirmed`이며 발표용 확정 수치가 아니다. 사람 확정 정답·검수 출처·freeze 해시가 갖춰져야 `human_confirmed_rescore`가 된다. 정답 버전별 점수는 새 파일에 보존한다. 재채점은 고정 패키지의 채점 구현과 최종 예측을 읽으며 현재 앱의 OCR·LLM·가드를 호출하지 않는다. 개선 후에도 기존 예측을 새 가드로 재처리하지 않는다.

v4는 dev2에서만 개발하고 별도 test2에서 고정 후 1회 평가한다. v3 test의 실패 사례·정답·예측을 튜닝 자료로 사용하지 않는다. 사람 판독자에게 앱 예측·점수를 정답 힌트로 제공하지 않는다. 사람 확인 페이지는 기존 독립 대조 절차를 유지한다.
