@echo off
REM ===== Tableau de bord Streamlit historique (optionnel, non requis) =====
REM L'interface principale de l'application est le frontend React.
cd /d "%~dp0"
call backend\.venv\Scripts\activate
streamlit run dashboard\dashboard.py
