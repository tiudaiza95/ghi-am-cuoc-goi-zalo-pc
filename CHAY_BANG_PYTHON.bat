@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
    echo Cai thu vien khong thanh cong.
    pause
    exit /b 1
)
py -3 main.py
if errorlevel 1 pause
