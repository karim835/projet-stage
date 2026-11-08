@echo off
REM ===== TEACHIUM AI Tutor - installation du backend (Windows) =====
cd /d "%~dp0backend"

if not exist ".venv" (
    echo Creation de l'environnement virtuel...
    python -m venv .venv
)

call .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist ".env" (
    echo.
    echo ATTENTION : le fichier backend\.env est absent.
    echo Copiez backend\.env.example vers backend\.env puis collez votre chaine Neon.
    echo.
    pause
    exit /b 1
)

echo.
echo Initialisation de la base Neon ^(tables + dataset + comptes de demo^)...
python scripts\init_database.py

echo.
echo Installation terminee. Lancez run_backend.bat puis run_frontend.bat.
pause
