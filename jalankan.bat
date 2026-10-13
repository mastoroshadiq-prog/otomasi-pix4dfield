@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Ekspor Blok Otomatis
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
