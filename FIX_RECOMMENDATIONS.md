# Plan de Correcciones - GGRevealer Audit Findings

**Fecha**: Noviembre 2025  
**Auditor**: Claude Code Audit Engine  
**Prioridad**: 2 CRÍTICOS + 9 MEDIOS  
**Estimado**: 4-6 horas de implementación

---

## PRIORITY 1: IMPLEMENTAR INMEDIATAMENTE

### Fix #1: Unificar Asyncio Event Loops

**Problema**: `asyncio.run()` llamado dos veces

**Archivo**: `main.py:1595, 1698`

**Solución**:

```python
# BEFORE (main.py:1567-1706)
asyncio.run(process_all_ocr1())      # Crea event loop #1
# ... código intermedio ...
asyncio.run(process_all_ocr2())      # Crea event loop #2

# AFTER: Unificar en una sola función async
async def run_all_ocr_phases():
    """Run OCR1 and OCR2 in unified event loop"""
    
    # Phase 1: OCR1
    logger.info(f"🔍 OCR1: {len(screenshot_files)} screenshots")
    semaphore = asyncio.Semaphore(semaphore_limit)
    tasks = [process_ocr1(sf) for sf in screenshot_files]
    await asyncio.gather(*tasks)
    
    # Phase 2: OCR2 (reutiliza el MISMO event loop)
    logger.info(f"🔍 OCR2: {len(matched_screenshots)} matched screenshots")
    semaphore = asyncio.Semaphore(semaphore_limit)
    tasks = [process_ocr2(screenshot_file, screenshot_filename) 
             for screenshot_file in screenshot_files
             if screenshot_file['filename'] in matched_screenshots]
    await asyncio.gather(*tasks)

# Reemplaza ambos asyncio.run() con uno solo
asyncio.run(run_all_ocr_phases())
```

**Testing**:
- [ ] Verificar que OCR1 y OCR2 se ejecutan secuencialmente
- [ ] Confirmar que semaphore está disponible en ambas fases
- [ ] No debe haber cambios en resultados finales

---

### Fix #2: API Key Validation Explícita

**Problema**: Fallback silencioso a DUMMY_API_KEY

**Archivos**: `main.py:1544-1545, ocr.py:31-32`

**Solución**:

```python
# main.py:1543-1548 (MODIFICAR)
# BEFORE
if not api_key or not api_key.strip():
    api_key = os.getenv('GEMINI_API_KEY', 'DUMMY_API_KEY_FOR_TESTING')

logger.info(f"Using API key: {'User-provided' if api_key != os.getenv('GEMINI_API_KEY') else 'Environment'}")

# AFTER
if not api_key or not api_key.strip():
    api_key = os.getenv('GEMINI_API_KEY')

if not api_key or api_key == 'your_gemini_api_key_here':
    logger.critical("❌ GEMINI_API_KEY not configured!")
    raise ValueError(
        "GEMINI_API_KEY is required. Please:\n"
        "1. Set in .env file: GEMINI_API_KEY=your_key\n"
        "2. Or pass in request header: X-Gemini-API-Key\n"
        "3. Get key from: https://makersuite.google.com/app/apikey"
    )

logger.info(f"Using Gemini API key (first 10 chars): {api_key[:10]}...")

# ocr.py:29-32 (MODIFICAR)
# BEFORE
if not api_key or api_key == "DUMMY_API_KEY_FOR_TESTING":
    return (False, None, "Gemini API key not configured")

# AFTER
if not api_key or api_key == "DUMMY_API_KEY_FOR_TESTING":
    raise ValueError("Gemini API key not configured - cannot proceed with OCR")
```

**Testing**:
- [ ] Job debe fallar con error claro si no hay API key
- [ ] Job debe proceder si API key es válido
- [ ] Error message debe incluir instrucciones de configuración

---

## PRIORITY 2: NEXT SPRINT

### Fix #3: Table Name Consistency

**Problema**: `unknown_table_1` vs `Unknown` mismatch

**Archivos**: `main.py:2326-2352, 2384-2389`

**Solución**:

```python
# OPCIÓN A: Mantener unknown_table_N en todo lado
# main.py:_group_hands_by_table NO cambiar generación
# main.py:_build_table_mapping (MODIFICAR línea 2388)

# BEFORE
if _normalize_table_name(hand_table_name) == _normalize_table_name(table_name):

# AFTER: Buscar por unknown_table pattern exacto
import re
def _table_matches(hand_table, group_table):
    """Check if two table names refer to same table"""
    # Exact match
    if hand_table == group_table:
        return True
    
    # Both are unknown variants
    if hand_table.startswith('unknown_table_') and group_table.startswith('unknown_table_'):
        return False  # Different unknown tables are different
    
    # Normalized match
    return _normalize_table_name(hand_table) == _normalize_table_name(group_table)

# Uso:
for screenshot_filename, matched_hand in matched_screenshots.items():
    hand_table_name = extract_table_name(matched_hand.raw_text)
    if _table_matches(hand_table_name, table_name):
        screenshots_for_table.append((screenshot_filename, matched_hand))
```

