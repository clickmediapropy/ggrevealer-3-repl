╔═══════════════════════════════════════════════════════════════════╗
║                      GGREVEALER v1.0.0                          ║
║              Instrucciones Rapidas de Instalacion               ║
╚═══════════════════════════════════════════════════════════════════╝

IMPORTANTE: Este archivo contiene instrucciones rapidas. Para la guia
completa con capturas de pantalla y detalles paso a paso, abre el archivo:
GUIA_INSTALACION_Y_USO.html


═══════════════════════════════════════════════════════════════════
  REQUISITOS PREVIOS
═══════════════════════════════════════════════════════════════════

Antes de instalar GGRevealer, necesitas:

1. Python 3.11 o superior instalado
   - Verifica con: python --version
   - Si no esta instalado, descarga de: https://www.python.org/downloads/
   - IMPORTANTE: Durante instalacion, marca "Add Python to PATH"

2. Google Gemini API Key
   - Obtener en: https://aistudio.google.com/app/apikey
   - Necesitas cuenta de Google
   - API Key gratuito: 15 solicitudes/minuto
   - Guardar el API Key en lugar seguro


═══════════════════════════════════════════════════════════════════
  INSTALACION (6 PASOS)
═══════════════════════════════════════════════════════════════════

╔═══════════════════════════════════════════════════════════════════╗
║  PASO 1: Descomprimir el archivo ZIP                             ║
╚═══════════════════════════════════════════════════════════════════╝

1. Extrae ggrevealer-windows.zip a una carpeta (ejemplo: C:\GGRevealer)
2. NO uses carpetas con espacios o caracteres especiales
3. Evita rutas muy largas (max 200 caracteres)


╔═══════════════════════════════════════════════════════════════════╗
║  PASO 2: Abrir Terminal en la carpeta                            ║
╚═══════════════════════════════════════════════════════════════════╝

Opcion A - Metodo rapido:
   1. Abre la carpeta en Explorador de Windows
   2. Escribe "cmd" en la barra de direccion
   3. Presiona Enter

Opcion B - Metodo manual:
   1. Presiona tecla Windows + R
   2. Escribe "cmd" y presiona Enter
   3. Navega: cd C:\GGRevealer


╔═══════════════════════════════════════════════════════════════════╗
║  PASO 3: Crear entorno virtual                                   ║
╚═══════════════════════════════════════════════════════════════════╝

Ejecuta en la terminal:

   python -m venv venv

Espera 10-30 segundos mientras se crea el entorno.


╔═══════════════════════════════════════════════════════════════════╗
║  PASO 4: Activar entorno virtual                                 ║
╚═══════════════════════════════════════════════════════════════════╝

Ejecuta:

   venv\Scripts\activate

Deberas ver (venv) al inicio de la linea de comando.


╔═══════════════════════════════════════════════════════════════════╗
║  PASO 5: Instalar dependencias                                   ║
╚═══════════════════════════════════════════════════════════════════╝

Ejecuta:

   pip install -r requirements.txt

Espera 1-3 minutos mientras se instalan las librerias.


╔═══════════════════════════════════════════════════════════════════╗
║  PASO 6: Configurar API Key                                      ║
╚═══════════════════════════════════════════════════════════════════╝

Opcion A - Archivo .env (RECOMENDADO):
   1. Abre el archivo ".env" con Bloc de Notas
   2. Reemplaza "tu_api_key_aqui" con tu API Key real:
      GEMINI_API_KEY=AIzaSyAbCd1234...
   3. Guarda el archivo

Opcion B - Ingresar en la web:
   1. Inicia la aplicacion (ver siguiente seccion)
   2. Ingresa API Key en la interfaz web
   3. NOTA: Deberas reingresarlo cada vez que inicies


═══════════════════════════════════════════════════════════════════
  INICIAR LA APLICACION
═══════════════════════════════════════════════════════════════════

╔═══════════════════════════════════════════════════════════════════╗
║  METODO 1: Script automatico (RECOMENDADO)                       ║
╚═══════════════════════════════════════════════════════════════════╝

