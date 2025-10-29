# Plan: Forzar API Key de Usuario (Implementación Futura)

## Objetivo
Hacer que todos los usuarios DEBAN ingresar su propia API key de Google Gemini para usar la aplicación. Sin API key válida, no se permite procesamiento.

## Cambios Necesarios

### 1. Frontend (templates/index.html + static/js/app.js)
- **Modal no se puede cerrar** sin una API key válida
- **Remover botón "Cerrar"** del modal de API key
- **Deshabilitar botón "Procesar"** si no hay API key configurada
- **Mostrar mensaje prominente** en el sidebar: "⚠️ Debes configurar tu API key para usar esta aplicación"
- **Auto-abrir modal** en cada carga si no hay API key (no se puede omitir)

### 2. Backend (main.py)
- **Remover fallback** a `os.getenv('GEMINI_API_KEY')` en `get_api_key_from_request()`
- **Validar que header X-Gemini-API-Key existe** en endpoint `/api/process/{job_id}`
- **Retornar error 403** si no hay API key de usuario:
  ```python
  if not user_api_key:
      raise HTTPException(
          status_code=403,
          detail="Debes configurar tu propia API key de Google Gemini para usar esta aplicación"
      )
  ```

### 3. Backend (run_processing_pipeline)
- **Eliminar línea de fallback** que usa API key de environment
- **Lanzar excepción** si `api_key` es None o vacío

## Flujo Resultante
1. Usuario abre app → Modal de API key aparece (obligatorio)
2. Usuario intenta cerrar modal → No se puede
3. Usuario intenta procesar sin API key → Error 403 con mensaje claro
4. Usuario ingresa API key válida → Puede usar la app normalmente
5. Usuario ingresa API key inválida → Modal muestra error, debe reintentar

## Archivos a Modificar
- `templates/index.html` (remover botón cerrar del modal)
- `static/js/app.js` (bloquear procesamiento sin API key)
- `static/css/styles.css` (estilos para mensajes de advertencia)
- `main.py` (eliminar fallbacks, agregar validaciones)

## Tiempo Estimado
1-2 horas de implementación y testing.

## Consideraciones
- **Comunicar a usuarios existentes** con anticipación (email/notificación)
- **Proporcionar instrucciones claras** de cómo obtener API key de Google Gemini
- **Agregar enlace directo** a https://makersuite.google.com/app/apikey en el modal
- **Mensaje amigable** explicando que esto reduce costos para ambos (ellos y tú)

---

**Fecha de creación:** Septiembre 2025
**Estado:** No implementado (plan futuro)