**Testing**:
- [ ] Unknown table 1 screenshots mapean a unknown_table_1 hands
- [ ] Unknown table 2 screenshots mapean a unknown_table_2 hands
- [ ] Named tables (e.g., 'Cartney') siguen funcionando

---

### Fix #4: ZIP Integrity Validation

**Problema**: No se valida integridad de ZIP antes de download

**Archivo**: `main.py:359-390`

**Solución**:

```python
# main.py:359-390 (MODIFICAR)
@app.get("/api/download/{job_id}")
async def download_output(job_id: int):
    """Download the processed ZIP file for successful files"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job is not completed yet")
    
    result = get_result(job_id)
    if not result or not result.get('output_txt_path'):
        raise HTTPException(status_code=404, detail="Output file not found")
    
    output_path = Path(result['output_txt_path'])
    
    # Validar integridad si es ZIP
    if output_path.suffix == '.zip' and output_path.exists():
        try:
            with zipfile.ZipFile(output_path, 'r') as zipf:
                bad_file = zipf.testzip()
                if bad_file:
                    raise HTTPException(
                        status_code=500,
                        detail=f"ZIP file corrupted: cannot read {bad_file}"
                    )
        except zipfile.BadZipFile:
            raise HTTPException(
                status_code=500,
                detail="ZIP file is corrupted and cannot be extracted"
            )
        
        return FileResponse(
            path=output_path,
            filename=f"resolved_hands_{job_id}.zip",
            media_type="application/zip"
        )
```

**Testing**:
- [ ] Descargar ZIP válido funciona
- [ ] ZIP corrupto retorna 500 error
- [ ] Error message es claro al usuario

---

### Fix #5: OCR2 Output Schema Validation

**Problema**: ocr_data sin validación de estructura

**Archivo**: `main.py:2404-2467`

**Solución**:

```python
# main.py:2404-2467 (MODIFICAR _build_table_mapping)
from pydantic import ValidationError, BaseModel

# Primero validar ocr_data
try:
    # Crear ScreenshotAnalysis para validar schema
    if isinstance(ocr_data, str):
        import json
        ocr_data = json.loads(ocr_data)
    
    # Validar campos requeridos
    required_fields = ['players', 'stacks', 'roles']
    for field in required_fields:
        if field not in ocr_data:
            raise ValueError(f"Missing required field: {field}")
    
    if not isinstance(ocr_data.get('players'), list):
        raise ValueError("'players' must be a list")
    if not isinstance(ocr_data.get('stacks'), list):
        raise ValueError("'stacks' must be a list")
    if not isinstance(ocr_data.get('roles'), dict):
        raise ValueError("'roles' must be a dict")
    
except (json.JSONDecodeError, ValueError, KeyError) as e:
    logger.error(f"Invalid OCR2 format for {screenshot_filename}: {str(e)}",
                screenshot=screenshot_filename,
                error=str(e))
    continue  # Skip this screenshot

# Ahora proceder con ocr_data validado
players_list = ocr_data['players']
stacks_list = ocr_data.get('stacks', [])
positions_list = ocr_data.get('positions', [])

# ... resto del código
```

**Testing**:
- [ ] OCR2 válido se procesa correctamente
- [ ] OCR2 con formato inválido se salta con warning
- [ ] Job no crashea por OCR2 malformado

---

### Fix #6: Dealer Player Explicit Logging

**Problema**: dealer_player puede ser None silenciosamente

**Archivos**: `main.py:2426-2447`

**Solución**:

```python
# main.py:2425-2447 (MODIFICAR _build_table_mapping)

# Calculate SB/BB from dealer position (NEW LOGIC)
dealer_player = ocr_data.get('roles', {}).get('dealer')

if not dealer_player:
    logger.warning(
        f"⚠️  No dealer detected for screenshot {screenshot_filename} - role-based mapping may be incomplete",
        screenshot=screenshot_filename,
        table=table_name
    )
    # Continue pero sin calcular SB/BB
    small_blind_player = None
    big_blind_player = None
else:
    if dealer_player and dealer_player in players_list:
        # Find dealer index in players list
        dealer_index = players_list.index(dealer_player)
        total_players = len(players_list)

        # Calculate SB and BB positions (clockwise from dealer)
        sb_index = (dealer_index + 1) % total_players
        bb_index = (dealer_index + 2) % total_players

        small_blind_player = players_list[sb_index]
        big_blind_player = players_list[bb_index]

        logger.debug(
            f"Calculated blinds from dealer '{dealer_player}'",
            screenshot=screenshot_filename,
            dealer=dealer_player,
            sb=small_blind_player,
            bb=big_blind_player
        )
    else:
        logger.warning(
            f"Dealer '{dealer_player}' not in player list",
            screenshot=screenshot_filename,
            dealer=dealer_player,
            players=players_list
        )
        small_blind_player = None
        big_blind_player = None
```

