@echo off
title Nayumi 24/7 Music & Watchdog Bot
color 0b
echo ====================================================
echo          NAYUMI 24/7 DISCORD BOT & MONITOR
echo ====================================================
echo Starting Nayumi Bot and Render Keep-Alive Watchdog...
echo.
cd /d "%~dp0"
python bot.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Bot stopped with error code %ERRORLEVEL%.
    pause
)
