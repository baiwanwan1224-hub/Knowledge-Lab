@echo off
chcp 65001 >nul
title Knowledge Lab

echo.
echo   ╔══════════════════════════════════════╗
echo   ║     Knowledge Lab · 自测学习平台      ║
echo   ╚══════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python 3.10+
    echo         https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Check/create .env
if not exist .env (
    echo [SETUP] First run — configuring...
    echo.
    set /p API_KEY="Enter your DeepSeek API Key: "
    echo LLM_API_KEY=!API_KEY!> .env
echo LLM_PROVIDER=deepseek>> .env
    echo VAULT_PATH=./vault>> .env
    echo.
    echo [OK] Configuration saved to .env
)

:: Check dependencies
python -c "import requests" >nul 2>&1
if %errorlevel% neq 0 (
    echo [SETUP] Installing dependencies...
    python -m pip install -r requirements.txt -q
    echo [OK] Dependencies installed
)

:: Create vault structure if missing
if not exist "vault\00_学习笔记" mkdir "vault\00_学习笔记"
if not exist "vault\01_错题本" mkdir "vault\01_错题本"
if not exist "vault\06_产品层" mkdir "vault\06_产品层"
:: Copy templates and standards
if not exist "vault\00_学习笔记\模板_学习笔记.md" copy "templates\模板_学习笔记.md" "vault\00_学习笔记\" >nul
if not exist "vault\01_错题本\模板_错题卡.md" copy "templates\模板_错题卡.md" "vault\01_错题本\" >nul
copy "standards\*" "vault\06_产品层\" >nul 2>&1

echo.
echo   Starting server...
echo.

:: Backup vault before starting (safety net)
if exist "vault\00_学习笔记\*.md" (
    echo   [BACKUP] Auto-backup vault...
    call backup.bat >nul 2>&1
)

:: Load .env and start
for /f "tokens=1,2 delims==" %%a in (.env) do set %%a=%%b
start "" http://localhost:5050
python server/quiz_server.py --port 5050

pause
