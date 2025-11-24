@echo off
echo ========================================
echo Building multiplecam.exe
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found in PATH!
    echo Please make sure Python is installed and added to PATH.
    pause
    exit /b 1
)

REM Check if PyInstaller is installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo [ERROR] PyInstaller is not installed!
    echo.
    echo Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller!
        echo Please install it manually: pip install pyinstaller
        pause
        exit /b 1
    )
    echo [INFO] PyInstaller installed successfully!
    echo.
)

echo [INFO] Cleaning previous build...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [INFO] Building executable...
python -m PyInstaller multiplecam.spec

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Build completed successfully!
echo ========================================
echo.
echo Executable location: dist\multiplecam.exe
echo.
pause

