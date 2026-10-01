# 문서 검수 성능 평가

이 폴더는 합성 서류, 사람이 작성할 빈 정답표, 평가 기준을 보관한다. 현재는 2A 준비 단계로, 정답 확정과 실제 기준 성능 측정은 아직 진행하지 않았다. 자동 추출 결과를 정답으로 채우지 않는다.

생성 정보에서 작성한 정답 초안과 사람의 최종 확정을 구분하는 절차를 추가했다. `reference_labels_dev.json`은 Codex가 생성 정보와 파일 내용을 대조한 초안이며 사람이 확정한 `ground_truth_dev.json`을 대신하지 않는다. Claude는 별도의 원문 묶음으로 독립 판독한 뒤 두 초안을 비교한다. 불일치 및 표본을 사람이 확인하고 정식 정답을 확정한다.

```powershell
python backend/scripts/build_reference_labels.py
.\backend\.venv\Scripts\python.exe backend/scripts/evaluate.py --split dev --mode rule --preliminary
```

초안 생성은 한국어 폰트와 `eval/requirements-tools.txt`의 도구가 있는 환경에서 수행한다. 현재는 Codex 번들 Python을 사용한다. 예비 결과는 `docs/eval/dev/preliminary/`에 저장하며 사람 확정 기준 성능과 파일명을 구분한다. test는 예비 측정하지 않는다.

## 자료 구성

| 구분 | 계약 수 | 문서 수 | 서식 계열 | 용도 |
| --- | ---: | ---: | --- | --- |
| dev | 10 | 59 | 문단형 | 규칙 기준 측정, 모델 선택과 개선 |
| test | 10 | 59 | 두 열과 표 | 구현과 설정 고정 후 최종 평가 |

전체 형식은 PDF 37개, PNG 45개, DOCX 36개이다. 시나리오는 정상 제출, 필수 서류 누락, 공급자 번호 불일치, 합계 불일치, 부가세 별도, 분할 지급, 이미지 스캔, 품목 표, 의미가 모호한 금액, 금액 산술 불일치이다. 모든 회사와 거래는 가상이다. `000`으로 시작하는 테스트 사업자번호는 체크섬 형식을 맞춘 예시이며 실제 등록 사업자가 아니다.

dev와 test는 생성 양식과 회사명 및 금액을 분리했다. 다만 두 가지 합성 서식 계열만 사용하므로 실제 회사의 다양한 증빙에 대한 일반화 성능을 증명하지 않는다. 기존 `sample-data`는 이 자료에 섞지 않았다. 향후 사용하더라도 dev에만 추가하고 자료 버전을 새로 만든다.

`dataset/manifest.json`은 입력 계약 정보, 자료 경로, 파일 해시, 검수 항목을 담는다. 문서 유형 정답과 필드 정답은 들어 있지 않다. `dataset/ground_truth_dev.json`과 `ground_truth_test.json`은 모두 미작성 상태다. `ground_truth_template.xlsx`의 노란색 칸을 사람이 작성하고, [라벨링 기준](LABELING_GUIDE.md)에 따라 확인한다.

PDF 전부를 렌더링했고 PDF와 PNG의 페이지 배치 및 Excel 7개 시트의 미리보기를 확인했다. DOCX는 열기 및 문단·표 구조 검사를 했지만 페이지 렌더링에 필요한 LibreOffice가 없어서 시각 검증을 마치지 못했다. DOCX의 검증 완료와 사람이 정답을 검수했다는 주장은 아직 하지 않는다.

## 정답을 작성하고 확정하는 순서

1. `ground_truth_template.xlsx`를 복사해 `ground_truth_reviewed.xlsx`로 저장한다.
2. DEV_유형, DEV_필드, DEV_검수의 모든 정답을 원문을 보며 작성한다. 입력 상태와 값의 차이 및 N/A 기준은 라벨링 문서에 있다.
3. 검수자 별칭을 지정하여 아래 명령으로 dev 정답을 가져온다. 미작성·미확인 행, 다른 자료 버전, 수식으로 입력한 정답은 거부한다.
4. 정답 확정 뒤 기준 성능을 측정한다. test 정답과 평가는 최종 설정을 고정한 뒤 진행한다.

프로젝트 폴더 `C:\3조 색인\3.project`에서 PowerShell로 실행한다. 기존 백엔드 가상환경을 사용한다.

