# 사용·운영 문서 목록

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [cli.py](../../backend/launcher/cli.py)

소스 폴더에서 사용할 때는 [최초 준비](installation.md) 후 C-Pilot.exe를 실행한다. 평소 실행에서는 CMD 창이나 Enter 대기 없이 브라우저가 열리며, 시작 실패 시 오류 안내 창이 뜬다. 관리 메뉴는 필요한 경우에만 `C-Pilot.exe manage`로 연다. 개발용 실행기 EXE 단독 복사는 지원하지 않는다. 이번 소스 전용 배포에는 설치 EXE가 없다.

| 할 일 | 문서 |
| --- | --- |
| 설치·빈 업무함·첫 계정 | [처음 설치](installation.md) |
| 실행·종료·설정·재시작 | [실행과 설정](startup_settings.md) |
| 문서 등록부터 결재·지급까지 | [업무 사용 흐름](workflow.md) |
| 정산 엑셀·증빙 ZIP | [자료 전달](accounting_export.md) |
| AI 활성화·모델·재판독 | [설정](../ai/runtime_settings.md) · [분석 흐름](../ai/pipeline.md) |
| 계정·비밀번호·퇴사 | [계정 안내](accounts_security.md) |
| 다른 PC 브라우저 접속 | [사내망](network.md) |
| 백업·복원 | [자료 복구](backup_restore.md) |
| 업데이트·장애 대응 | [운영 유지보수](maintenance.md) |
| 고객용 설치·판매 범위 | [Setup 소스와 검증 범위](customer_package.md) · [판매 검토](distribution.md) |
| 실제 자료와 분리한 시연 | [시연 업무함](../submission/omitted_records.md) · [기존 시연 대본](../submission/omitted_records.md) |

시연·측정 안내는 작성 당시 자료와 빌드를 사용한다. 화면 공유 자료와 실제 앱, 실시간 모델과 고정 응답 재생, 기계 처리시간과 사람 작업시간을 구분한다. 새 XLSX·VLM 기능의 완료 상태는 현재 상태에서 확인한다.


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
