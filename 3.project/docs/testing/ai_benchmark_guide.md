# AI 회귀 확인과 성능 측정

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 이번 AI 개선 작업의 실행 가능한 검사 도구. 실제 측정 결과는 각 실행의 JSON을 기준으로 한다.

관련 소스: [합성 회귀 검사](../../backend/scripts/ai_synthetic_benchmark.py) · [고정 결과 재채점·캐시 재생](../../backend/scripts/ai_cached_guard_benchmark.py) · [도구 자체 테스트](../../backend/scripts/test_ai_benchmark_tools.py)

## 1. 원본 평가 자료 없이 실행하는 검사

프로젝트 루트의 PowerShell에서 실행한다.

```powershell
$python='.\backend\.venv\Scripts\python.exe'
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
& $python -X utf8 backend/scripts/ai_synthetic_benchmark.py --repeat 20 --warmup 2 --output "build/ai-smoke-$stamp.json"
& $python -X utf8 -m unittest backend.scripts.test_ai_benchmark_tools -v
```

- 가상 TXT 3개와 DOCX 1개를 실제 파일 파서·분류기·규칙 추출기로 처리한다. 명시 금액, 0원 세액, 원문의 산술 오류 보존을 확인한다.
- 고정된 가상 모델 제안 10개를 v3/v4 가드에 각각 넣어 총 24개 사례를 확인한다. 잘못된 당사자·페이지·인용문·금액·날짜·사업자번호가 포함된다.
- 임시 자료만 사용하며 OCR, Ollama, VLM, 국세청 조회는 실행하지 않는다. 기존 DB, 원본 서류, 평가 정답·예측을 읽거나 수정하지 않는다.
- 기존 필드 평가 함수와 정규화 규칙을 재사용한다. 기대값은 검사 작성자가 만든 가상 값이며, 독립 검수한 실제 정확도 자료가 아니다.
- 각 사례의 반복 시간, p50/p95, 실패 내역, 소스 SHA-256, Python/패키지/OS를 JSON으로 남긴다. p95는 nearest-rank이고 반복 수가 적으면 참고값일 뿐이다. 준비·import·warmup은 측정 시간에서 제외하며 warmup의 오류도 실패로 처리한다.
- 종료 코드: 0=이 검사 범위 통과, 1=회귀 또는 실행 도중 코드 변경, 2=환경·입력·출력 오류. OCR/모델의 `not_run`은 통과를 뜻하지 않는다.
- 출력은 새 JSON만 허용한다. 기존 파일이나 `eval`, `docs/eval`, 고객 `storage` 아래에 쓰지 않는다.

## 2. 업로드된 고정 평가 결과를 재현

압축을 푼 읽기 전용 평가 자료 폴더를 `$archive`로 지정한다. 기존 결과를 덮어쓰지 않도록 새 출력 이름을 사용한다.

```powershell
$archive='D:\C-Pilot-evaluation'
& $python -X utf8 backend/scripts/ai_cached_guard_benchmark.py --archive-root $archive --split test --output "build/frozen-test-$stamp.json"
& $python -X utf8 backend/scripts/ai_cached_guard_benchmark.py --archive-root $archive --split test2 --output "build/frozen-test2-$stamp.json"
```

이 단계는 저장된 예측과 정답만 재채점한다. 패키지 receipt, 체크포인트, 정답·manifest freeze의 해시를 검증하고 과거 보고서의 모든 기존 지표와 대조한다. 패키지 안 Python은 실행하지 않는다. 새 진단 항목이 추가되어도 기존 지표를 생략하거나 바꾸면 재현 실패다. 사람 표본 검수와 AI 일치 정답을 사람 전수 검수로 바꾸어 설명하지 않는다.

## 3. 수정 전후 가드만 같은 캐시로 비교

코드 변경을 끝낸 뒤 별도 프로세스에서 실행한다. 아래는 TEST2/v4 예시이며 TEST/v3은 `--split test`로 별도 실행한다.

