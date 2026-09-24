@echo off
cd /d "%~dp0"
echo Instaluji Diktovatko...
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -m venv .venv || goto :error
".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
echo.
echo Hotovo. Diktovatko spustite dvojklikem na start.bat.
pause
exit /b 0
:error
echo.
echo Instalace selhala. Potrebujete Python 3.11 nebo novejsi z python.org.
pause
exit /b 1
