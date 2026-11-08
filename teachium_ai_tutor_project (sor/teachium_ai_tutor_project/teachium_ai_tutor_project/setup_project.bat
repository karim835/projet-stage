@echo off
python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
python scripts\generate_dataset.py
python scripts\train_models.py
python scripts\generate_diagrams.py
echo Setup finished. Run run_api.bat then run_dashboard.bat in another terminal.