```powershell
$baseline='D:\C-Pilot-before'
& $python -X utf8 backend/scripts/ai_cached_guard_benchmark.py --archive-root $archive --code-root $baseline --split test2 --replay --repeat 20 --output "build/guard-before-$stamp.json"
& $python -X utf8 backend/scripts/ai_cached_guard_benchmark.py --archive-root $archive --split test2 --replay --repeat 20 --output "build/guard-after-$stamp.json"
```

`--code-root`에는 신뢰할 수 있는 수정 전 소스 체크아웃을 지정한다. 평가 ZIP 안의 구현 스냅샷을 실행 대상으로 사용하지 않는다.

두 결과의 `same_inputs_sha256`이 같고 `source_unchanged_during_run=true`인지 먼저 확인한다. 입력 페이지, 규칙 필드, 요청 대상, 모델 응답은 같아야 한다. 비교 대상은 `field_metrics`, `guard_outcomes`, `field_predictions_sha256` 및 결정 변화다. 버전 문자열만 바뀌어도 전체 trace 해시는 달라질 수 있다.

이 결과는 이미 사용한 held-out 자료의 탐색적 재사용이다. 새 독립 TEST 성능이나 OCR/모델 개선 결과가 아니다. 계약 검수 상태는 변경된 필드로 다시 계산하지 않으며, 시간은 현재 장치에서 `apply_proposals`만 실행한 값이다. 저장된 과거 OCR/모델 시간을 현재 실행 시간에 더해 속도 향상으로 발표하지 않는다. v3/v4 고정 릴리스 검사를 완화하지 않고 공식 보고서도 수정하지 않는다.

## 4. Windows에서 실제 OCR·모델 측정

[기존 평가기](../../backend/scripts/evaluate.py), [네 모드 평가기](../../backend/scripts/compare_llm_modes.py), [AI 실행 설정](../ai/runtime_settings.md)을 사용한다. Windows OCR 한국어 지원, 동일한 로컬 모델 digest, Python/패키지, GPU와 설정을 먼저 확인한다. 모델의 cloud-disabled 설정은 기존 요구사항 그대로 유지한다.

```powershell
# 확정 DEV 자료의 실제 파일 처리와 규칙 추출
& $python -X utf8 backend/scripts/evaluate.py --dataset "$archive/eval/dataset" --split dev --mode rule --output "build/live-rule-$stamp"

# DEV 네 모드. 새 캐시 폴더로 실제 모델 호출과 캐시 재생을 구분한다.
# 이 기존 비교 경로의 guarded 모드는 v3이다.
& $python -X utf8 backend/scripts/compare_llm_modes.py --dataset "$archive/eval/dataset" --split dev --selected-model qwen3:latest --cache "build/live-model-$stamp/cache" --output "build/live-model-$stamp/report"
```

- 기존 held-out의 재실행 제한·릴리스 해시를 바꾸지 않는다. 개선 선택은 DEV에서 하고 새 독립 TEST로 최종 검증한다. DEV2의 현재 정답은 미확정 초안이다.
- 실제 스캔 PDF/이미지 처리 결과를 확인해야 OCR 성능을 말할 수 있다. TXT/DOCX 통과나 고정 페이지 캐시로 Windows OCR 정확도를 추정하지 않는다.
- 기존 평가기의 문서 시간은 수집·추출 범위의 시간이며 API 요청부터 화면 표시까지의 전체 지연이나 사람 검수 시간은 아니다. 첫 호출/예열, 반복 수, 오류 수, 모델 로딩, 캐시 적중 여부를 함께 기록한다.
- 수정 전후에 같은 DEV 원본·정답·모델·하드웨어를 사용한다. 출력과 캐시는 서로 다른 새 폴더에 둔다. 회귀가 없거나 같은 점수라면 그대로 보고하며, 측정하지 않은 향상률을 만들지 않는다.

[전체 문서](../README.md) · [테스트와 검증](../development/test_and_verification.md)
