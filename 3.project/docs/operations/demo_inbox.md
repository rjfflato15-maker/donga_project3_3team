# C업체 시연 전용 업무함

관련 도구는 `backend/scripts/prepare_demo_inbox.py`다. 실제 업무 DB·계정·설정·원본을 복사하지 않고 dev 합성 원본으로 새 업무함을 만든다. 출력은 Git에서 제외한 `storage/demo/` 아래 새 폴더로 제한하며 기존 폴더를 덮어쓰거나 삭제하지 않는다.

## 준비와 실행

프로젝트 루트에서 실행한다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/prepare_demo_inbox.py
```

결과 폴더는 `storage/demo/c-company-v1/`이다. **`Run-demo.bat` 하나**에서 1(규칙만), 2(AI 보완 결과), 0(시연 서버 종료)을 선택한다. 초기 시연 계정은 같은 폴더의 `initial-accounts.txt`에 있으며 첫 로그인 때 비밀번호를 변경한다. 초기 비밀번호를 콘솔·Git·제출 문서에 넣지 않는다.

| 비교 상태 | 원문·DB 위치 | 접속 |
| --- | --- | --- |
| 규칙만 | `rule/storage/` | `http://127.0.0.1:8020/` |
| AI 보완 결과 | `guarded-replay/storage/` | `http://localhost:8021/` |

별도 호스트 이름으로 두 시연 업무함의 로그인 쿠키를 구분한다. 실제 업무 서버 8000과 Claude의 임시 서버 8010을 종료하거나 설정하지 않는다. 선택한 포트가 다른 프로그램에 사용 중이면 기존 프로그램을 종료하지 않고 실행이 거부된다.

시연 전후 원본 상태를 다시 준비하려면 새 폴더를 지정한다. 규칙 업무함만 필요하면 `--rule-only`를 사용한다.

```powershell
backend/.venv/Scripts/python.exe backend/scripts/prepare_demo_inbox.py --output storage/demo/c-company-v2
```

## 다섯 사례

| 시연 계약 | dev 출처 | 보여 줄 내용 |
| --- | --- | --- |
| 정상 제출 | case_01 | 6종 제출과 원문 확인, 담당자 확인 후 대표 최종 확인 |
| 서류 누락 | case_02 | 통장사본·검수확인서 누락, 직접 연락한 요청과 회신 기록 |
| 금액 불일치 | case_04 | 견적 합계와 등록 계약 금액 대조 |
| 사업자번호 불일치 | case_03 | 공급자 번호와 등록 거래처 번호 대조 |
| 모호한 금액 | case_09 | 참고값을 공급가액·세액·합계로 추측하지 않고 원문 확인으로 넘김 |

다섯 계약에 원본 28개가 들어간다. 등록 기준과 원문을 유지하고 제목에는 시연 사례를 표시한다. 분류와 추출에 정답표를 넣거나 정답 값을 덮어써서 PASS를 만들지 않는다. 정상 제출도 국세청 미연동·추출 미확인 때문에 REVIEW가 있을 수 있으며 이 상태를 숨기지 않는다. 사람·대표 확인 기록은 사용자가 시연에서 직접 남긴다.

## 합의한 국세청 조회 정책

사업자 상태 조회는 `APP_NTS_MODE`로 켜고 끌 수 있는 기존 구조를 유지한다. **시연과 평가는 항상 `APP_NTS_MODE=disabled`(끔·미연동)**로 실행한다. 시연·평가 서류의 사업자번호는 모두 가상 번호이므로 실제 조회의 미등록 결과는 서류 판독 성능을 평가하는 데 의미가 없다. 실제 조회에는 외부 통신도 필요하여 사내망 기본 원칙과 맞지 않는다. 실제 번호를 조회해 미등록 여부를 확인한 것은 아니다.

공식 연동 경로는 [공공데이터포털의 국세청 사업자등록정보 진위확인 및 상태조회 API](https://www.data.go.kr/data/15081808/openapi.do)다. 현재 상태조회 클라이언트는 `https://api.odcloud.kr/api/nts-businessman/v1/status`를 사용하며 홈택스 스크래핑은 쓰지 않는다. 실환경에서 연동하려면 외부 통신 허용과 발급 키가 필요하고 기존 설정은 `APP_NTS_MODE=api`다. 이번 시연에서 연동을 켜거나 호출하지 않는다.

시연 준비 하위 프로세스와 시연 실행기 모두 NTS를 `disabled`로 강제한다. 부모 환경에 `APP_NTS_MODE=api`가 있어도 시연은 미연동이며 사업자 상태는 자동 PASS 대신 REVIEW로 남긴다. 새 시연 생성 기록에도 `nts_mode: disabled`를 저장한다.

## AI 비교를 설명하는 법

규칙 업무함에서 원문을 실제 분석한 뒤 그 업무함을 시연 폴더 안에서 복사하고, AI 비교 업무함에 **기존 dev qwen3 응답을 가드 v3로 다시 적용**한다. 모델·프롬프트·가드·설정 해시와 같은 입력의 캐시 해시를 검사한다. 캐시가 없거나 다르면 새 모델 호출 없이 준비를 중단한다.

이것은 **LLM 미사용 상태와 기존 LLM 보완 결과의 비교**다. 실시간 모델 추론이나 실제 처리 속도 시연이라고 말하지 않는다. 시연 서버의 새 업로드 자동 LLM 호출은 꺼져 있다. 현재 개발 수치와 평가용 캐시는 그대로 보존하고 test 자료·정답·응답을 사용하지 않는다. `guarded-replay/receipt.json`과 `demo_manifest.json`에 재생 문서 수·변경 필드 수·모델 버전·출처·새 LLM 호출 0건을 기록한다.

[C업체 프로필](../architecture/c_company_profile.md) · [LLM 설정](../eval/llm_settings.md) · [설명 문서 목차](../submission/explanation_outline.md)
