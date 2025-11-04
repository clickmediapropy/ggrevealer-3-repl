# GGRevealer - Guía de Instalación para Windows

## ¿Qué es GGRevealer?

GGRevealer es una aplicación web que convierte archivos de historial de manos de GGPoker (con jugadores anónimos) en archivos compatibles con PokerTracker usando screenshots de PokerCraft y OCR con Google Gemini Vision API.

**Resultado**: Archivos de historial con nombres reales de jugadores en lugar de códigos hexadecimales anónimos.

---

## Requisitos Previos

### 1. Python 3.11 o superior

**Verificar si ya tienes Python instalado:**
```cmd
python --version
```

**Si no tienes Python o tienes una versión antigua:**
1. Descarga Python desde: https://www.python.org/downloads/
2. **IMPORTANTE**: Durante la instalación, marca la opción "Add Python to PATH"
3. Reinicia el símbolo del sistema después de instalar

### 2. Google Gemini API Key

Necesitas una API key de Google para usar el servicio de OCR:

1. Ve a: https://aistudio.google.com/app/apikey
2. Inicia sesión con tu cuenta de Google
3. Haz clic en "Create API Key"
4. Copia la clave generada (la necesitarás más adelante)

**Nota**: El tier gratuito de Gemini incluye 15 requests por minuto, suficiente para procesar ~150 manos por hora.

---

## Instalación Paso a Paso

### Paso 1: Extraer los archivos

1. Extrae el archivo `GGRevealer.rar` en una carpeta de tu elección
2. Ejemplo: `C:\Users\TuUsuario\GGRevealer\`

### Paso 2: Configurar la API Key

1. Abre la carpeta donde extrajiste GGRevealer
2. Busca el archivo `.env.example`
3. Haz una copia del archivo y renómbrala a `.env` (sin el .example)
4. Abre el archivo `.env` con el Bloc de notas
5. Reemplaza `your_api_key_here` con tu API key de Gemini:
   ```
   GEMINI_API_KEY=TuClaveAPIAquí
   ```
6. Guarda y cierra el archivo

### Paso 3: Instalar dependencias

1. Abre el **Símbolo del sistema** (cmd) como Administrador:
   - Presiona `Windows + R`
   - Escribe `cmd`
   - Presiona `Ctrl + Shift + Enter` (para abrirlo como administrador)

2. Navega a la carpeta de GGRevealer:
   ```cmd
   cd C:\Users\TuUsuario\GGRevealer
   ```

3. Instala las dependencias de Python:
   ```cmd
   pip install -r requirements.txt
   ```

   **Si tienes problemas con pip**, intenta:
   ```cmd
   python -m pip install -r requirements.txt
   ```

### Paso 4: Iniciar la aplicación

**Opción A - Usando el script start.bat (Recomendado)**
1. Haz doble clic en el archivo `start.bat`
2. Se abrirá una ventana con el servidor ejecutándose

**Opción B - Desde el símbolo del sistema**
```cmd
python main.py
```

### Paso 5: Acceder a la aplicación

1. Abre tu navegador web (Chrome, Firefox, Edge, etc.)
2. Ve a: `http://localhost:8000`
3. Deberías ver la interfaz de GGRevealer

---

## Cómo Usar GGRevealer

### Preparación de Archivos

**Archivos TXT (Historiales de manos):**
- Exporta tus historiales de manos desde GGPoker
- Formato: archivos `.txt` con manos anónimas

**Screenshots (Capturas de PokerCraft):**
- Toma screenshots de tus mesas en PokerCraft
- Formato: `.png` o `.jpg`
- **Importante**: Los screenshots deben mostrar claramente los nombres de jugadores

### Proceso de Upload

1. **Selecciona API Tier**:
   - **Free**: 15 requests/minuto (recomendado para empezar)
   - **Paid**: Si tienes una cuenta de pago de Google AI Studio

2. **Sube archivos**:
   - Arrastra o selecciona tus archivos `.txt` de historiales
   - Arrastra o selecciona tus screenshots de PokerCraft
   - El sistema soporta uploads por lotes para archivos grandes

3. **Inicia el procesamiento**:
   - Haz clic en "Process Files"
   - El sistema automáticamente:
     - Extrae IDs de manos de los screenshots (OCR Fase 1)
     - Empareja screenshots con manos
     - Extrae nombres de jugadores (OCR Fase 2)
     - Genera archivos de salida

