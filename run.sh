#!/bin/bash
pip install -r requirements.txt
playwright install chromium
clear
echo "========================================================"
echo "Autonomous Red Solver is running!"
echo "Open your browser at: http://localhost:1111"
echo "========================================================"
python3 app.py
