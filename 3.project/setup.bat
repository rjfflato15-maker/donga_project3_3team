@echo off
chcp 65001 > nul
title AI Contract Evidence Manager - 초기 환경 설정

echo ========================================================
echo  AI Contract Evidence Manager - 초기 환경 설정 마법사
echo ========================================================
echo.

node scripts\setup.js

echo.
echo 설치가 완료되었습니다. 아무 키나 누르면 창이 닫힙니다.
pause > nul
