@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PROGRAM_DIR=%~dp0Programme-Rust"
if not exist "%PROGRAM_DIR%\build\NeuronNet-Rust.spec" set "PROGRAM_DIR=%~dp0Programme"
pushd "%PROGRAM_DIR%" || exit /b 1
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYINSTALLER_CONFIG_DIR=%CD%\build\pyinstaller-cache"
set "SPEC=%CD%\build\NeuronNet-Rust.spec"
set "VERSION_HELPER=%CD%\build\version_build.py"
set "DLL=%CD%\rust\training.dll"
set "DIST=%CD%\dist"
set "STAGE=%CD%\build\package-rust"
set "EXE=%DIST%\NeuronNet.exe"

echo.
echo NeuronNet Rust - EXE erstellen
echo Ziel: "%EXE%"
echo.

if not exist "%SPEC%" (
    echo FEHLER: Die PyInstaller-Konfiguration fehlt.
    goto failure
)
set "PY_LAUNCHER="
for /f "delims=" %%P in ('where.exe py.exe') do if not defined PY_LAUNCHER set "PY_LAUNCHER=%%P"
if not defined PY_LAUNCHER (
    echo FEHLER: Der Python-Launcher py.exe wurde nicht gefunden.
    goto failure
)

"%PY_LAUNCHER%" -3.14 -m PyInstaller --version >nul
if errorlevel 1 (
    echo FEHLER: Python 3.14 mit PyInstaller wird benoetigt.
    goto failure
)

"%PY_LAUNCHER%" -3.14 "%VERSION_HELPER%" choose
set "VERSION_RESULT=%ERRORLEVEL%"
if "%VERSION_RESULT%"=="2" goto cancelled
if "%VERSION_RESULT%"=="10" goto public_build
if "%VERSION_RESULT%"=="11" goto author_build
goto failure

:public_build
set "NEURONNET_BUILD_FLAVOR=public"
goto build

:author_build
set "NEURONNET_BUILD_FLAVOR=author"

:build
if not exist "%DLL%" (
    "%PY_LAUNCHER%" -3.14 "%CD%\build\build_training_dll.py"
    if errorlevel 1 goto rollback
)
rem Fremde DLL-Suchpfade koennen inkompatible Systembibliotheken in die EXE ziehen.
set "PATH=%SystemRoot%\System32;%SystemRoot%;%SystemRoot%\System32\Wbem"
"%PY_LAUNCHER%" -3.14 -m PyInstaller --noconfirm --clean --distpath "%STAGE%" --workpath "%CD%\build\pyinstaller-rust" "%SPEC%"
if errorlevel 1 (
    echo FEHLER: Die EXE konnte nicht erstellt werden.
    goto rollback
)

"%PY_LAUNCHER%" -3.14 "%CD%\build\publish_rust_exe.py" "%STAGE%\NeuronNet.exe" "%DLL%" "%EXE%"
if errorlevel 1 (
    echo FEHLER: Die Rust-DLL konnte nicht bestätigt werden oder die Ziel-EXE ist gesperrt.
    echo Falls NeuronNet aus dem Testordner noch läuft, bitte schließen und erneut starten.
    goto rollback
)
rmdir "%STAGE%" 2>nul
"%PY_LAUNCHER%" -3.14 "%VERSION_HELPER%" commit
if errorlevel 1 echo WARNUNG: Der Build war erfolgreich, aber der Versionsabschluss ist fehlgeschlagen.
echo.
echo Fertig. Die EXE enthält die Rust-DLL:
echo "%EXE%"
set /p "BUILD_VERSION=" < "%CD%\VERSION.txt"
echo Version: %BUILD_VERSION%
if /I not "%~1"=="--no-pause" explorer.exe /select,"%EXE%"
set "RESULT=0"
goto finish

:cancelled
set "RESULT=0"
goto finish

:rollback
"%PY_LAUNCHER%" -3.14 "%VERSION_HELPER%" rollback

:failure
set "RESULT=1"

:finish
popd
echo.
if /I not "%~1"=="--no-pause" pause
exit /b %RESULT%
