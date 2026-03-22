@echo off
title CodeDojo Launcher
cd /d "%~dp0desktop"
start "" /min cmd /c "npm run dev"
