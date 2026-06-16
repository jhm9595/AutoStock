@echo off
title AutoStock Terminator
echo ==========================================================
echo  Terminating AutoStock Processes...
echo ==========================================================

:: Kill uvicorn / python process
taskkill /f /im python.exe /fi "WINDOWTITLE eq uvicorn" >nul 2>&1
:: Fallback kill general python uvicorn
taskkill /f /t /fi "COMMANDLINE eq *uvicorn*" >nul 2>&1
:: Kill python uvicorn specifically if started from venv
wmic process where "commandline like '%%uvicorn%%'" delete >nul 2>&1

:: Kill node / vite process
wmic process where "commandline like '%%vite%%'" delete >nul 2>&1

echo AutoStock system stopped successfully.
pause
exit
