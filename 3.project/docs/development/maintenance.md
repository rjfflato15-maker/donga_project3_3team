# 개발자 변경·확인 절차

먼저 [소스 역할 표](../architecture/module_map.md)에서 담당 영역을 찾는다. 파일 길이만으로 나누지 않고 서로 다른 책임이 섞여 있을 때 분리한다. 실행·계정·문서 읽기·AI 추출·검수·저장·화면의 경계를 유지한다.

1. 바꿀 동작과 관련 모듈을 정한다. 화면 디자인은 계획과 이미지 시안을 승인받는다.
2. 고객 DB·정답·평가 자료 대신 임시 자료로 작업한다. 소스 수정과 고객 자료 변경을 섞지 않는다.
3. 영향이 있는 확인을 실행한다. 이번처럼 실행기 구조를 바꾸면 중복 실행·다른 프로세스 보호·백업·복원을 확인한다.
4. 담당 운영 문서와 작업 기록을 갱신하고 진행 요약에 링크를 추가한다.
5. 로컬 커밋으로 변경을 보관한다. 배포·push·PR은 해당 작업의 승인 범위에 따른다.

## 프로젝트 루트에서 실행하는 확인

```powershell
# 백엔드 회귀 검증: 테스트는 고객 DB와 별도 임시 DB를 사용
backend/.venv/Scripts/python.exe -m pytest backend/tests -q

# 화면 형식 검사와 빌드
cd frontend
npm run build
```

실행기 설정은 `storage/launcher/settings.json`에 있고 계정·회사·필수서류 설정은 업무 DB에 있다. EXE 입구는 `tools/launcher/Program.cs`, Python 입구는 `backend/pilot_launcher.py`다. 입구 경로를 임의로 바꾸면 예약 작업과 EXE 연결도 확인한다.

## 고정 평가 코드와 데이터

가드 v3의 관련 코드·모델·프롬프트·설정은 `docs/eval/dev/guard_v3/release_lock.json`과 비교한다. test 준비에서는 같은 표본 검수 출처를 test에도 허용하는 정답 검증 절차만 확장했고 `docs/eval/test/preparation/release_lock.json`에 원래 기록과 변경 파일을 남겼다. AI·검수·스키마·모델·프롬프트·가드는 원래 버전과 같다. 리팩터링도 코드 변경이므로 무심코 이동하거나 다시 고정하지 않는다. 변경이 필요하면 별도 버전과 평가 계획을 정한다.

확정 dev 정답과 사람 출처는 임의 수정하지 않는다. test 원본은 승인받은 [정답 준비](../eval/test_review_preparation.md)에만 읽고 개발·튜닝에 사용하지 않는다. 성능 측정은 [최종 평가 조건](../eval/final_workflow.md)을 따른다. 캐시·JSON·CSV·고정 기록은 문서 정리 대상에서 제외한다.

frontend는 별도 브랜치의 화면 담당자가 맡는다. 이번 백엔드 작업에서 수정하지 않았으며 [API 인계](../api/frontend_handoff.md)를 기준으로 연결한다. 새 운영 기록 테이블은 백엔드 시작 때 생성한다. 실제 운영 서버에 적용할 때는 먼저 백업하고 통합 실행기로 재시작한다.

고객 업데이트는 [운영 유지보수](../operations/maintenance.md), 배포할 폴더는 [배포 경계](distribution_boundary.md)를 참고한다.

개발·운영 보조 스크립트는 [tools 안내](../../tools/README.md), 파일 보관 기준은 [폴더 안내](folder_guide.md)를 확인한다.
