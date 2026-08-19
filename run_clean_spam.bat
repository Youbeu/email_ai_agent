@echo off
title Email AI Agent - Nettoyage Anti-Spam & Désabonnement
color 0C
echo ===================================================
echo     EMAIL AI AGENT - NETTOYAGE SPAM & DESABONNEMENT
echo ===================================================
echo.
python "%~dp0email_agent.py" --clean-spam --live
echo.
pause
