Write-Host "==========================================================" -ForegroundColor Green
Write-Host " Starting AutoStock Trading System (FastAPI + React) " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green

# Start FastAPI backend in a new window
Write-Host "1. Starting Python FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\venv\Scripts\python.exe -m uvicorn src.app:app --port 8000 --reload"

# Start Vite React frontend in the current window
Write-Host "2. Starting Vite React frontend on http://localhost:5173..." -ForegroundColor Cyan
cd frontend
npm run dev
