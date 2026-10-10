# OCR·텍스트 AI·이미지 재판독

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: HEAD `54a8841` + 미커밋 작업 트리. 작업 트리 기준. 설치 검증 범위는 고객 패키지 안내 참조.

관련 소스: [__init__.py](../../backend/app/ai/__init__.py) · [llm_supplement.py](../../backend/app/ai/llm_supplement.py) · [grounding.py](../../backend/app/ai/grounding.py) · [local_vlm.py](../../backend/app/ai/local_vlm.py) · [vlm_reread_service.py](../../backend/app/services/vlm_reread_service.py) · [documents.py](../../backend/app/api/documents.py)

## 기본 분석의 책임

`preprocessor.py`가 문서 본문·스캔 OCR을 읽고, `classifier.py`가 종류를 분류하며, `extractor.py`가 규칙으로 필드를 추출한다. `analyze_document`는 가림본도 만들고, 텍스트 AI가 켜져 있으면 `llm_supplement.py`로 필요한 항목을 보완한다. 최종 검수 상태는 [자동 검사 정책](../validation/current_rules.md)에서 정한다.

Qwen3는 OCR/문서 텍스트를 받는다. 원문 라벨·값·당사자·쪽/줄 등의 근거를 가드에서 확인하고 보완 기록과 거절 사유를 남긴다. 기존 규칙값과 AI 제안, 사람 수정의 출처를 구분한다. 가림본 생성이 로컬 AI 입력의 모든 개인정보 제거를 의미하지 않는다.

## 수동 VLM

Qwen2.5-VL은 현재 페이지 이미지를 받는 별도 모델이다. 버튼을 누를 때만 실행하고, JSON 후보값을 별도 AuditEvent에 저장한다. PDF·이미지 현재 본을 지원하며 문서 크기·페이지·SHA·revision/fingerprint를 확인한다. 모델 호출 중 DB 쓰기 잠금을 유지하지 않고 끝난 뒤 다시 자료 기준을 비교한다.

후보의 형식·제안 문구·당사자 표시는 기본 검사를 거친다. 이 검사는 이미지 원문을 독립적으로 검증한 증거가 아니다. 모델이 주장한 문구·좌표를 실제 OCR bbox로 자동 연결하지 않는다. 전액/부분 청구도 관련 명시 문구가 없으면 선택 가능한 후보로 보지 않는다.

사람이 가림을 끈 실제 원문과 대조하고 선택한 항목·사유·동의를 보내면 기존 필드 정정 경로로 저장한다. 선택하지 않은 필드는 유지한다. `VLM_ORIGINAL_CONFIRMED`는 사람이 확인한 방법을 나타내며 AI의 독립 정확도 인증이 아니다. 수정으로 자료 기준이 달라지면 이전 결재·지급의 현재 연결을 재확인한다.

## 실패와 성능 해석

판독 불가·모델 미설치·시간 초과·출력 한도·응답 형식 오류는 실패 안내를 제공하고 기존 저장값을 유지한다. 원문에서 보이지 않는 숫자는 사람이 추측해서 저장하지 않는다. 선명한 원본 또는 고친 본을 받는다.

VLM 연결 점검은 별도 가상 스캔 4장·20항목에서 19개가 일치했고, 가린 합계를 추측한 1개는 틀렸다. 이는 작은 연결 시험이며 정식 실무 정확도·기존 test2 결과에 포함되지 않는다. Qwen3-VL 4B 기본 태그는 다항목 응답 검증 문제로 추가 검토 대상으로 남겼다. 모델별 입력·설정은 [실행 설정](runtime_settings.md), 고정 평가 설명은 [평가 요약](../submission/evaluation_results.md)를 따른다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
