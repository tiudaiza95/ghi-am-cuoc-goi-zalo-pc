@echo off
setlocal
cd /d "%~dp0"
py -3 -m pip install -r requirements-lock.txt
if errorlevel 1 goto fail
py -3 packaging\build_release.py
if errorlevel 1 goto fail
echo Release created in release\Ghi-Am-Zalo-PC-2.9.0
pause
exit /b 0
:fail
echo Build failed. See the error above.
pause
exit /b 1
