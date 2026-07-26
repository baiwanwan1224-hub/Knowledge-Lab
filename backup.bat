@echo off
chcp 65001 >nul
title Knowledge Lab Backup
REM === Knowledge Lab Vault Backup ===
REM Run: manually or scheduled via Task Scheduler

set "PROJECT_DIR=%~dp0"
set "VAULT=%PROJECT_DIR%vault"
set "BACKUP_ROOT=C:\Users\27224\Documents\Obsidian Vault\Knowledge Lab Backup"
set "TIMESTAMP=%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "BACKUP_DIR=%BACKUP_ROOT%\%TIMESTAMP%"

if not exist "%VAULT%" (
    echo [SKIP] Vault not found, nothing to backup.
    exit /b 0
)

echo [BACKUP] Knowledge Lab vault → Obsidian Vault...
mkdir "%BACKUP_DIR%" 2>nul
xcopy "%VAULT%" "%BACKUP_DIR%" /E /I /Y /Q >nul
echo [OK] Backup saved to: %BACKUP_DIR%

:: Keep only last 30 backups
for /f "skip=30 delims=" %%a in ('dir /b /ad /o-d "%BACKUP_ROOT%\*" 2^>nul') do (
    rmdir /s /q "%BACKUP_ROOT%\%%a" 2>nul
)
echo [OK] Cleaned old backups (keeping latest 30).
