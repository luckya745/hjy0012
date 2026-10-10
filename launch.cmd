@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "GAME_PYTHON="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if not errorlevel 1 set "GAME_PYTHON=py -3"
if defined GAME_PYTHON goto ready
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if not errorlevel 1 set "GAME_PYTHON=python"
if defined GAME_PYTHON goto ready
set "GAME_BUNDLED=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if not exist "%GAME_BUNDLED%" goto missing
"%GAME_BUNDLED%" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>nul
if errorlevel 1 goto missing
set GAME_PYTHON="%GAME_BUNDLED%"
:ready
echo Python runtime found.
if /i "%~1"=="--check" goto check
set "PYTHONPATH=%~dp0.packages;%PYTHONPATH%"
%GAME_PYTHON% -c "import importlib.util,sys; sys.exit(0 if all(importlib.util.find_spec(m) for m in ['roboid','serial','sqlalchemy','streamlit','psycopg']) else 1)" >nul 2>nul
if not errorlevel 1 goto run
echo Installing game libraries. Internet is required for the first run.
set "TEMP=%~dp0.install-temp"
set "TMP=%TEMP%"
if not exist "%TEMP%" mkdir "%TEMP%"
%GAME_PYTHON% -m pip install --target "%~dp0.packages" -r requirements-local.txt
if errorlevel 1 goto installfailed
:run
if /i "%~1"=="--admin" goto admin
echo Starting game server...
%GAME_PYTHON% bridge.py
goto finish
:admin
if exist ".streamlit\secrets.toml" goto adminrun
%GAME_PYTHON% setup_admin.py
if errorlevel 1 goto finish
:adminrun
set "ESCAPE_LOCAL=1"
%GAME_PYTHON% -m streamlit run streamlit_app.py --server.address 127.0.0.1
goto finish
:check
if not exist "bridge.py" exit /b 2
if not exist "dist\index.html" exit /b 3
%GAME_PYTHON% -c "import sys; print('Verified Python: '+sys.executable)"
exit /b 0
:missing
echo No working Python 3.11+ runtime found. Install Python with PATH enabled.
goto finish
:installfailed
echo Robot library installation failed. Check the error above and internet access.
:finish
pause
