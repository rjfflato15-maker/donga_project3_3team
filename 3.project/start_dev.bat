@echo off
chcp 65001 > nul
title AI Contract Evidence Manager - Dev Server

echo ========================================================
echo  AI Contract Evidence Manager - 개발 서버 실행기
echo  (VS Code 없이 백엔드와 프론트엔드를 동시에 실행합니다)
echo ========================================================
echo.

:: 1. Node.js 확인
where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [오류] Node.js 가 설치되어 있지 않습니다.
    echo https://nodejs.org/ 에서 Node.js 를 설치해주세요.
    pause
    exit /b 1
)

:: 2. Python 가상환경 확인 및 생성 안내
if not exist "backend\.venv\Scripts\python.exe" (
    echo [안내] 가상환경이 발견되지 않아 초기 설정을 진행합니다...
    call node scripts\setup.js
)

:: 3. 브라우저 자동 실행 (2초 후)
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:5173"

:: 4. 통합 개발 서버 시작 (FastAPI 8000 + Vite 5173)
node scripts\dev.js

pause
