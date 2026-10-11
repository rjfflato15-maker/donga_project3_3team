# 정산 엑셀과 증빙 ZIP 전달

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: HEAD `54a8841` + 미커밋 작업 트리. 작업 트리 기준. 설치 검증 범위는 고객 패키지 안내 참조.

관련 소스: [contract_exports.py](../../backend/app/api/contract_exports.py) · [settlement_export_service.py](../../backend/app/services/settlement_export_service.py) · [contract_export_service.py](../../backend/app/services/contract_export_service.py)

## 다운로드

계약 상세의 내려받기 메뉴에서 정산 엑셀·증빙 ZIP을 받는다. 지급 완료 화면에도 내려받기 동작을 제공한다. 개인정보 가림 ON이면 가린 값이며 실제 정산 전달에는 필요한 범위의 실제값을 사용한다. 실제값 다운로드 전 원문·확인 상태와 전달 대상을 확인한다.

| 파일 | 내용 |
| --- | --- |
| 정산 XLSX | 정산 내역·서류별 값·필드 확인·자동 검사·안내 5시트 |
| 증빙 ZIP | 현재/이전 원본, 검수 결과, 수정·요청·결재·지급 등 기록과 manifest |

XLSX는 현재 계약 자료의 snapshot이다. 자동 검사·사람 확인·유효한 결재와 지급 연결을 별도로 표시한다. 빈 칸을 0원으로 바꾸지 않고, 복수 계산서/통장 중 하나를 임의로 선택하거나 합산하지 않는다. 서류별 시트를 확인한다. 번호 앞자리 0을 보존하며 사용자 문자열을 Excel 수식으로 실행하지 않는다.

ZIP 가림본은 원본 형식·배치와 차이가 있을 수 있다. DOCX 등의 가림은 TXT로 전달할 수 있으며 PNG/PDF 가림도 OCR 누락까지 완전 제거를 보장하지 않는다. masked=false는 실제 원본 개인정보가 포함된다.

## 전달 범위

현재 XLSX는 일반 정산 자료이며 특정 더존·이카운트의 전표 업로드 형식을 검증하지 않았다. 세무사에게 증빙과 정산 자료를 전달하거나 ERP 담당자가 실제 양식의 계정과목·거래처 코드·필수 항목에 맞춰 변환한다. 세무 처리와 송금이 완료됐다는 자동 증명은 아니다.

자료 생성 중 기준이 바뀌면 409로 거절한다. 최신 자료를 불러오고 다시 다운로드한다. 다운로드는 OCR·LLM·검수·결재를 재실행하지 않으며 준비 성공 감사 기록이 파일 완전 수신을 증명하지는 않는다. 자세한 응답은 [XLSX API](../api/work_system.md)와 [기존 ZIP 규격 기록](../submission/omitted_records.md)을 참고한다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