**Testing**:
- [ ] Si hay dealer, se calculan SB/BB correctamente
- [ ] Si no hay dealer, se loguea warning sin fallar
- [ ] Mapping se completa aunque sea parcial

---

## PRIORITY 3: MEJORAS TÉCNICAS

### Fix #7: Excepciones Específicas

**Archivo**: `ocr.py:89-90, parser.py:106-108, main.py:2029-2034`

```python
# ocr.py (MODIFICAR)
try:
    response = await client.aio.models.generate_content(...)
    hand_id = response.text.strip()
    if not hand_id:
        return (False, None, "Hand ID not found in screenshot")
except asyncio.TimeoutError:
    return (False, None, "OCR timeout - Gemini API did not respond")
except Exception as e:
    logger.error(f"OCR1 error: {type(e).__name__}: {str(e)}")
    return (False, None, f"OCR1 error: {str(e)}")

# parser.py (MODIFICAR)
try:
    # ... parsing logic
except ValueError as e:
    logger.debug(f"Invalid hand format: {str(e)}")
    return None
except Exception as e:
    logger.error(f"Unexpected parser error: {type(e).__name__}: {str(e)}")
    return None
```

**Testing**:
- [ ] Timeout errors se capturan específicamente
- [ ] ValueError se diferencia de otros errores
- [ ] Logging muestra tipo de error

---

### Fix #8: File Upload Rollback

**Archivo**: `main.py:228-250`

```python
# main.py:228-250 (MODIFICAR upload_files)
job_upload_path = UPLOADS_PATH / str(job_id)
job_upload_path.mkdir(exist_ok=True)

txt_path = job_upload_path / "txt"
screenshots_path = job_upload_path / "screenshots"
txt_path.mkdir(exist_ok=True)
screenshots_path.mkdir(exist_ok=True)

try:
    for txt_file in txt_files:
        if not txt_file.filename:
            raise HTTPException(status_code=400, detail="File must have a filename")
        file_path = txt_path / txt_file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(txt_file.file, f)
        add_file(job_id, txt_file.filename, "txt", str(file_path))
    
    for screenshot in screenshots:
        if not screenshot.filename:
            raise HTTPException(status_code=400, detail="File must have a filename")
        file_path = screenshots_path / screenshot.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(screenshot.file, f)
        add_file(job_id, screenshot.filename, "screenshot", str(file_path))

except Exception as e:
    # Cleanup on failure
    logger.error(f"Upload failed, cleaning up: {str(e)}")
    if job_upload_path.exists():
        shutil.rmtree(job_upload_path)
    raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

update_job_file_counts(job_id, len(txt_files), len(screenshots))
```

**Testing**:
- [ ] Archivos se escriben si todo es OK
- [ ] Si falla, directorio se limpia completamente
- [ ] Usuario recibe error claro

---

## Checklist de Implementación

### Phase 1 (Inmediato - 2-3 horas)
- [ ] Fix #1: Asyncio event loops unificados
- [ ] Fix #2: API Key validation explícita
- [ ] Testing y validación
- [ ] Commit y PR

### Phase 2 (Sprint siguiente - 3-4 horas)
- [ ] Fix #3: Table name consistency
- [ ] Fix #4: ZIP integrity validation
- [ ] Fix #5: OCR2 schema validation
- [ ] Fix #6: Dealer player logging
- [ ] Testing y validación
- [ ] Commit y PR

### Phase 3 (Mejoras técnicas - 2-3 horas)
- [ ] Fix #7: Excepciones específicas
- [ ] Fix #8: File upload rollback
- [ ] Code review y refactoring
- [ ] Commit y PR

---

## Verificación Post-Fix

```bash
# Después de cada fix:
1. pytest test_*.py
2. Ejecutar job test completo
3. Validar que métricas no cambian
4. Verificar logs están claros
5. Probar edge cases específicos del fix
```

---

**Estimado Total**: 4-6 horas  
**Impacto**: Sistema pasa de 85% a 95%+ de calidad

