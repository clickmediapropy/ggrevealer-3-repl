# Solución para Layout Roto en Replit

## Problema
El layout no funciona en Replit después del deployment, pero funciona localmente.

## Posibles Causas y Soluciones

### 1. **Archivos Estáticos No Incluidos en Deployment**

**Diagnóstico**: Verifica en la consola del navegador (F12) si hay errores 404 para archivos CSS/JS.

**Solución A - Verificar que carpetas existen**:
El archivo `.replit` debería incluir todos los archivos necesarios. Verifica que las carpetas `static/`, `templates/` están en el repo.

```bash
# En la shell de Replit, ejecuta:
ls -la static/css/
ls -la static/js/
ls -la static/images/
```

Si falta alguna carpeta, hay que crearla manualmente.

**Solución B - Forzar inclusión en .gitignore**:
Asegúrate de que `.gitignore` NO excluya estas carpetas:

```bash
# Verifica .gitignore, NO debería tener:
# static/
# templates/
```

### 2. **Orden de Ejecución de StaticFiles Mount**

**Problema**: El mount de `/static` puede fallar si la carpeta no existe al momento de inicializar FastAPI.

**Solución - Modificar main.py** (líneas 76-86):

```python
# ANTES del app.mount(), asegurarse que directorios existen
import os
from pathlib import Path

# Crear directorios ANTES de montar
Path("static").mkdir(exist_ok=True)
Path("static/css").mkdir(exist_ok=True)
Path("static/js").mkdir(exist_ok=True)
Path("static/images").mkdir(exist_ok=True)
Path("templates").mkdir(exist_ok=True)

# Verificar que archivos existen
if not os.path.exists("static/css/styles.css"):
    print("⚠️  WARNING: static/css/styles.css not found!")
if not os.path.exists("static/js/app.js"):
    print("⚠️  WARNING: static/js/app.js not found!")

# Ahora montar
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")
```

### 3. **CORS Headers o Content-Type Incorrecto**

**Problema**: Replit puede no servir archivos CSS/JS con los headers correctos.

**Solución - Agregar configuración de MIME types en StaticFiles**:

```python
from starlette.staticfiles import StaticFiles

# Mount con configuración explícita
app.mount(
    "/static",
    StaticFiles(directory="static", html=True),
    name="static"
)
```

### 4. **Rutas Absolutas vs Relativas**

**Problema**: En deployment, las rutas absolutas pueden resolver diferente.

**Solución RÁPIDA - Cambiar a rutas relativas en templates/index.html**:

```html
<!-- CAMBIAR DE: -->
<link href="/static/css/styles.css" rel="stylesheet">
<script src="/static/js/app.js"></script>

<!-- A: -->
<link href="{{ url_for('static', path='css/styles.css') }}" rel="stylesheet">
<script src="{{ url_for('static', path='js/app.js') }}"></script>
```

### 5. **Bootstrap CDN Bloqueado**

**Problema**: Replit puede bloquear recursos externos.

**Diagnóstico**: Verifica en consola del navegador (F12 → Network) si Bootstrap se carga.

**Solución**: Descargar Bootstrap localmente:

```bash
# Descargar Bootstrap
mkdir -p static/vendor/bootstrap/css
mkdir -p static/vendor/bootstrap/js
curl -o static/vendor/bootstrap/css/bootstrap.min.css https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css
curl -o static/vendor/bootstrap/js/bootstrap.bundle.min.js https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js
```

Luego cambiar en `templates/index.html`:
```html
<link href="/static/vendor/bootstrap/css/bootstrap.min.css" rel="stylesheet">
<script src="/static/vendor/bootstrap/js/bootstrap.bundle.min.js"></script>
```

### 6. **Cache del Navegador**

**Solución**: Hard refresh en el navegador de Replit:
- Chrome/Edge: Ctrl + Shift + R (Windows) o Cmd + Shift + R (Mac)
- O abre DevTools (F12) → Network tab → marcar "Disable cache"

### 7. **Puerto o Proxy de Replit**

**Problema**: El webview de Replit puede tener problemas con el proxy interno.

**Solución**: Abrir en una nueva ventana:
- En Replit, click en "Open in new tab" (icono de ventana)
- Esto abre la app en una URL directa sin el iframe de Replit

## Pasos de Debugging Recomendados

### Paso 1: Verificar Logs del Servidor

En la consola de Replit, busca mensajes como:
```
✅ FastAPI app started
INFO: Application startup complete
```

### Paso 2: Probar Endpoint de Static Files

En el navegador, accede directamente a:
```
https://tu-repl-url.replit.dev/static/css/styles.css
```

Si esto devuelve 404, el problema es el mount de static files.

### Paso 3: Console del Navegador

Abre DevTools (F12) y busca:
- **Console tab**: Errores de JavaScript
- **Network tab**: Archivos que fallan en cargar (404, CORS errors)
- **Sources tab**: Verifica que los archivos CSS/JS están disponibles

### Paso 4: Verificar Archivos en Shell de Replit

```bash
# En la Shell de Replit
pwd  # Debería mostrar el directorio del proyecto
ls -la static/
cat static/css/styles.css | head -20  # Ver primeras líneas del CSS
```

## Solución MÁS PROBABLE para Replit

La solución más común es usar `url_for()` de Jinja2 en lugar de rutas hardcodeadas:

1. **Modificar templates/index.html líneas 9, 12-15, y última línea**:

```html
<!-- Línea 9 -->
<link href="{{ url_for('static', path='css/styles.css') }}" rel="stylesheet">

<!-- Líneas 12-15 (favicons) -->
<link rel="icon" type="image/x-icon" href="{{ url_for('static', path='images/favicon.ico') }}">
<link rel="icon" type="image/png" sizes="32x32" href="{{ url_for('static', path='images/favicon-32x32.png') }}">
<link rel="icon" type="image/png" sizes="16x16" href="{{ url_for('static', path='images/favicon-16x16.png') }}">
<link rel="apple-touch-icon" sizes="180x180" href="{{ url_for('static', path='images/apple-touch-icon.png') }}">

<!-- Logo (línea 22) -->
<img src="{{ url_for('static', path='images/logo-icon.png') }}" alt="GGRevealer" class="logo-icon">

<!-- Al final del archivo -->
<script src="{{ url_for('static', path='js/app.js') }}"></script>
```

## Test Rápido

Si quieres probar rápidamente si el problema es de static files, agrega esto temporalmente en `main.py`:

```python
@app.get("/test-static")
async def test_static():
    """Test endpoint to verify static files"""
    import os
    static_files = {
        "css_exists": os.path.exists("static/css/styles.css"),
        "js_exists": os.path.exists("static/js/app.js"),
        "logo_exists": os.path.exists("static/images/logo-icon.png"),
        "static_dir_exists": os.path.exists("static"),
        "current_dir": os.getcwd(),
        "static_contents": os.listdir("static") if os.path.exists("static") else []
    }
    return static_files
```

Luego accede a `https://tu-repl.replit.dev/test-static` y verifica que todos sean `true`.

## Contacto con Replit Support

Si ninguna solución funciona, proporciona a Replit Support:

1. URL del Repl
2. Screenshot de DevTools (F12) mostrando errores
3. Output de `/test-static` endpoint
4. Logs completos del servidor desde Replit console

## Solución Definitiva (Aplicar en orden)

1. ✅ Modificar templates/index.html para usar `url_for()`
2. ✅ Agregar logs en main.py para verificar archivos
3. ✅ Probar endpoint `/test-static`
4. ✅ Hard refresh del navegador
5. ✅ Abrir en nueva pestaña (fuera del iframe de Replit)
