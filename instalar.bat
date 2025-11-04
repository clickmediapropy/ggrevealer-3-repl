@echo off
chcp 65001 >nul
cls

:: ============================================
::   _____ _____  ____                      _
::  / ____|  __ \|  _ \                    | |
:: | |  __| |  | | |_) | _____   _____  __ _| | ___ _ __
:: | | |_ | |  | |  _ < / _ \ \ / / _ \/ _` | |/ _ \ '__|
:: | |__| | |__| | |_) |  __/\ V /  __/ (_| | |  __/ |
::  \_____|_____/|____/ \___| \_/ \___|\__,_|_|\___|_|
::
::              INSTALADOR AUTOMATICO
:: ============================================
echo.
color 0A

:: Verificar Python
echo [*] Verificando Python...
python --version >nul 2>&1
if errorlevel 1 (
    color 0C
    echo.
    echo [ERROR] Python no esta instalado en este sistema.
    echo.
    echo Por favor, instala Python 3.11 o superior desde:
    echo https://www.python.org/downloads/
    echo.
    echo Asegurate de marcar la opcion "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [OK] %PYTHON_VERSION% encontrado
echo.

:: Paso 1/3: Crear entorno virtual
echo [Paso 1/3] Creando entorno virtual...
if exist "venv\" (
    echo [OK] Entorno virtual ya existe, usando el existente
) else (
    python -m venv venv
    if errorlevel 1 (
        color 0C
        echo.
        echo [ERROR] No se pudo crear el entorno virtual.
        echo.
        echo Intenta ejecutar manualmente:
        echo   python -m venv venv
        echo.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado exitosamente
)
echo.

:: Paso 2/3: Activar entorno virtual
echo [Paso 2/3] Activando entorno virtual...
call venv\Scripts\activate.bat
if errorlevel 1 (
    color 0C
    echo.
    echo [ERROR] No se pudo activar el entorno virtual.
    echo.
    echo Intenta ejecutar manualmente:
    echo   venv\Scripts\activate.bat
    echo.
    pause
    exit /b 1
)
echo [OK] Entorno virtual activado
echo.

:: Paso 3/3: Instalar dependencias
echo [Paso 3/3] Instalando dependencias...
echo Este proceso puede tomar varios minutos...
echo.
pip install -r requirements.txt
if errorlevel 1 (
    color 0C
    echo.
    echo [ERROR] Fallo la instalacion de dependencias.
    echo.
    echo Intenta ejecutar manualmente:
    echo   venv\Scripts\activate.bat
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo.
echo [OK] Dependencias instaladas exitosamente
echo.

:: Mensaje de éxito
color 0A
echo ============================================
echo [OK] Instalacion completada con exito!
echo ============================================
echo.
echo Proximos pasos:
echo.
echo 1. Crea el archivo .env con tu clave API de Gemini:
echo    GEMINI_API_KEY=tu_clave_aqui
echo.
echo 2. Ejecuta el servidor con:
echo    ejecutar.bat
echo.
echo 3. Abre tu navegador en:
echo    http://localhost:8000
echo.
echo ============================================
echo.
pause
