@echo off
echo ========================================
echo    GGRevealer - Iniciando servidor
echo ========================================
echo.

REM Verificar si Python está instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python no está instalado o no está en el PATH
    echo Por favor instala Python 3.11 o superior desde https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo Python detectado correctamente
echo.

REM Verificar si existe el archivo .env
if not exist .env (
    echo ADVERTENCIA: No se encontró el archivo .env
    echo Por favor copia .env.example a .env y agrega tu API key de Gemini
    echo.
    pause
    exit /b 1
)

echo Archivo .env encontrado
echo.

REM Verificar si las dependencias están instaladas
echo Verificando dependencias...
pip show fastapi >nul 2>&1
if errorlevel 1 (
    echo Las dependencias no están instaladas. Instalando...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: No se pudieron instalar las dependencias
        echo Intenta ejecutar manualmente: pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
) else (
    echo Dependencias ya instaladas
)

echo.
echo ========================================
echo  Iniciando GGRevealer en puerto 8000
echo  Abre tu navegador en: http://localhost:8000
echo ========================================
echo.
echo Presiona Ctrl+C para detener el servidor
echo.

REM Iniciar el servidor
python main.py

REM Si el servidor termina, pausar para ver errores
if errorlevel 1 (
    echo.
    echo ERROR: El servidor se detuvo con errores
    echo.
    pause
)
