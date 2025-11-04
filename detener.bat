@echo off
chcp 65001 > nul
color 0E

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║                    GGRevealer v1.0.0                           ║
echo ║                      Deteniendo...                             ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

echo [*] Buscando procesos en puerto 8000...
echo.

REM Buscar proceso escuchando en puerto 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    set PID=%%a
    goto :found
)

REM No se encontró proceso
color 0A
echo [OK] No hay procesos corriendo en puerto 8000.
echo.
pause
exit /b 0

:found
echo [*] Encontrado proceso con PID: %PID%
echo [*] Deteniendo proceso...
echo.

REM Intentar detener el proceso
taskkill /PID %PID% /F /Q > nul 2>&1

REM Verificar si se detuvo correctamente
if errorlevel 1 (
    color 0C
    echo [ERROR] No se pudo detener el proceso.
    echo.
    pause
    exit /b 1
) else (
    color 0A
    echo [OK] Proceso detenido exitosamente.
    echo.
    pause
    exit /b 0
)
