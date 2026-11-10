@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Sotuvchi AI - veb-panel
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -m pip install -q -r requirements.txt
start "" http://127.0.0.1:5000
%PY% web.py
pause