Haz doble clic en:

   iniciar_ggrevealer.bat

Se abrira una ventana negra (NO la cierres) y tu navegador.


╔═══════════════════════════════════════════════════════════════════╗
║  METODO 2: Manual                                                 ║
╚═══════════════════════════════════════════════════════════════════╝

1. Abre terminal en la carpeta
2. Activa entorno: venv\Scripts\activate
3. Ejecuta: python main.py
4. Abre navegador: http://localhost:8000


═══════════════════════════════════════════════════════════════════
  DETENER LA APLICACION
═══════════════════════════════════════════════════════════════════

Metodo 1 (Si usaste el .bat):
   - Cierra la ventana negra de comandos

Metodo 2 (Si iniciaste manualmente):
   - En la terminal, presiona: Ctrl + C
   - Espera mensaje de cierre


═══════════════════════════════════════════════════════════════════
  PROBLEMAS COMUNES
═══════════════════════════════════════════════════════════════════

╔═══════════════════════════════════════════════════════════════════╗
║  PROBLEMA 1: "python no se reconoce como comando"                ║
╚═══════════════════════════════════════════════════════════════════╝

CAUSA: Python no esta en PATH del sistema

SOLUCION:
   1. Reinstala Python desde: https://www.python.org/downloads/
   2. MARCA la opcion "Add Python to PATH" al instalar
   3. Reinicia la terminal
   4. Verifica: python --version

ALTERNATIVA:
   - Usa "py" en lugar de "python" en todos los comandos
   - Ejemplo: py -m venv venv


╔═══════════════════════════════════════════════════════════════════╗
║  PROBLEMA 2: Error "cannot activate virtual environment"         ║
╚═══════════════════════════════════════════════════════════════════╝

CAUSA: Politicas de ejecucion de PowerShell (si usas PowerShell)

SOLUCION A (Cambiar a CMD):
   1. Cierra PowerShell
   2. Abre CMD (ver PASO 2 de instalacion)
   3. Reintenta activacion

SOLUCION B (Permitir scripts en PowerShell):
   1. Abre PowerShell como Administrador
   2. Ejecuta: Set-ExecutionPolicy RemoteSigned
   3. Confirma con "Y"
   4. Reintenta activacion


╔═══════════════════════════════════════════════════════════════════╗
║  PROBLEMA 3: "Address already in use" al iniciar                 ║
╚═══════════════════════════════════════════════════════════════════╝

CAUSA: Puerto 8000 ocupado por otra aplicacion

SOLUCION:
   1. Cierra todas las ventanas de terminal abiertas
   2. Abre Administrador de Tareas (Ctrl + Shift + Esc)
   3. Busca procesos "python.exe"
   4. Finaliza todos los procesos python.exe
   5. Reintenta iniciar GGRevealer

ALTERNATIVA:
   - Edita main.py, busca la linea:
     uvicorn.run(app, host="0.0.0.0", port=8000)
   - Cambia 8000 por otro puerto (ejemplo: 8001)
   - Guarda y reinicia


╔═══════════════════════════════════════════════════════════════════╗
║  PROBLEMA 4: "GEMINI_API_KEY not found" o errores de API         ║
╚═══════════════════════════════════════════════════════════════════╝

CAUSA: API Key no configurado o invalido

SOLUCION:
   1. Verifica que el archivo .env existe en la carpeta raiz
   2. Abre .env con Bloc de Notas
   3. Verifica formato exacto:
      GEMINI_API_KEY=AIzaSy...tu_clave_completa...
   4. SIN comillas, SIN espacios antes/despues del =
   5. Guarda el archivo
   6. Reinicia la aplicacion

VERIFICAR API KEY:
   - Debe comenzar con: AIzaSy
   - Longitud: ~39 caracteres
   - Obtener nueva: https://aistudio.google.com/app/apikey


