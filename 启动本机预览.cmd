@echo off
cd /d "%~dp0"
python tools\desktop_demo.py
if errorlevel 1 pause
