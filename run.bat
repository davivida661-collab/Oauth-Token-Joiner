@echo off
title UtilityToolsV2 - OAuth Joiner

if not exist venv (
echo Creating virtual environment...
python -m venv venv

```
echo Activating venv...
call venv\Scripts\activate

echo Installing requirements...
pip install --upgrade pip
pip install -r requirements.txt
```

) else (
echo Activating existing venv...
call venv\Scripts\activate
)

echo Starting UtilityToolsV2...
python joiner.py

echo.
echo Program exited.
pause
