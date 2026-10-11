# C-Pilot 계약 증빙 검수

> 상태: 현재 기준
> 확인일: 2026-10-11
> 기준: contract-risk-review-v3 승인 배포본. 기존 실행본과 제출 ZIP/PDF는 별도 보존하고 현재 실행 앱·새 제출본을 같은 소스로 맞춘다.

관련 소스: [main.py](backend/app/main.py) · [package.json](package.json)

공식 주제: **콘텐츠 자동 분류·색인 시스템** · **3조** · 팀장 **이우현**

계약 대금 지급 전에 서류 누락·불일치와 원문을 확인하고 보완 요청·결재·지급 사실을 기록하는 로컬 시범 앱이다. 기본 필수 서류는 계약서·견적서·사업자등록증·통장사본·세금계산서·검수확인서이며 회사 설정에서 관리한다.

계약 전체 결과에서 문제와 필수 판단을 먼저 처리한다. 원본 근거·계약 기준·교차 검사를 충족한 반복값은 다시 원문 대조하도록 요구하지 않는다. 지급·업무 판단과 근거를 검증하지 못한 항목은 직접 확인한다. [현재 사용자 흐름](docs/ux/current_review_flow.md)과 [검증 범위](docs/development/verification_latest.md)를 기준으로 사용한다.

| 목적 | 시작 |
| --- | --- |
| 개발 환경 실행 | [개발 환경과 실행 명령](docs/development/getting_started.md) |
| 화면·기능별 수정 위치 | [소스 책임 지도](docs/architecture/module_map.md) |
| 기능 수정·검증 | [유지보수 작업표](docs/development/maintenance_cheat_sheet.md) |
| 사용자 실행·계정·백업 | [운영 안내](docs/operations/run_guide.md) |
| 구현 상태·제한·남은 작업 | [현재 상태](docs/progress/current_status.md) |
| 제출·발표 작성 | [설명 문서 구성](docs/submission/explanation_outline.md) |
| 제출용 소스 ZIP | [포함·제외·검증 기준](docs/submission/source_package.md) |

소스 실행에는 앱 폴더와 개발 환경이 필요하다. 2026-10-11 ZIP에는 GUI 실행기 `C-Pilot.exe`를 포함한다. `start_pilot.bat`으로 실행기를 다시 만들 수 있으며 개발용 실행기 EXE만 다른 PC에 복사하는 방식은 지원하지 않는다. 이전 제출본의 고객용 Setup 빌드와 동일 PC 격리 설치·업데이트·제거 시험은 기록돼 있다. 이번 배포는 소스 전용이며 설치 EXE 재빌드는 범위에 포함하지 않는다. 향후 설치형으로 배포할 때는 변경된 소스로 Setup을 다시 빌드하고 확인해야 한다. 새 PC 설치·실제 AI 모델 준비·설치 마법사 화면·제품 서명 검증은 별도 확인 대상이다.

준비한 PC에서는 `C-Pilot.exe`를 더블클릭하면 CMD 창 없이 브라우저가 열린다. 관리 메뉴는 필요한 때만 별도로 호출한다. 최초 설치·빈 업무함 생성·종료 방법은 [운영 안내](docs/operations/run_guide.md)를 따른다. 실제 환경 파일 대신 [설정 예시](backend/.env.example)를 제공하며 로컬 pilot 실행에는 외부 DB 계정이나 API Key가 필요 없다.

텍스트 보완은 Qwen3, 이미지 재판독은 별도 Qwen2.5-VL 모델을 사용한다. 이미지 재판독 후보는 사람이 원문과 비교한 항목만 저장한다. 일반 정산 XLSX는 제공하지만 특정 ERP 업로드 양식의 호환은 검증하지 않았다.

고객 DB·문서·계정 안내·환경 설정·백업은 코드와 분리한다. 개발·확인은 별도 임시 업무함으로 진행한다.

[전체 문서](docs/README.md) · [현재 구현 상태](docs/progress/current_status.md)

## 이번 OCR·근거 가드 보완

Windows 로컬 OCR 엔진과 로컬 모델은 바꾸지 않았다. 혼합 PDF의 페이지별 판독, 근거 누락 방어, 이미지 좌표 일관성을 보완했다. 현재 버전에서는 고정 정답의 합성 스캔을 실제 Windows OCR로 처리해 원본 행 재판독·계약 기준 대조·상신 흐름을 시험했다. 실고객 정확도·시간 절감과 실제 LLM/VLM 추론은 이번 검증에 포함하지 않았다. 저장된 과거 응답 비교와 현재 스캔 시험을 구분한다.

- [검사 실행 안내](docs/submission/omitted_records.md)
- [이번 비교 결과](docs/submission/omitted_records.md)

PDF 자동 처리에는 보수적인 50페이지 제한이 적용된다. 일부 페이지를 판독하지 못하면 정상 처리 완료로 취급하지 않으며, 파일을 나누거나 판독 환경을 확인한 뒤 다시 시도해야 한다. 완전히 빈 페이지로 확인된 구분 페이지는 읽을 내용이 있는 문서에서 제외해 판단한다. OCR이 빈 결과를 냈다는 이유만으로 빈 페이지로 간주하지 않는다.