```powershell
$env:PYTHONIOENCODING = 'utf-8'
.\backend\.venv\Scripts\python.exe backend/scripts/import_evaluation_labels.py eval/ground_truth_reviewed.xlsx --split dev --reviewer "검수자별칭" --confirmed
.\backend\.venv\Scripts\python.exe backend/scripts/evaluate.py --split dev --validate-only
.\backend\.venv\Scripts\python.exe backend/scripts/evaluate.py --split dev --mode rule
```

정답 확정 시 검수자, 확정 일시, Excel·정답·자료 목록 SHA256을 `ground_truth_dev.freeze.json`에 기록한다. 이미 확정된 자료는 가져오기 명령으로 덮어쓰지 않는다. 정답을 수정해야 하면 근거를 남기고 새 버전의 자료와 정답을 만든다. 해시는 파일 버전을 식별할 뿐 검수 사실을 독립적으로 증명하는 서명이 아니다.

정식 측정이 완료되면 `docs/eval/dev/baseline/`에 보고서 Markdown, 지표 JSON, CSV가 생긴다. 빈 정답표로 실행하면 종료 코드 2로 중단하고 보고서를 만들지 않는다. 평가 과정은 임시 저장소와 미연동 국세청 클라이언트를 사용한다. 고객 DB와 증빙을 평가에 사용하지 않는다. 콘솔과 오류 사례에는 원문이나 추출 필드 값을 출력하지 않는다. `--save-predictions`는 현재 가상 자료 버전에 한하여 로컬 결과 JSON 저장을 허용하며 독립 판독 묶음에는 넣지 않는다.

최종 평가 명령에는 `--split test --final`이 필요하다. `--final`은 사용자가 설정 고정을 확인하는 실행 옵션이며 실제 고정을 자동으로 보증하지는 않는다. 모델과 프롬프트 및 설정 고정 기록은 2B 단계에서 추가한다.

## Claude 독립 판독과 초안 대조

`claude_blind_review.zip`은 dev 원본 59개, 공통 기준과 프롬프트, 계약별 등록 기준 및 빈 JSON 양식이다. 파일명은 유형을 담지 않는다. 생성 시나리오, 문서 유형별 검수 항목 배정, Codex 정답 초안, 앱 코드와 추출 결과, test 자료는 제외했다. 배정으로 유형을 누설하지 않도록 모든 문서에 동일한 검수 후보 목록을 제공한다.