╔═══════════════════════════════════════════════════════════════════╗
║  PROBLEMA 5: Navegador no abre automaticamente                   ║
╚═══════════════════════════════════════════════════════════════════╝

SOLUCION:
   1. Verifica en la terminal que aparezca:
      "Application startup complete"
   2. Abre manualmente tu navegador
   3. Ve a: http://localhost:8000
   4. Si no carga, verifica que no haya errores en terminal


╔═══════════════════════════════════════════════════════════════════╗
║  PROBLEMA 6: Error "pip is not recognized"                       ║
╚═══════════════════════════════════════════════════════════════════╝

SOLUCION:
   1. Verifica que activaste el entorno virtual (debe mostrar (venv))
   2. Si no esta activado:
      venv\Scripts\activate
   3. Reintenta: pip install -r requirements.txt

ALTERNATIVA:
   - Usa: python -m pip install -r requirements.txt


═══════════════════════════════════════════════════════════════════
  USO BASICO
═══════════════════════════════════════════════════════════════════

1. Inicia la aplicacion
2. En el navegador (http://localhost:8000):
   - Sube archivos .txt (hand histories de GGPoker)
   - Sube capturas .png/.jpg (screenshots de PokerCraft)
3. Haz clic en "Procesar"
4. Espera a que termine (barra de progreso)
5. Descarga archivos procesados:
   - resolved_hands.zip (manos completamente de-anonimizadas)
   - fallidos.zip (manos con IDs pendientes)

Para detalles de uso avanzado, consulta GUIA_INSTALACION_Y_USO.html


═══════════════════════════════════════════════════════════════════
  INFORMACION TECNICA
═══════════════════════════════════════════════════════════════════

Version:              1.0.0
Puerto por defecto:   8000
Tecnologia:           Python 3.11+ / FastAPI / Gemini 2.5 Flash
Base de datos:        SQLite (ggrevealer.db)
Archivos generados:   storage/ (uploads, outputs, debug)

Estructura de carpetas:
   ggrevealer/
   ├── main.py                  (aplicacion principal)
   ├── requirements.txt         (dependencias)
   ├── .env                     (configuracion API Key)
   ├── iniciar_ggrevealer.bat   (script de inicio)
   ├── venv/                    (entorno virtual)
   ├── storage/                 (archivos procesados)
   ├── static/                  (interfaz web)
   └── templates/               (HTML)

Uso de API:
   - Tier gratuito: 15 solicitudes/minuto
   - 1 screenshot = 1 solicitud OCR
   - Procesar 30 screenshots = ~2 minutos

Logs de depuracion:
   - Ubicacion: storage/debug/
   - Nombre: debug_job_{id}_{timestamp}.json
   - Contiene: estado completo del job + logs


═══════════════════════════════════════════════════════════════════
  SOPORTE Y DOCUMENTACION
═══════════════════════════════════════════════════════════════════

Guia completa HTML:   GUIA_INSTALACION_Y_USO.html
                      (abre con navegador para ver capturas de pantalla)

Archivos clave:
   - CLAUDE.md          (documentacion tecnica para desarrolladores)
   - README.txt         (este archivo)
   - requirements.txt   (lista de dependencias)

Para problemas no listados:
   1. Revisa storage/debug/ para logs de errores
   2. Verifica que todos los pasos de instalacion se completaron
   3. Asegurate de tener conexion a internet (para API Gemini)


═══════════════════════════════════════════════════════════════════
  NOTAS IMPORTANTES
═══════════════════════════════════════════════════════════════════

- NO compartas tu GEMINI_API_KEY con nadie
- NO subas el archivo .env a repositorios publicos
- Mantén actualizado Python a la version mas reciente 3.11+
- Los archivos procesados se guardan en: storage/outputs/{job_id}/
- La base de datos ggrevealer.db guarda historial de trabajos


═══════════════════════════════════════════════════════════════════

             Gracias por usar GGRevealer v1.0.0
                  Desarrollado para GGPoker
             De-anonimiza hand histories facilmente

═══════════════════════════════════════════════════════════════════
