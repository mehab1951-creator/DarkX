@echo off
title QUREO Autonomous Red Solver
pip install -r requirements.txt
playwright install chromium
cls
echo ========================================================
echo Autonomous Red Solver is running!
echo Open your browser at: http://localhost:1111
echo ========================================================
python app.py
pause
