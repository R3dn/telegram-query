@echo off
title Telegram Sync
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python sync.py
echo.
pause