1. 새 Claude 대화에서 `claude_blind_review/CLAUDE_PROMPT.md` 내용을 붙여 넣는다. 앞선 Claude 대화는 생성 코드를 이미 봤으므로 독립 판독에 재사용하지 않는다.
2. 로컬 파일 접근이 가능하면 해당 폴더 내부만 읽게 한다. 일반 채팅이면 ZIP을 풀고 공통 기준과 case_01부터 각 건의 원본, `registered_contract.json`, `reply_template.json`을 제공한다. ZIP 내부를 직접 읽을 수 있다고 가정하지 않는다.
3. 계약별 완성 응답을 `claude_reply_case_01.json` 등의 파일로 저장한다. 실제 읽은 방법과 근거를 적고 읽지 못한 문서는 미응답으로 둔다. 작성자를 Claude로 기록하되 사람 확정은 false로 유지한다.
4. 아래 명령으로 실제 응답을 대조한다. 여러 파일은 경로를 나열한다. 누락된 계약이나 미응답은 일치로 세지 않으며, 반복 ID는 덮어쓰지 않고 중단한다.

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/compare_reference_labels.py eval/claude_reply_case_01.json eval/claude_reply_case_02.json --output eval/reconciliation-v1
```

모든 dev 응답이 필요하다. 위 두 파일 예시는 일부 계약만 받은 상태의 대조이며 미완료로 표시된다. 결과는 `comparison.json`, `human_review_queue.csv`, 안내 Markdown이다. 사람 확인 목록은 불일치와 모호한 칸 전부 및 나머지 일치 칸의 무작위 20%다. seed 42와 입력 파일 해시, 계약별 표본 포함 여부를 기록한다. 20%가 정확도를 보증하거나 자동으로 정답을 확정하지 않는다. 표본 오류가 발견되면 범위를 넓힌다.

CSV는 대조용 입력 자료이며 Excel 가져오기 양식과 다르다. 전수 직접 확인용 빈 Excel은 `import_evaluation_labels.py`, AI 대조 후 직접·표본 확인용 Excel은 `import_reconciled_labels.py`로 가져온다. 두 절차의 확인 범위를 구분하며 아래 현재 대조 결과 안내를 따른다.

## Claude 판독 완료 후 사람 확인

실제 응답 10개를 `claude_blind_review/replies/case_01.json`부터 `case_10.json`까지 받았다. dev 문서 59개( PDF 18개, PNG 23개, DOCX 18개)의 유형 59칸·필드 413칸·검수 412칸·누락 목록 10칸을 대조한 결과, 총 894개가 일치했고 불일치 및 미응답은 0개다. 이는 두 초안의 일치율이며 앱 정확도나 정답 보증이 아니다. Claude 요약문의 DOCX 20개 표기는 실제 파일 수와 다르지만 JSON은 실제 59개 문서에 대응한다.

두 AI가 같은 해석을 선택했더라도 사람이 판단할 질문 12개를 `human_questions_dev_v1.json`에 별도로 기록했다. 검수확인서 9건의 금액 범위, case_09 견적서 범위 1칸, case_10 세금계산서 산술 및 전액 대조 2칸이다. 원래 모호한 상태 15칸과 질문 12칸 중 1칸이 중복되어 필수 확인은 26칸이다. 나머지 일치 868칸에서 seed 42로 20%를 올림한 174칸을 무작위 선정했다. 최종 사람 확인 목록은 200칸(문서 유형·필드 105칸, 검수·누락 95칸)이다. 기준 질문 추가 전 `reconciliation-v1`은 초기 대조 기록이며, 현재 사용 양식은 `reconciliation-v2`다.

사람 확인 양식은 `outputs/01a0f640-7f7a-7eb1-8eb2-bb5a189f1850/human_review.xlsx`이다. 안내, 필드확인, 검수확인, 원문목록의 네 시트가 있다. I·J열 최종 답은 AI 초안으로 미리 채웠고, K열 직접 확인과 L열 사람 판단 근거는 비워 두었다. 안내 B12에 검수자 별칭을 적고 선택된 원문과 등록 기준을 직접 읽는다. 답이 맞으면 I·J를 유지하고 틀리면 수정한다. K에서 확인을 선택하고 L에 판단 근거를 작성한다. 사업자번호는 앞자리 0이 유지되는 하이픈 문자열로 작성한다. 금액과 날짜는 typed Excel 값이다.

확인한 파일을 `human_reviewed.xlsx` 등의 다른 이름으로 저장한다. 완료 후 아래 명령을 실행한다. 지금 제공한 미확인 양식으로는 정답을 확정하지 않는다.

```powershell
.\backend\.venv\Scripts\python.exe backend/scripts/import_reconciled_labels.py outputs/01a0f640-7f7a-7eb1-8eb2-bb5a189f1850/human_reviewed.xlsx --reviewer "검수자별칭" --confirmed
.\backend\.venv\Scripts\python.exe backend/scripts/evaluate.py --split dev --mode rule
```

가져오기는 대조 결과를 원본 초안·실제 Claude 응답에서 재계산하고, Excel의 버전 및 해시·검수자·필수 행·직접 확인·판단 근거를 검사한다. 미완료면 기존 정답을 변경하지 않는다. 확정 시 사람 직접 확인과 AI 일치의 출처를 항목별로 기록하고, 보고서에 실제 확인 수를 명시한다. 선택된 200칸이 전부 확인됐다고 나머지 694칸까지 사람 전수 검수로 기록하지 않는다. 기존 확정 정답은 덮어쓰지 않는다.

무작위 표본에서 오답을 수정했다면 초기 확인 범위로 확정하지 않는다. `--sample-rate 1.0`의 새 대조와 양식으로 나머지 항목까지 확인한다. 해석 질문은 현재 모든 해당 문서의 범위가 확인 목록에 있으므로 판단과 이유를 기록하여 수정할 수 있다. 정답 수정 시 초기 예비 수치와 확정 수치의 정답 해시가 달라졌음을 설명하고 확정 정답으로 기준 성능부터 다시 측정한다.

## 현재 예비 결과

생성 설계값을 사용한 dev 초안을 실제 PDF·DOCX 내용 및 PNG·스캔 PDF 픽셀과 대조했다. 초안은 별도 `reference_labels_dev.json`에 저장했으며 사람 정답 `ground_truth_dev.json`과 test 정답은 빈 상태로 유지했다. 초안 해시와 사용한 생성 코드·기준 문서 해시를 기록했고 예비 명령에서 변경 여부를 검사한다. 픽셀 일치는 판독 가능성이나 사람이 검수했다는 증거는 아니다.

예비 규칙 측정은 분류 Macro F1 1.000, 핵심 필드 정확도 0.7834, 누락 Recall 1.000, 교차검증 Macro F1 0.7530이며 문제가 있는 항목에서 잘못된 PASS는 0/17다. 핵심 필드는 VALUE와 REVIEW 337칸 중 264칸을 맞혔다. FAIL 정답 4건 중 FAIL을 출력한 것은 1건이므로 잘못된 PASS 0건만으로 오류를 모두 찾았다고 설명하지 않는다. 누락 표본은 단 2종이므로 100%를 폭넓은 성능 보장으로 해석하지 않는다. 상세 결과는 `docs/eval/dev/preliminary/preliminary_rule.md`에 있다. Claude 독립 판독과 사람 확인이 끝나기 전까지 발표용 정식 성능으로 사용하지 않는다.

## 비교 모드와 지표

현재 실행 가능한 모드는 `rule`이다. `llm`, `hybrid_unguarded`, `hybrid_guarded`는 1번 구현 뒤 연결할 자리만 있으며 아직 실행되지 않는다. 가드 효과는 같은 모델 응답을 저장하여 가드 전후를 비교해야 한다. 정답표를 나중에 예측 결과에 맞춰 고치지 않는다.

| 지표 | 분모와 해석 |
| --- | --- |
| 분류 Macro F1 | 6종 문서의 F1 평균. 파일명 및 사용자 유형 힌트로 정답을 제공하지 않음 |
| 핵심 필드 정확도 | VALUE와 REVIEW 정답 전체. 존재하는 값의 추출을 보류해도 분모에 남음 |
| 누락 Recall | 실제 미제출 필수 서류 중 MISSING으로 찾은 비율 |
| 교차검증 Macro F1 | PASS, FAIL, REVIEW, MISSING의 F1 평균. N/A끼리 일치한 행은 제외 |
| 잘못된 PASS 비율 | FAIL·REVIEW·MISSING 정답 중 PASS를 출력한 비율 |
| PASS 중 잘못된 비율 | 위의 잘못된 PASS 수를 전체 출력 PASS 수로 나눈 값 |
| 값 제공 비율 | 전체 필드 중 비어 있지 않은 값을 낸 비율. 사람 승인율이 아님 |
| 없는 필드의 거짓 추출률 | ABSENT 정답 중 값을 만들어 낸 비율 |
| 확인 필요 비율 | 채점 대상 검수 결과에서 REVIEW 비율 |
| 처리시간 | 문서 분류와 추출 평균 시간. 규칙 검수 및 사람 작업·대기시간 제외 |

분모가 0인 비율은 0%나 100%로 대신 표시하지 않고 측정 불가로 보고한다. Macro F1은 평가 클래스 수를 고정하고 정답과 예측이 모두 없는 클래스는 F1 0으로 둔다. 유형별 표본 수와 오류 수도 JSON에 기록한다. LLM의 근거 없는 추출률과 가드 거부 사유 집계는 LLM 구현 전이므로 아직 계산하지 않는다.

## 합성 자료 재생성

생성 코드는 `backend/scripts/generate_evaluation_dataset.py`이다. `eval/requirements-tools.txt`에 있는 생성 도구와 한국어 폰트가 필요하다. 기존 자료와 정답을 덮어쓰지 않도록 출력 폴더가 비어 있어야 한다. 다른 버전은 생성 코드의 자료 버전과 경로를 함께 변경한다. 현재 자료는 Codex의 번들 Python과 `C:\Windows\Fonts\malgun.ttf`로 생성했다.

```powershell
python backend/scripts/generate_evaluation_dataset.py --output eval/dataset-new-version --font C:/Windows/Fonts/malgun.ttf
```

이 명령은 정답이 비어 있는 JSON까지 생성한다. Excel 정답 양식은 별도로 만들어 ID와 자료 해시를 일치시켜야 한다. 서류를 사람이 검수한 정답까지 자동 생성하는 명령은 없다.
