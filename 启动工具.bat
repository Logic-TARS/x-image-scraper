@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title XScrape - X media scraper
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "ENV_DIR=%~dp0.conda"
set "ENV_PYTHON=%ENV_DIR%\python.exe"

:: ========== Check Python environment ==========
call :CHECK_ENV
if errorlevel 1 (
    echo.
    echo [ERROR] Conda not found. Please install Miniconda first.
    echo         https://docs.conda.io/en/latest/miniconda.html
    echo.
    pause
    exit /b 1
)

:: ========== Launch web UI ==========
:START
cls
echo ===========================================
echo     XScrape - X/Twitter Media Scraper
echo     Starting web UI in your browser...
echo ===========================================
echo.

call :ENSURE_ENV
if errorlevel 1 pause & goto END
call :VERIFY_DEPS
if errorlevel 1 pause & goto END

"%ENV_PYTHON%" -m streamlit run "%~dp0webui.py"
if errorlevel 1 (
    echo.
    echo [INFO] First run detected. Installing dependencies (browser mode)...
    "%ENV_PYTHON%" -m pip install -e ".[all]"
    if errorlevel 1 (
        echo [ERROR] Install failed. Try running as Administrator.
        pause
        goto END
    )
    "%ENV_PYTHON%" -m playwright install chromium
    "%ENV_PYTHON%" -m streamlit run "%~dp0webui.py"
)

echo.
echo ===========================================
echo     Done!
echo ===========================================
echo   Output folder: output\
echo   Log file: logs\scraper.log
echo.

set "act="
set /p act="[O] Open output folder  [R] Restart  [other] Exit: "
if /i "!act!"=="O" (
    if exist "output\" (
        start "" "output\"
    )
)
if /i "!act!"=="R" (
    cls
    goto START
)

:END
cls
echo Goodbye!
timeout /t 2 /nobreak >nul
exit /b 0

:CHECK_ENV
where conda >nul 2>&1
if errorlevel 1 exit /b 1
exit /b 0

:ENSURE_ENV
if exist "%ENV_PYTHON%" exit /b 0

echo -- First run: creating local Python environment...
echo    (One-time setup, about 1-2 minutes)
echo.
call conda create -y -p "%ENV_DIR%" python=3.12
if errorlevel 1 (
    echo [ERROR] Failed to create environment. Check your network.
    exit /b 1
)

echo -- Installing dependencies (includes Playwright)...
"%ENV_PYTHON%" -m pip install -e ".[all]"
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    exit /b 1
)

echo -- Installing Playwright browser (Chromium)...
"%ENV_PYTHON%" -m playwright install chromium
if errorlevel 1 (
    echo [WARN] Playwright browser install failed. X search may not work.
)

echo -- Ready!
exit /b 0

:VERIFY_DEPS
"%ENV_PYTHON%" -c "import xscrape, streamlit, playwright" >nul 2>&1
if not errorlevel 1 exit /b 0

echo -- Installing missing dependencies (includes Playwright)...
"%ENV_PYTHON%" -m pip install -e ".[all]"
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    exit /b 1
)

"%ENV_PYTHON%" -c "import xscrape, streamlit, playwright" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Dependency verification failed after install.
    exit /b 1
)

echo -- Installing Playwright browser (Chromium)...
"%ENV_PYTHON%" -m playwright install chromium
if errorlevel 1 (
    echo [WARN] Playwright browser install failed. X search may not work.
)
exit /b 0
