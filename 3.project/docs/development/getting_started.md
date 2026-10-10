# 개발 환경과 실행 명령

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 2026-10-09 구조 정리 소스 사본. 현재 소스와 과거 설치·평가 기록의 검증 범위를 구분한다.

관련 소스: [manage_pilot.py](../../backend/manage_pilot.py) · [config.py](../../backend/app/config.py) · [vite.config.ts](../../frontend/vite.config.ts) · [setup.js](../../tools/dev/node/setup.js)

## 먼저 확인할 것

프로젝트 루트는 `package.json`과 `backend/`, `frontend/`가 함께 있는 폴더다. 제출 ZIP에서는 `3.project`에 해당한다. 아래 명령은 이 폴더의 PowerShell에서 시작한다. Windows x64, Python 3.12, Node.js와 npm이 필요하다. 스캔 OCR은 Windows 한국어 OCR 기능의 영향을 받는다. 먼저 `py -3.12 --version`, `node --version`, `npm.cmd --version`으로 설치 여부를 확인한다.

```powershell
# 최초 설치. 준비된 .venv가 있으면 새로 만들지 않는다.
py -3.12 -m venv backend/.venv
& .\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
npm.cmd --prefix frontend ci
```

가상환경 활성화는 필수가 아니다. 아래처럼 Python 실행 경로를 직접 지정하면 전역 Python과 혼동하지 않는다. `npm.cmd`는 PowerShell에서 npm.ps1 실행 정책 문제를 피하기 위한 Windows 명령이다.

## 고객 자료와 분리한 개발 실행

비어 있는 새 개발 폴더를 지정한다. 기존 DB·설정이 있는 폴더를 초기화 대상으로 선택하지 않는다.

```powershell
$env:APP_DEPLOYMENT_MODE='pilot'
$env:APP_STORAGE_ROOT=Join-Path (Get-Location) 'storage/dev-local'
$env:APP_NTS_MODE='disabled'
$env:APP_LLM_ENABLED='false'
$env:APP_VLM_ENABLED='false'
& .\backend\.venv\Scripts\python.exe backend/manage_pilot.py migrate --empty
& .\backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

`migrate --empty`는 최초 한 번만 실행한다. 이미 `pilot.db`가 있으면 이 단계는 생략한다. 초기 계정은 지정 폴더의 `initial-accounts.txt`에 생성되며 공유하지 않는다. 첫 로그인에서 비밀번호를 변경한다. 백엔드는 `http://127.0.0.1:8000/health`에서 status=ok를 반환해야 한다.

두 번째 PowerShell을 같은 프로젝트 루트에서 열어 화면을 실행한다.

```powershell
npm.cmd --prefix frontend run dev -- --host 127.0.0.1
```

출력된 Vite 주소로 접속한다. 보통 5173이며, 포트가 바뀌면 [CORS 설정](../ai/runtime_settings.md)도 확인한다. 개발용 서버는 Ctrl+C로 종료한다. 운영 실행기로 시작한 서버는 [관리 메뉴](../operations/startup_settings.md)에서 종료한다.

기존 `npm run dev` 도구는 백엔드를 0.0.0.0에 바인딩하고, `npm run setup` 도구는 설치 실패 뒤에도 완료 문구를 출력할 수 있다. 처음에는 위 명시적 명령과 종료 코드를 기준으로 확인한다.

## 다음 읽기

[전체 동작](../architecture/overview.md) → [파일 책임](../architecture/module_map.md) → [수정 작업표](maintenance_cheat_sheet.md) → [테스트와 빌드](test_and_verification.md).


[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
