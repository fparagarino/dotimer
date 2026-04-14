@echo off
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found. Download it from https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during installation.
    pause
    exit /b
)
echo Installing DoTimer dependencies...
pip install pynput pyttsx3
echo Done.
pause
