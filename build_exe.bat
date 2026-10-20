@echo off
chcp 65001 >nul
title Compilation de Email AI Agent v2.0 (.EXE Natif Windows)
cd /d "%~dp0"

echo ===================================================================
echo   COMPILATION DE L'EXECUTABLE PRO : EMAIL AI AGENT v2.0
echo ===================================================================
echo.

echo [1/3] Compilation PyInstaller en cours (Mode Fenetre Native sans console)...
python -m PyInstaller Email_AI_Agent.spec --noconfirm
if %ERRORLEVEL% NEQ 0 (
    echo [ERREUR] Echec de la compilation PyInstaller.
    pause
    exit /b 1
)

echo.
echo [2/3] Synchronisation de la configuration (.env et config.yaml)...
if exist ".env" copy /Y ".env" "dist\Email_AI_Agent\.env" >nul
if exist "config.yaml" copy /Y "config.yaml" "dist\Email_AI_Agent\config.yaml" >nul

echo.
echo [3/3] Creation du raccourci sur le Bureau Windows...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"

echo.
echo ===================================================================
echo   TERMINE AVEC SUCCES !
echo   Exécutable généré : dist\Email_AI_Agent\Email_AI_Agent.exe
echo   Un raccourci "Email AI Agent" a été placé sur votre Bureau.
echo ===================================================================
pause
