@echo off
title Email AI Agent v2.0 - Poste de Pilotage
cd /d "%~dp0"
if exist "dist\Email_AI_Agent\Email_AI_Agent.exe" (
    start "" "dist\Email_AI_Agent\Email_AI_Agent.exe"
) else (
    start "" pythonw desktop_app.py
)
