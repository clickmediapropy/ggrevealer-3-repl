@echo off
chcp 65001 >nul
cls

echo.
echo  ═══════════════════════════════════════════════════════════════
echo  ║                                                             ║
echo  ║              GGRevealer v1.0.0                              ║
echo  ║         Reinstalando Dependencias                           ║
echo  ║                                                             ║
echo  ═══════════════════════════════════════════════════════════════
echo.

color 0E

REM Verificar que el entorno virtual existe
if not exist "venv\" (
    color 0C
    echo [ERROR] El entorno virtual no existe.
    echo [ERROR] Ejecuta instalar.bat primero.
    echo.
    pause
    exit /b 1
)

REM Activar el entorno virtual
echo [*] Activando entorno virtual...
call venv\Scripts\activate.bat
if errorlevel 1 (
    color 0C
    echo [ERROR] No se pudo activar el entorno virtual.
    echo.
    pause
    exit /b 1
)

echo.
echo [*] Reinstalando dependencias (forzado)
echo [*] Esto puede tardar 3-10 minutos
echo ════════════════════════════════════════════
echo.

REM Reinstalar todas las dependencias forzadamente
pip install -r requirements.txt --force-reinstall --no-cache-dir
if errorlevel 1 (
    color 0C
    echo.
    echo ════════════════════════════════════════════
    echo [ERROR] No se pudieron reinstalar las dependencias.
    echo.
    pause
    exit /b 1
)

color 0A
echo.
echo ════════════════════════════════════════════
echo [OK] ¡Dependencias reinstaladas exitosamente!
echo.
pause
