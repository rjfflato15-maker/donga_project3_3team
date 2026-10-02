# test 정답 준비와 사람 확인

사용자가 dev와 같은 방식의 test 정답 준비를 승인했다. test 원본은 **정답 초안 작성·독립 판독 묶음·사람 확인 화면 준비에만** 읽었다. 모델 출력·성능 측정·프롬프트 또는 가드 튜닝에는 사용하지 않았다. test 정답은 미확정이고 Claude 응답과 사람 확인은 아직 없다. 최종 평가 시도 기록도 없다.

## 전달할 자료

- `eval/claude_blind_review_test.zip`: 원본 59개와 공통 기준·프롬프트·등록 계약·빈 응답 양식, 계약 10건.
- `eval/claude_blind_review_test/CLAUDE_PROMPT.md`: 새 Claude 대화에 입력할 요청문.
- `eval/claude_blind_review_test/replies/`: 실제 Claude 응답을 `case_01.json`~`case_10.json`으로 저장할 곳.
- `eval/human_review_page_test/index.html`: dev와 같은 빌더·화면을 재사용한 페이지. 현재는 판독 대기이며 결과 저장을 막는다.

독립 판독은 frontend 개발용 Claude 대화와 별도의 새 대화에서 진행한다. Claude에는 ZIP 또는 그 폴더만 제공하고 생성 코드·정답 초안·앱 결과·평가 보고서는 제공하지 않는다. ZIP에 정답·생성 시나리오·앱 예측을 넣지 않았으며 모든 원본의 수령 해시를 제공한다. DOCX 판독에서 페이지 배치를 실제 확인하지 않았다면 그 사실을 기록한다.

Codex 초안은 `eval/dataset/reference_labels_test.json`이다. 생성 설계값을 앱 추출과 독립된 파일 판독/픽셀 대조로 확인했고, 사람 확정과 AI 독립 판독 완료 상태는 false다. 두 AI 결과가 같다는 사실만으로 사람이 전부 확인했다고 기록하지 않는다.

## 다음 순서

준비 명령은 기존 정답과 묶음을 덮어쓰지 않으며 고정 기록·자료 해시를 확인한다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/prepare_test_review.py
```

Claude 응답 10개를 받은 뒤 아래 명령을 실행한다. 미판독·빈 답이 있으면 사람 확인 목록을 생성하지 않는다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/prepare_test_review.py --replies eval/claude_blind_review_test/replies
```

실제 응답을 초안과 대조해 `eval/reconciliation-test-v1/`을 만들고, 불일치·모호함·해석 항목 전부와 나머지 일치 항목의 10%를 사례·문서 종류별 표본으로 뽑는다. `eval/human_review_test.xlsx`의 I·J열에 제안 답을 표시하고 K·L열은 비워 둔다. dev의 113칸과 동일한 수를 약속하지 않으며 실제 확인 수는 대조 후 결정한다. 같은 빌더가 test 페이지에 그 목록과 원문을 연결한다.

사람이 원문을 확인한 결과 JSON을 받으면 원래 양식 해시와 test 구분, 시트·행·ID를 검사한다. 확인·근거를 Excel 사본 K·L열에 옮기고 안내 B12에 실제 검수자를 기록한다. 원본 JSON·확인 시각·Excel과 정답 해시를 출처로 보관한다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/prepare_test_review.py --human-result "검수 결과 JSON 경로"
```

수정·보류가 있으면 자동 확정하지 않는다. 무작위 표본의 답을 고쳤다면 dev와 동일하게 확인 범위를 확대하고 새 대조·양식 버전을 만든다. 완료한 정답을 다시 가져와 덮어쓰지 않는다. 기존 dev 정답·Claude 응답·사람 확인 기록은 변경하지 않는다.

## 고정 버전

qwen3 모델 digest, 프롬프트 v3, 가드 v3와 모든 AI·검수 구현은 dev 고정 기록과 같다. 기존 평가 정답 검증기가 표본 검수를 dev에만 허용했으므로 **같은 출처 검증을 test에도 허용하는 검수 절차만 확장**했다. test 예비 측정은 계속 차단한다.

기존 `docs/eval/dev/guard_v3/release_lock.json`은 보존했다. 파생 고정 기록 `docs/eval/test/preparation/release_lock.json`에는 원래 기록의 해시와 평가 정답 검증기만 변경됐다는 내역을 남겼다. AI·프롬프트·가드·판정 코드가 달라지면 준비를 차단한다. 최종 평가에는 이 파생 기록을 사용한다. [최종 실행 안내](final_workflow.md)를 따른다.

평가 준비 도구는 최종 실행을 자동으로 시작하지 않는다. 사람 확정 후 버전·모델과 실행 환경을 확인하고 기존 `--final` 평가를 한 번 실행한다. 실패·중단도 시도 기록으로 남으며 임의 재실행하지 않는다.
