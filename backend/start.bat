@echo off
cd /d C:\Users\rapha\Advisor-Console\backend
python -m uvicorn main:app --reload --port 8000
pause
