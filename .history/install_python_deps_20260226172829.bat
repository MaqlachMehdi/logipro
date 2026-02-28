@echo off
REM Script d'installation des dépendances Python pour RegieTour

echo.
echo ============================================================
echo Installing Python Dependencies for RegieTour
echo ============================================================
echo.

REM Essayer pip d'abord
python -m pip install pandas pulp geopy requests matplotlib numpy

if errorlevel 1 (
    echo.
    echo ⚠️  Python not found or pip failed
    echo Trying with python3...
    echo.
    
    python3 -m pip install pandas pulp geopy requests matplotlib numpy
    
    if errorlevel 1 (
        echo.
        echo ❌ ERROR: Could not install packages with either python or python3
        echo Please ensure Python is installed and in your PATH
        echo.
        pause
        exit /b 1
    )
)

echo.
echo ============================================================
echo ✅ Installation Complete!
echo ============================================================
echo.
echo Next steps:
echo 1. Start the backend: cd backend && npm start
echo 2. Start the frontend: npm run dev
echo.
pause
