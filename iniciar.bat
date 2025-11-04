@echo off
color 0A
chcp 65001 >nul 2>&1
cls

echo ═══════════════════════════════════════════
echo   GGRevealer v1.0.0 - Iniciando...
echo ═══════════════════════════════════════════
echo.

REM Verificar que el entorno virtual existe
if not exist "venv\Scripts\activate.bat" (
    color 0C
    echo [ERROR] El entorno virtual no existe. Ejecuta primero: instalar.bat
    echo.
    pause
    exit /b 1
)

REM Advertencia si .env no existe
if not exist ".env" (
    color 0E
    echo [ADVERTENCIA] Archivo .env no encontrado.
    echo La aplicación podría no funcionar correctamente sin configuración.
    echo.
    set /p continuar="¿Continuar? (S/N): "
    if /i not "%continuar%"=="S" (
        echo.
        echo [*] Operación cancelada.
        pause
        exit /b 0
    )
    color 0A
    echo.
)

REM Activar entorno virtual
echo [*] Activando entorno virtual...
call venv\Scripts\activate.bat
if errorlevel 1 (
    color 0C
    echo [ERROR] No se pudo activar el entorno virtual.
    pause
    exit /b 1
)
echo [OK] Entorno virtual activado.
echo.

REM Iniciar FastAPI
echo [*] Iniciando FastAPI en http://localhost:8000
echo ════════════════════════════════════════════
echo.
echo Presiona Ctrl+C para detener la aplicación
echo.

REM Esperar 3 segundos y abrir navegador
timeout /t 3 /nobreak >nul
start http://localhost:8000

REM Ejecutar servidor
python main.py

REM Al detener con Ctrl+C
echo.
echo [OK] Aplicación detenida.
pause
