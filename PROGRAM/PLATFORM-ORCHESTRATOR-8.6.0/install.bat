@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Platform Orchestrator INSTALL
echo === One-click install (HARD_CUT) ===
where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: Install Python 3.11+ and add it to PATH.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo Creating .venv...
  python -m venv .venv
  if errorlevel 1 (
    echo ERROR: failed to create .venv
    pause
    exit /b 1
  )
)
call .venv\Scripts\activate.bat
if errorlevel 1 (
  echo ERROR: failed to activate .venv
  pause
  exit /b 1
)
set "DEPS_FILE=requirements.txt"
if exist requirements.lock set "DEPS_FILE=requirements.lock"
for /f "delims=" %%H in ('powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 -LiteralPath '%DEPS_FILE%').Hash"') do set "DEPS_HASH=%%H"
set "NEED_DEPS=1"
if exist .venv\.deps_hash set "NEED_DEPS=0"
if "%NEED_DEPS%"=="0" set /p OLD_HASH=<.venv\.deps_hash
if "%NEED_DEPS%"=="0" if /I not "%OLD_HASH%"=="%DEPS_HASH% set "NEED_DEPS=1"
if "%NEED_DEPS%"=="1" (
  echo Installing %DEPS_FILE%...
  python -m pip install -q --upgrade pip
  if errorlevel 1 (
    echo ERROR: pip bootstrap failed
    pause
    exit /b 1
  )
  python -m pip install -q -r "%DEPS_FILE%"
  if errorlevel 1 (
    echo ERROR: dependency installation failed
    pause
    exit /b 1
  )
  > .venv\.deps_hash echo %DEPS_HASH%
)
if not exist config.yaml copy /Y config.example.yaml config.yaml >nul
if errorlevel 1 (
  echo ERROR: failed to create config.yaml
  pause
  exit /b 1
)
if not exist .env if exist .env.example copy /Y .env.example .env >nul
if not exist data mkdir data
if not exist tokens mkdir tokens
if not exist backups mkdir backups
if not exist logs mkdir logs
set PYTHONPATH=src;scripts
python -m orchestrator.main --version
if errorlevel 1 (
  echo ERROR: version smoke failed
  pause
  exit /b 1
)
echo.
echo Install OK. Run start.bat or:
echo   python -m orchestrator.main --config config.yaml --db data\orch.sqlite --daemon --health-port 8080
echo Panel: http://127.0.0.1:8080/webapp/
pause
exit /b 0
