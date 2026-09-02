@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 台股技術指標篩選器 Web 版
echo 正在啟動 台股技術指標篩選器 Web 版...
python -m streamlit run "股票技術指標篩選器_Web.py"
pause
