@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Sotuvchi AI - Telegram bot
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -m pip install -q -r requirements.txt
%PY% bot.py
pause
