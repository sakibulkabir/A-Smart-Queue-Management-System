
@echo off
title QueueLess BD Setup
cd /d "%~dp0"

where py >nul 2>nul || (
    echo Python Launcher not found.
    pause
    exit /b 1
)

where node >nul 2>nul || (
    echo Node.js not found.
    pause
    exit /b 1
)

if not exist backend\.env copy backend\.env.example backend\.env
if not exist frontend\.env copy frontend\.env.example frontend\.env

echo Setting up Python environment...
cd /d "%~dp0backend"

if not exist .venv (
    py -3.12 -m venv .venv
)

.venv\Scripts\python.exe -m pip install -r requirements.txt

if errorlevel 1 (
    echo Backend installation failed.
    pause
    exit /b 1
)

echo Setting up frontend...
cd /d "%~dp0frontend"

call npm install

if errorlevel 1 (
    echo Frontend installation failed.
    pause
    exit /b 1
)

echo Starting QueueLess API...
start "QueueLess API" cmd /k "cd /d ""%~dp0backend"" && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"

echo Starting QueueLess Web...
start "QueueLess Web" cmd /k "cd /d ""%~dp0frontend"" && npm run dev -- --host 127.0.0.1"

timeout /t 5 >nul
start http://localhost:5173

echo QueueLess BD started.
pause
