@echo off
REM ===== TEACHIUM AI Tutor - interface React sur http://localhost:5173 =====
cd /d "%~dp0frontend"
if not exist "node_modules" (
    echo Installation des dependances npm...
    call npm install
)
call npm run dev
