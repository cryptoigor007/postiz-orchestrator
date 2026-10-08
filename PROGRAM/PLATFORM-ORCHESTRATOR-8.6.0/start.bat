@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Platform Orchestrator HARD_CUT
echo ==========================================
echo  Platform Orchestrator - HARD_CUT start
echo ==========================================

where python >nul 2>&1
if errorlevel 1 (
  echo ERROR: python not in PATH. Install Python 3.11+ and retry.
  pause
  exit /b 1
)

if not exist .venv\Scripts\python.exe (
  echo [1/5] Creating venv...
  python -m venv .venv
  if errorlevel 1 (
    echo ERROR: failed to create .venv
    pause
    exit /b 1
  )
) else (
  echo [1/5] venv exists
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
  echo [2/5] Installing %DEPS_FILE%...
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
) else (
  echo [2/5] Dependencies current; %DEPS_FILE% ready
)

if not exist config.yaml (
  echo [3/5] config.yaml from example
  copy /Y config.example.yaml config.yaml >nul
  if errorlevel 1 (
    echo ERROR: failed to create config.yaml
    pause
    exit /b 1
  )
) else (
  echo [3/5] config.yaml exists
)

if not exist data mkdir data
if not exist tokens mkdir tokens
if not exist backups mkdir backups
if not exist logs mkdir logs
if not exist .env if exist .env.example copy /Y .env.example .env >nul

set PYTHONPATH=src;scripts
echo [4/5] Smoke dry-run...
python -m orchestrator.main --version
if errorlevel 1 (
  echo ERROR: version check failed
  pause
  exit /b 1
)
python -m orchestrator.main --config config.yaml --db data\orch.sqlite --dry-run --once
if errorlevel 1 (
  echo ERROR: dry-run failed
  pause
  exit /b 1
)

echo [5/5] Health/WebApp http://127.0.0.1:8080  (Ctrl+C to stop)
echo       Panel: http://127.0.0.1:8080/webapp/
python -m orchestrator.main --config config.yaml --db data\orch.sqlite --daemon --health-port 8080
set RC=%ERRORLEVEL%
pause
exit /b %RC%
