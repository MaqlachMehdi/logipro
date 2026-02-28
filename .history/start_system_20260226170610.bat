@echo off
REM Script pour démarrer le système VRP complet

echo.
echo ============================================================
echo   VRP System Launcher
echo ============================================================
echo.

REM Vérifier si Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python n'est pas installé ou pas dans le PATH
    echo    Veuillez installer Python 3.8+ et ajouter à PATH
    pause
    exit /b 1
)
echo ✅ Python détecté

REM Vérifier si Node.js est installé
node --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Node.js n'est pas installé
    echo    Veuillez installer Node.js 16+
    pause
    exit /b 1
)
echo ✅ Node.js détecté: %*

REM Installer les dépendances du backend si nécessaire
echo.
echo 📦 Vérification des dépendances Node...
if not exist "backend\node_modules" (
    echo   Installing backend dependencies...
    cd backend
    call npm install
    cd ..
)
echo ✅ Node dependencies OK

REM Vérifier les dépendances Python
echo.
echo 📦 Vérification des dépendances Python...
python -c "import pandas, pulp, geopy, requests, matplotlib, numpy" 2>nul
if errorlevel 1 (
    echo   ⚠️  Installation des dépendances Python...
    pip install pandas pulp geopy requests matplotlib numpy
)
echo ✅ Python dependencies OK

REM Démarrer le backend
echo.
echo 🚀 Démarrage du Backend...
echo   http://localhost:5000
start "VRP Backend" cmd /k "cd backend && npm start"

REM Attendre que le backend soit prêt
timeout /t 3 /nobreak

REM Démarrer le frontend
echo.
echo 🚀 Démarrage du Frontend...
echo   http://localhost:5173
start "VRP Frontend" cmd /k "npm run dev"

echo.
echo ============================================================
echo ✅ Système démarré!
echo ============================================================
echo.
echo 📍 Frontend:  http://localhost:5173
echo 📍 Backend:   http://localhost:5000
echo.
echo Appuyez sur une touche pour fermer cette fenêtre...
pause >nul
