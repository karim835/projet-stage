@echo off
REM ===== TEACHIUM AI Tutor - API FastAPI sur http://127.0.0.1:8000 =====
cd /d "%~dp0backend"
call .venv\Scripts\activate
uvicorn app.main:app --reload
