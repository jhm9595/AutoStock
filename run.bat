@echo off
title AutoStock Launcher
cd /d "C:\secjob\AutoStock"

echo ==========================================================
echo  Starting AutoStock Trading System (FastAPI + React)
echo ==========================================================

:: Start backend FastAPI in a minimized window
echo 1. Launching Python FastAPI backend...
start "" /min cmd /c "venv\Scripts\python.exe -m uvicorn src.app:app --port 8000"

:: Start frontend dev server in a minimized window
echo 2. Launching Vite React frontend...
cd frontend
start "" /min cmd /c "npm run dev"

echo ==========================================================
echo  AutoStock started successfully.
echo  Access: http://localhost:5173/
echo ==========================================================
exit
