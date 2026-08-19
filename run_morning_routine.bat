@echo off
title Email AI Agent - Routine Matinale
color 0B
echo ===================================================
echo     EMAIL AI AGENT - ROUTINE MATINALE DU JOUR
echo ===================================================
echo.
python "%~dp0email_agent.py" --morning --live
echo.
pause