4. **Descarga resultados**:
   - **resolved_hands.zip**: Manos 100% de-anonimizadas (listas para PT4)
   - **fallidos.zip**: Manos con algunos IDs sin emparejar (necesitan más screenshots)

### Estructura de Resultados

Los archivos procesados se guardan en:
```
storage/
├── uploads/{job_id}/txt/           # Tus archivos originales
├── uploads/{job_id}/screenshots/   # Tus screenshots
└── outputs/{job_id}/               # Archivos procesados
    ├── {table}_resolved.txt        # 100% de-anonimizado
    ├── {table}_fallado.txt         # Parcialmente resuelto
    ├── resolved_hands.zip          # Listos para importar a PT4
    └── fallidos.zip                # Necesitan más screenshots
```

---

## Importar a PokerTracker 4

1. Descarga el archivo `resolved_hands.zip`
2. Extrae los archivos `.txt`
3. En PokerTracker 4:
   - Ve a **"Get Hands from Disk"**
   - Selecciona la carpeta con los archivos extraídos
   - Importa normalmente

**Validaciones automáticas**: GGRevealer aplica 10 reglas de validación que replican las de PT4 para garantizar importación exitosa.

---

## Solución de Problemas

### "Python no se reconoce como un comando interno..."
- Python no está en el PATH de Windows
- Reinstala Python y marca "Add Python to PATH"
- O busca la ruta de instalación (ej: `C:\Python311\python.exe`) y úsala directamente

### "pip no está instalado"
```cmd
python -m ensurepip --upgrade
```

### "Error de permisos al instalar paquetes"
- Ejecuta el símbolo del sistema como Administrador
- O usa: `pip install --user -r requirements.txt`

### El servidor no inicia
- Verifica que el puerto 8000 no esté en uso
- Cierra otras aplicaciones que puedan estar usando ese puerto
- Intenta con otro puerto: `python main.py --port 8001`

### "Invalid API Key" al procesar
- Verifica que copiaste la API key correctamente en el archivo `.env`
- Asegúrate de que el archivo se llama `.env` y no `.env.txt`
- Verifica que la API key es válida en: https://aistudio.google.com/app/apikey

### OCR no detecta nombres correctamente
- Asegúrate de que los screenshots sean claros y legibles
- Los screenshots deben mostrar la mesa completa con nombres visibles
- Toma screenshots en resolución alta (no reducida)

### Archivos en "fallidos.zip"
- Esto es normal si no tienes screenshots para todas las manos
- Toma más screenshots de PokerCraft y procesa de nuevo
- Los archivos "fallidos" contienen las manos que sí se resolvieron

---

## Configuración Avanzada

### Cambiar el puerto del servidor

Edita `main.py` cerca de la línea 3600:
```python
port = int(os.environ.get("PORT", 8000))  # Cambia 8000 por tu puerto preferido
```

### Ajustar límites de archivos

En `main.py`, líneas ~60-80:
```python
# Tier gratuito
MAX_TXT_FILES_FREE = 50
MAX_SCREENSHOTS_FREE = 200

# Tier de pago
MAX_TXT_FILES_PAID = 200
MAX_SCREENSHOTS_PAID = 1000
```

### Logs y debugging

Los logs se guardan en:
- Base de datos SQLite: `ggrevealer.db`
- Debug automático: `storage/debug/debug_job_{id}_{timestamp}.json`

---

## Detener la Aplicación

Para cerrar el servidor:
1. Ve a la ventana del símbolo del sistema donde está ejecutándose
2. Presiona `Ctrl + C`
3. Confirma con `S` o `Y` si te lo pide

---

## Soporte y Contacto

Si encuentras errores o tienes preguntas:
- Revisa el archivo `CLAUDE.md` para documentación técnica detallada
- Contacta al desarrollador que te compartió esta aplicación

---

## Tecnologías Utilizadas

- **Backend**: Python 3.11+ con FastAPI
- **Base de datos**: SQLite (ligera, sin servidor)
- **OCR**: Google Gemini 2.5 Flash Vision
- **Frontend**: HTML + JavaScript (Vanilla) + Bootstrap 5

---

## Notas Finales

- **Privacidad**: Todos los archivos se procesan localmente. Solo los screenshots se envían a Google Gemini para OCR.
- **Costo**: El tier gratuito de Gemini es suficiente para uso personal (~150 manos/hora).
- **Precisión**: ~96% de matching exitoso con screenshots de buena calidad.
- **Compatibilidad**: Archivos de salida 100% compatibles con PokerTracker 4.

---

**¡Buena suerte en las mesas! 🃏**
