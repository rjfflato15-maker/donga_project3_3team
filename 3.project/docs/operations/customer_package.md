# Windows Setup 설치와 검증 범위

> 상태: 현재 기준
> 확인일: 2026-10-09
> 기준: 현재 소스의 설치 도구와 이전 Windows x64 1.0.0 설치 기록. 이번 소스의 Setup 재빌드·Windows 실행은 미검증.

관련 소스: [build_package.py](../../tools/installer/build_package.py) · [build_setup.ps1](../../tools/installer/build_setup.ps1) · [C-Pilot.iss](../../tools/installer/C-Pilot.iss) · [ai_setup.py](../../backend/launcher/ai_setup.py)

## 현재 제공 범위

이번 ZIP은 소스 전용이며 설치 EXE를 포함하지 않는다. EXE 재빌드는 이번 구조 정리의 범위가 아니다. 소스 실행은 [개발 환경](../development/getting_started.md)과 [소스 설치](installation.md)를 따른다. 아래는 설치 도구의 동작과 이전 버전의 시험 범위다.

## 별도로 빌드한 Setup의 사용 방법

Windows에서 해당 버전의 소스로 빌드·검증한 C-Pilot-Setup-1.0.0.exe를 실행한다. 한국어 설치 마법사이며 현재 Windows 사용자 계정에 설치한다. Python 실행 환경·필수 라이브러리·빌드된 화면이 포함되어 Python과 Node.js를 따로 설치할 필요가 없다. 설치 후 C-Pilot 바로가기를 실행하면 CMD 창 없이 브라우저에서 앱을 연다. 첫 실행에 빈 업무함과 담당자·대표 초기 계정 안내가 생성되며 첫 로그인에서 비밀번호를 바꾼다.

기본 앱 경로는 %LOCALAPPDATA%/Programs/C-Pilot, 자료·설정·로그·백업은 %LOCALAPPDATA%/C-Pilot 아래다. 설치 파일에는 고객 DB·계정·원문·환경 설정·로그·모델이 없다. 기본 실행은 로컬 접속이다. 사내 다른 PC 접속은 [네트워크 운영](network.md)에 따라 별도로 설정한다.

## AI와 관리

로컬 AI 준비는 설치 마지막 단계의 선택 항목이다. 기본 선택하지 않으며 모델 가중치는 Setup에 포함하지 않는다. 선택하면 Ollama와 Qwen 모델을 인터넷으로 준비한다. 기존 모델 서버는 임의로 종료하지 않으며 연결과 모델 확인이 완료된 뒤 AI 사용을 켠다. 다운로드·GPU·한국어 OCR 준비는 PC 환경에 따라 확인해야 한다.

평소에는 C-Pilot 바로가기를 사용한다. 백업·복구·서버 종료 등은 시작 메뉴의 C-Pilot 관리(백업·복구)를 명시적으로 열어 수행한다. 앱 제거·업데이트는 업무 자료 폴더를 삭제하지 않는다. 업데이트 전에 진행 중인 검수와 저장을 마치고 백업한다.

## 이전 버전에서 확인한 범위

이전 Windows 작업 기록에서는 동일 실행 payload를 별도 AppId·설치 폴더·사용자 자료 폴더로 분리해 현재 PC에서 조용한 설치 → 실행 → 업데이트 → 재실행 → 제거를 시험했다. 기존 C-Pilot 설치 기록과 다른 AppId를 사용해 기존 설치를 덮어쓰지 않았다. PATH에서 개발용 Python·Node를 제외한 상태로 번들 Python import, 빈 DB와 초기 계정, 복구용 신규 테이블, health·화면·assets 응답을 확인했다. 업데이트와 제거 후 별도 DB·자료 보존 표식이 남았다.

이는 당시 PC의 격리 설치 시험이며 이번 구조 정리 소스의 실행 결과가 아니다. 설치 마법사 화면의 직접 시각 점검, 완전히 새 PC·다른 Windows 환경, 실제 AI 모델 다운로드·오프라인 반입·제품 코드 서명은 별도 확인 대상으로 남는다. 기존 OCR 언어 팩을 설치 파일이 자동 준비하는 것은 아니다. [최신 검증](../development/verification_latest.md)을 함께 읽는다.

## 재빌드와 라이브러리 고지

개발 환경에서 frontend npm run build, tools/launcher/build_launcher.ps1, tools/installer/build_setup.ps1 순서로 빌드한다. Windows x64 Python 3.12 환경과 Inno Setup 컴파일러가 필요하다. 빌드 결과는 dist/C-Pilot-Setup-1.0.0.exe와 SHA-256 파일이다. 설치형 배포를 할 때만 변경된 소스와 같은 버전의 Setup을 재빌드·검증한다. 소스 전용 배포에는 Setup 재빌드가 필요하지 않다.

라이브러리 고지는 payload의 licenses와 Python dist-info에 보존한다. HWP 판독용 pyhwp는 AGPLv3+다. 모델·외부 라이브러리·설치 도구의 판매 배포 조건, 대응 소스와 제품 서명은 상용 판매 전에 따로 확인한다. 설치 빌드 통과를 상용 배포 조건 확인 완료로 표시하지 않는다.

[전체 문서](../README.md) · [현재 구현 상태](../progress/current_status.md)
