@echo off
chcp 65001 >nul
title Knowledge Lab

echo.
echo   ╔══════════════════════════════════════╗
echo   ║     Knowledge Lab · 自测学习平台      ║
echo   ╚══════════════════════════════════════╝
echo.

cd /d "%~dp0"

:: Find working Python
set PYTHON=
for %%p in (
    "C:\Users\27224\AppData\Local\Python\bin\python.exe"
    "C:\Python\python.exe"
    "python"
) do (
    if not defined PYTHON (
        %%~p --version >nul 2>&1
        if not errorlevel 1 set PYTHON=%%~p
    )
)
if not defined PYTHON (
    echo [ERROR] Python not found.
    pause & exit /b 1
)
echo   Python: %PYTHON%

:: Install deps if missing
%PYTHON% -c "import flask,requests,pydantic" >nul 2>&1
if %errorlevel% neq 0 (
    echo   [SETUP] Installing dependencies...
    %PYTHON% -m pip install flask requests pydantic flasgger -q
)

:: Create vault structure
if not exist "vault\00_学习笔记" mkdir "vault\00_学习笔记"
if not exist "vault\01_错题本" mkdir "vault\01_错题本"
if not exist "vault\06_产品层" mkdir "vault\06_产品层"

echo   Starting server on http://localhost:5050 ...
echo.

:: Open browser after a short delay (wait for server)
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:5050"

:: Start Flask server
%PYTHON% -c "import sys; sys.path.insert(0,'.'); from server.app import create_app; create_app().run(host='127.0.0.1',port=5050,debug=False)"

pause
