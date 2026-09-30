@echo off
chcp 65001 > nul
title AI Contract Evidence Manager - Single Production Server

echo ========================================================
echo  AI Contract Evidence Manager - 단일 통합 서버 실행기
echo  (포트 8000 하나로 백엔드 API 및 프론트엔드 웹 화면 제공)
echo ========================================================
echo.

where node >nul 2>nul
if %errorlevel% neq 0 (
    echo [오류] Node.js 가 설치되어 있지 않습니다.
    pause
    exit /b 1
)

if not exist "backend\.venv\Scripts\python.exe" (
    echo [안내] 가상환경이 발견되지 않아 초기 설정을 진행합니다...
    call node scripts\setup.js
)

:: 브라우저 자동 실행
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:8000"

:: 단일 통합 서버 시작
node scripts\start.js

pause
