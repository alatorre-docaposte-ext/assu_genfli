@echo off
REM =============================================================
REM  Script de build Windows pour assu_genfli (IHM tkinter)
REM  Crée un dossier autonome sans dépendance externe
REM =============================================================

echo [1/4] Verification de Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR : Python n'est pas installe ou pas dans le PATH.
    pause
    exit /b 1
)

echo [2/4] Installation des dependances...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERREUR : Echec de l'installation des dependances.
    pause
    exit /b 1
)

echo [3/4] Nettoyage des anciens artefacts...
if exist build   rmdir /s /q build
if exist dist    rmdir /s /q dist

echo [4/4] Compilation avec PyInstaller...
pyinstaller --noconfirm assu_genfli.spec
if errorlevel 1 (
    echo ERREUR : La compilation a echoue.
    pause
    exit /b 1
)

echo.
echo ============================================
echo  Build termine avec succes !
echo  Livrable : dist\assu_genfli\
echo  Executable : dist\assu_genfli\assu_genfli.exe
echo.
echo  Copier le dossier dist\assu_genfli\ en entier
echo  sur la machine de production.
echo  Aucune installation supplementaire requise.
echo ============================================
pause
