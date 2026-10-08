@echo off
cd /d "%~dp0.."
".venv\Scripts\python.exe" "serve.py" >> "logs\app.log" 2>&1
