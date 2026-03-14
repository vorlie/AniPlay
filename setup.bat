@echo off
setlocal

echo =========================================
echo             AniPlay Setup
echo =========================================
echo.

:: Check if uv is installed
where uv >nul 2>nul
if %errorlevel% neq 0 (
    echo [INFO] 'uv' is not installed. Downloading and installing...
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    :: Add common uv installation paths to PATH for the current session
    set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%LOCALAPPDATA%\uv\bin;%PATH%"
    
    :: Verify installation
    where uv >nul 2>nul
    if %errorlevel% neq 0 (
        :: Direct fallback check
        if exist "%USERPROFILE%\.local\bin\uv.exe" (
            set "UV_CMD=%USERPROFILE%\.local\bin\uv.exe"
        ) else (
            echo [ERROR] Failed to install or locate 'uv'. Please install manually from https://astral.sh/uv
            pause
            exit /b 1
        )
    )
) else (
    echo [INFO] 'uv' is already installed.
)

echo.
echo [INFO] Setting up virtual environment and syncing dependencies...
if not defined UV_CMD set "UV_CMD=uv"

:: Ensure Python 3.14 (or compatible) is installed via uv if not present
echo [INFO] Checking/Installing Python...
%UV_CMD% python install 3.14

%UV_CMD% sync --python 3.14

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 'uv sync' failed. Please check the error message above.
    pause
    exit /b %errorlevel%
)

echo.
echo =========================================
echo       Setup Completed Successfully!
echo =========================================
echo.
echo Your environment is ready. To run the application, activate the virtual 
echo environment and launch the module:
echo.
echo   1. .venv\Scripts\activate
echo   2. python -m aniplay.main
echo   or run "run_aniplay.bat" file.
echo.
pause
