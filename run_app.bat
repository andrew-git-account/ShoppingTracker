@echo off
REM Shopping Tracker - Run Script for Windows
REM Double-click this file to start the application

echo ============================================================
echo Starting Shopping Tracker...
echo ============================================================
echo.

REM Change to project directory
cd /d "%~dp0"

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if activation succeeded
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    echo Please run: python -m venv venv
    echo Then run: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo ============================================================
echo Virtual environment activated!
echo Starting Flask application...
echo ============================================================
echo.

REM Run the application as a module (not as a script)
python -m app.main

REM If we get here, the app has stopped
echo.
echo ============================================================
echo Application stopped.
echo ============================================================
pause
