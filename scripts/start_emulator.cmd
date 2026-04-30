@echo off
REM 双击本文件也可启动模拟器，窗口会保持打开以便查看报错
cd /d "%~dp0.."
powershell -NoExecutionPolicy Bypass -File "%~dp0start_emulator.ps1"
if errorlevel 1 pause
