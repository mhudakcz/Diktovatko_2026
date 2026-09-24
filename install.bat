@echo off
cd /d "%~dp0"
echo Instaluji Diktovatko...
where py >nul 2>nul && (set PY=py) || (set PY=python)
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" || goto :pyversion
%PY% -m venv .venv || goto :error
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt || goto :error
echo.
echo Hotovo. Diktovatko spustite dvojklikem na start.bat.
pause
exit /b 0
:pyversion
echo.
echo Diktovatko potrebuje Python 3.11 nebo novejsi z python.org.
pause
exit /b 1
:error
echo.
echo Instalace selhala. Potrebujete Python 3.11 nebo novejsi z python.org a pripojeni k internetu.
pause
exit /b 1
