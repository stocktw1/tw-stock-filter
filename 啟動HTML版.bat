@echo off
chcp 65001 >nul
title 台股技術指標篩選器 - HTML/Web 版
echo ===================================================
echo   正在啟動 台股技術指標篩選器 HTML/Web 版...
echo ===================================================
echo.
"C:\Users\dou543\AppData\Local\Python\bin\python.exe" "%~dp0server.py"
pause
