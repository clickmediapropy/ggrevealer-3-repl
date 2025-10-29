# Sesión Q&A - Descubrimientos e Ideas Innovadoras
**Fecha:** 2025-09-29
**Participantes:** Usuario (Nico) + Claude Code
**Objetivo:** Entender el sistema completo y proponer mejoras

---

## Tabla de Contenidos
1. [Visualizaciones Creadas](#visualizaciones-creadas)
2. [Descubrimiento #1: Hero SÍ se reemplaza](#descubrimiento-1-hero-sí-se-reemplaza)
3. [Descubrimiento #2: Código actual tiene mapeo invertido](#descubrimiento-2-código-actual-tiene-mapeo-invertido)
4. [Idea Innovadora: Dos OCRs separados + Dealer Button](#idea-innovadora-dos-ocrs-separados--dealer-button)
5. [Ventajas de la nueva propuesta](#ventajas-de-la-nueva-propuesta)
6. [Plan de Implementación](#plan-de-implementación)

---

## Visualizaciones Creadas

Durante la sesión se crearon tres diagramas complementarios para explicar el flujo completo de GGRevealer:

### Archivo: `docs/diagrams/ggrevealer-workflow-visualizations.md`

**Diagrama 1: Flowchart (Flujo del Pipeline)**
- Muestra el proceso completo desde upload hasta download
- Incluye todas las decisiones (¿Hand ID match? ¿Score >= 70? ¿IDs sin mapear?)
- Con colores por fase: Parser (azul), OCR (amarillo), Matcher (rosa), Writer (verde)

**Diagrama 2: Architecture (Estructura Modular)**
- 6 capas: API/Frontend → Orquestación → Processing → Validation → Storage → External Services
- Muestra cómo fluyen los datos entre módulos
- Identifica claramente qué hace cada archivo (.py)

**Diagrama 3: Sequence (Transformación de Datos)**
- Ejemplo concreto con datos reales del Job #3
- Muestra la transformación paso a paso de datos
- Incluye ejemplo completo de input → output

**Cómo visualizar:**
- VS Code: Extensión "Markdown Preview Mermaid Support"
- GitHub: Renderizado automático
- Online: https://mermaid.live

---

## Descubrimiento #1: Hero SÍ se reemplaza

### Problema encontrado
La documentación (CLAUDE.md) afirmaba incorrectamente:
```
"NUNCA reemplazar Hero" (PokerTracker requirement)
```

### Realidad del código
El sistema **SÍ reemplaza "Hero"** con el nombre real extraído del OCR:

**Evidencia en matcher.py:343:**
```python
"""
Build name mapping from hand to screenshot based on seat positions
Maps anonymized player IDs to real names (including Hero to real hero name)
"""
```

**Evidencia en writer.py:**
- NO existe código que diga `if anon_id == 'Hero': skip`
- Los 14 patrones de regex se aplican a TODOS los IDs en mappings, incluyendo Hero

**Ejemplo práctico:**

Input TXT:
```
Seat 1: e3efcaed ($100 in chips)
Seat 2: 5641b4a0 ($250 in chips)
Seat 3: Hero ($625 in chips)
Dealt to Hero [Kh Kd]
```

OCR extrae:
- Hero real name = "TuichAAreko"

Matcher crea mappings:
```python
{
  "e3efcaed": "Gyodong22",
  "5641b4a0": "v1[nn]1",
  "Hero": "TuichAAreko"  # ← SÍ incluye Hero!
}
```

Output TXT:
```
Seat 1: Gyodong22 ($100 in chips)
Seat 2: v1[nn]1 ($250 in chips)
Seat 3: TuichAAreko ($625 in chips)  # ← Hero fue reemplazado!
Dealt to TuichAAreko [Kh Kd]
```

### Correcciones aplicadas
Se actualizó la documentación en:
- **CLAUDE.md** (5 ubicaciones corregidas)
- **docs/diagrams/ggrevealer-workflow-visualizations.md** (3 ubicaciones)

**Commit:** `72ae5a3` - "docs: Correct Hero replacement documentation"

---

## Descubrimiento #2: Código actual tiene mapeo invertido

### Análisis realizado
Se analizaron 10 screenshots del Job #9 para entender cómo PokerCraft organiza visualmente a los jugadores.

### Caso de prueba: Hand #SG3247423387

**Hand History (TXT):**
```
Poker Hand #SG3247423387
Seat 1: Hero (small blind) - 300 chips
Seat 2: c460cec2 (big blind) - 300 chips
Seat 3: 9018bbd8 (button/dealer) - 300 chips
```

**Screenshot visual:**
- **ABAJO** (centro): Hero = TuichAAreko
- **IZQUIERDA**: DOI002 (sin indicador de dealer)
- **DERECHA**: JuGGernaut! con **círculo "D" amarillo** (dealer button)

### El código actual (matcher.py:388-393)

```python
# Calculate real seat number using counter-clockwise mapping
# Visual position 1 = Hero's seat
# Visual position 2 = Seat before Hero (counter-clockwise)
# Visual position 3 = Seat 2 before Hero (counter-clockwise)
offset = visual_position - 1
real_seat_number = hero_seat_number - offset
```

**Si Hero está en Seat 1:**
- Visual pos 1 (abajo): Seat 1 - 0 = **Seat 1** = Hero ✅
- Visual pos 2 (izquierda): Seat 1 - 1 = Seat 0 → wrap to **Seat 3**
- Visual pos 3 (derecha): Seat 1 - 2 = Seat -1 → wrap to **Seat 2**

**Resultado del código actual:**
- Jugador IZQUIERDA = Seat 3 (button) ❌ **INCORRECTO**
- Jugador DERECHA = Seat 2 (big blind) ❌ **INCORRECTO**

**Lo que REALMENTE muestra el screenshot:**
- Jugador DERECHA tiene el dealer button "D" = **DEBE ser Seat 3** (button) ✅
- Jugador IZQUIERDA NO tiene dealer button = **DEBE ser Seat 2** (big blind) ✅

### Conclusión
**El código actual está invirtiendo las posiciones izquierda/derecha.**

### Confusión sobre clockwise vs counter-clockwise

**Nota importante del usuario:**
> En los juegos de póker, el movimiento de turnos es en sentido **horario (clockwise)**.
> - El botón del dealer se mueve hacia la izquierda (siguiendo las agujas del reloj)
> - Las acciones también se realizan en sentido horario
> - Small blind está a la izquierda del dealer
> - Big blind está a la izquierda del small blind

El código usa terminología "counter-clockwise" pero el cálculo matemático no refleja correctamente cómo PokerCraft organiza visualmente a los jugadores.

---

## Idea Innovadora: Dos OCRs separados + Dealer Button

### Propuesta del usuario (Nico)

En lugar del sistema actual (un OCR complejo + cálculo matemático de posiciones), implementar:

#### Fase 1: Primer OCR (ultra-simple)
**Objetivo:** Extraer SOLO el Hand ID del screenshot

**Prompt simplificado:**
```
"Extrae SOLO el Hand ID visible en la esquina superior derecha del screenshot"
```

**Ventajas:**
- ✅ Mucho más confiable: 99.9%+ accuracy (tarea simple)
- ✅ Más rápido: Menos tokens = respuesta más rápida
- ✅ Match 100% confiable: Si tienes Hand ID → match perfecto

#### Fase 2: Match directo
**Objetivo:** Buscar TXT que contenga ese Hand ID

**Resultado:** Match directo con 100% de confianza (elimina fallback matching problemático)

#### Fase 3: Segundo OCR (enfocado)
**Objetivo:** Extraer nombres + identificar dealer button

**Prompt enfocado:**
```
"Extrae los nombres de los 3 jugadores Y identifica quién tiene el dealer button (círculo amarillo con D)"
```

**Ventajas:**
- ✅ Más confiable que pedir 8+ campos a la vez
- ✅ Dealer button es clave para mapeo directo

#### Fase 4: Mapeo directo por roles
**Objetivo:** Mapear jugadores por su rol (dealer/SB/BB) en vez de posiciones numéricas

**Ejemplo:**

Del screenshot (OCR extrae):
- Jugador DERECHA (JuGGernaut!): tiene círculo "D" amarillo = **DEALER**
- Jugador IZQUIERDA (DOI002): tiene indicador "SB" = **SMALL BLIND**
- Jugador ABAJO (TuichAAreko): tiene indicador "BB" = **BIG BLIND**

Del hand history (parser extrae):
- Seat 3: es el dealer (button)
- Seat 1: es el small blind
- Seat 2: es el big blind

**Mapeo DIRECTO (sin matemáticas):**
```python
# Dealer
screenshot_dealer = "JuGGernaut!"
hand_dealer_seat = 3  # Seat 3: 9018bbd8 (button)
mapping["9018bbd8"] = "JuGGernaut!"

# Small Blind
screenshot_sb = "DOI002"
hand_sb_seat = 1  # Seat 1: Hero (small blind)
mapping["Hero"] = "DOI002"

# Big Blind
screenshot_bb = "TuichAAreko"
hand_bb_seat = 2  # Seat 2: c460cec2 (big blind)
mapping["c460cec2"] = "TuichAAreko"
```

**Sin cálculos counter-clockwise, sin confusión, mapeo 1:1 directo.**

---

## Ventajas de la nueva propuesta

### Comparación: Sistema Actual vs Propuesta

| Aspecto | Sistema Actual | Propuesta Nueva |
|---------|---------------|-----------------|
| **OCR** | Un OCR complejo (8+ campos) | Dos OCRs simples (Hand ID, luego nombres+roles) |
| **Hand ID extraction** | ~85-90% accuracy (se confunde con campos extra) | ~99.9% accuracy (prompt ultra-simple) |
| **Matching** | Hand ID (cuando funciona) + Fallback scoring (70 pts) | Hand ID casi siempre funciona → elimina fallback |
| **Mapeo de posiciones** | Cálculo matemático counter-clockwise (INVERTIDO) | Mapeo directo por roles (dealer/SB/BB) |
| **Confiabilidad** | Propenso a errores (matemática + OCR complejo) | Mucho más confiable (visual directo) |
| **Complejidad** | Alta (cálculos abstractos) | Baja (mapeo 1:1 visual) |
| **Dependencias** | Debe encontrar Hero primero | Identifica todos por rol simultáneamente |
| **Costo API** | 1x llamada Gemini por screenshot | 2x llamadas Gemini por screenshot |
| **Tiempo** | ~2-3s por screenshot | ~4-6s por screenshot (2x OCRs) |

### Pros de la propuesta ✅

1. **Elimina el bug del mapeo invertido** sin necesidad de arreglar matemáticas complejas
2. **Mejora match rate** (menos fallas en extraer Hand ID)
3. **Reduce complejidad** (mapeo visual directo vs cálculo abstracto)
4. **Más fácil de debuggear** (mapeo transparente)
5. **Menos propenso a errores** (no depende de encontrar Hero primero)

### Contras de la propuesta ❌

1. **Doble costo en API calls** (2x llamadas a Gemini por screenshot)
2. **Doble tiempo de procesamiento** (~2x más lento)
3. **Requiere refactorización significativa** del pipeline actual

---

## Verificación del Dealer Button

### Pregunta crítica
**¿PokerCraft reorganiza el dealer button visualmente o no?**

### Análisis de 10 screenshots (Job #9)

**Indicadores visuales encontrados:**
- **"D" en círculo amarillo/blanco** - Dealer button visual
- **"B" en círculo azul** - También indica button
- **"SB"** - Small blind indicator
- **"BB"** - Big blind indicator

**Observaciones clave:**

1. **Hero siempre está ABAJO** (centro) - confirmado en los 10 screenshots
2. **Dealer button aparece en diferentes posiciones visuales:**
   - A veces IZQUIERDA
   - A veces DERECHA
   - A veces en Hero mismo (cuando Hero es button)
3. **PokerCraft reorganiza TODO visualmente** con Hero abajo

### Conclusión sobre dealer button

**SÍ, PokerCraft reorganiza el dealer button visualmente.**

**PERO esto NO es un problema**, porque:
- El OCR VE la configuración visual final
- Puede identificar QUÉ jugador tiene el dealer button visualmente
- Ese jugador corresponde al button real del hand history
- **Mapeo directo**: "Jugador con círculo D" = "Seat que es button en hand history"

**Ejemplo:**
- Screenshot: Jugador DERECHA tiene "D"
- Hand history: Seat 3 es button
- Conclusión: Jugador DERECHA = Seat 3

No importa que PokerCraft haya reorganizado, porque el resultado final es un mapeo 1:1 visual.

---

## Plan de Implementación

### Fase 1: Implementación básica (bajo riesgo, alto valor)

**Objetivo:** Validar que dos OCRs separados mejoran el match rate

**Cambios:**
1. Implementar **primer OCR simplificado** (solo Hand ID)
2. Implementar **segundo OCR** (nombres + posiciones, SIN dealer button por ahora)
3. Mantener el mapeo counter-clockwise actual (pero arreglado)
4. **Medir mejora**: ¿Cuántos más matches conseguimos?

**Archivos a modificar:**
- `ocr.py` - Crear dos funciones: `ocr_hand_id()` y `ocr_player_details()`
- `main.py` - Modificar pipeline para hacer dos llamadas OCR secuenciales
- `matcher.py` - Usar Hand ID del primer OCR para matching

**Métricas a medir:**
- Match rate antes vs después
- OCR Hand ID success rate (esperado: >99%)
- Tiempo de procesamiento (esperado: ~2x más lento)
- Costo API (esperado: 2x costo)

### Fase 2: Mapeo por dealer button (si Fase 1 funciona)

**Objetivo:** Eliminar el cálculo counter-clockwise y usar mapeo directo por roles

**Cambios:**
1. Agregar detección de dealer button al segundo OCR
2. Agregar detección de SB/BB indicators
3. **Verificar** con screenshots reales: ¿Roles siempre visibles?
4. Implementar nueva función `_build_seat_mapping_by_roles()`
5. Reemplazar `_build_seat_mapping()` actual

**Nueva función propuesta:**
```python
def _build_seat_mapping_by_roles(
    hand: ParsedHand,
    screenshot: ScreenshotAnalysis
) -> Dict[str, str]:
    """
    Build name mapping based on player roles (dealer/SB/BB)
    instead of mathematical position calculations.

    Direct 1:1 mapping:
    - Screenshot player with "D" indicator → Hand history button seat
    - Screenshot player with "SB" indicator → Hand history SB seat
    - Screenshot player with "BB" indicator → Hand history BB seat
    """
    mapping = {}

    # Find seats by role in hand history
    dealer_seat = find_seat_by_role(hand, "button")
    sb_seat = find_seat_by_role(hand, "small blind")
    bb_seat = find_seat_by_role(hand, "big blind")

    # Find players by role in screenshot
    dealer_player = find_player_by_indicator(screenshot, "D")
    sb_player = find_player_by_indicator(screenshot, "SB")
    bb_player = find_player_by_indicator(screenshot, "BB")

    # Direct mapping
    if dealer_seat and dealer_player:
        mapping[dealer_seat.player_id] = dealer_player.name
    if sb_seat and sb_player:
        mapping[sb_seat.player_id] = sb_player.name
    if bb_seat and bb_player:
        mapping[bb_seat.player_id] = bb_player.name

    return mapping
```

**Archivos a modificar:**
- `ocr.py` - Agregar extracción de roles/indicators al prompt
- `matcher.py` - Nueva función de mapeo por roles
- `models.py` - Agregar campos a `ScreenshotAnalysis` (dealer_indicator, sb_indicator, bb_indicator)

**Validaciones necesarias:**
1. ¿Todos los screenshots tienen indicators visibles? (SB, BB, D)
2. ¿Qué pasa si un jugador foldea antes del screenshot? (puede no tener indicator)
3. ¿Qué pasa en hands heads-up (2 jugadores)? (solo BB y button, no SB)

### Fase 3: Testing y rollback plan

**Testing:**
1. Usar Job #9 como test case (ya tenemos screenshots y TXTs)
2. Ejecutar pipeline con nueva lógica
3. Comparar resultados:
   - Match rate actual vs nuevo
   - Mappings correctos vs incorrectos
   - Tiempo de procesamiento
   - Costo API

**Rollback plan:**
- Mantener código actual en git branch separado
- Nueva implementación en feature branch
- Si match rate empeora → rollback inmediato
- Si match rate mejora → merge y deploy

**Criterio de éxito:**
- Match rate mejora en al menos 10%
- No aumentan mappings incorrectos
- Tiempo de procesamiento aceptable (<5s por screenshot promedio)

### Fase 4: Cambios de Base de Datos

**Objetivo:** Adaptar el esquema de base de datos para soportar los dos OCRs separados

#### Tabla `screenshot_results` - MODIFICAR ⚠️

**Agregar campos para separar los dos OCRs:**

```sql
-- Campos nuevos a agregar (database.py):
ALTER TABLE screenshot_results ADD COLUMN ocr1_success INTEGER DEFAULT 0;
ALTER TABLE screenshot_results ADD COLUMN ocr1_hand_id TEXT;
ALTER TABLE screenshot_results ADD COLUMN ocr1_error TEXT;
ALTER TABLE screenshot_results ADD COLUMN ocr2_success INTEGER DEFAULT 0;
ALTER TABLE screenshot_results ADD COLUMN ocr2_data TEXT;
ALTER TABLE screenshot_results ADD COLUMN ocr2_error TEXT;
```

**Descripción de campos nuevos:**
- `ocr1_success` - ¿Primer OCR (Hand ID extraction) exitoso? (0/1)
- `ocr1_hand_id` - Hand ID extraído del screenshot (ej: "SG3247423387")
- `ocr1_error` - Mensaje de error si primer OCR falla
- `ocr2_success` - ¿Segundo OCR (player details) exitoso? (0/1)
- `ocr2_data` - JSON con nombres, roles, stacks extraídos
- `ocr2_error` - Mensaje de error si segundo OCR falla

**Campos deprecados (mantener por compatibilidad):**
- `ocr_success` → Reemplazado por `ocr1_success` + `ocr2_success`
- `ocr_error` → Reemplazado por `ocr1_error` + `ocr2_error`
- `ocr_data` → Reemplazado por `ocr2_data`

**Nuevo schema de `ocr2_data` (JSON) para Fase 2:**
```json
{
  "players": ["TuichAAreko", "DOI002", "JuGGernaut!"],
  "hero_name": "TuichAAreko",
  "hero_cards": "8s Tc",
  "board_cards": "8d 6c Ts 5d Ks",
  "stacks": [300, 300, 300],
  "positions": [1, 2, 3],
  "roles": {
    "dealer": "JuGGernaut!",
    "small_blind": "DOI002",
    "big_blind": "TuichAAreko"
  }
}
```

**Ejemplo de registro completo:**
```sql
id: 1
job_id: 9
screenshot_filename: "2025-10-22_11_32_AM_#SG3247423387.png"
-- Primer OCR (Hand ID)
ocr1_success: 1
ocr1_hand_id: "SG3247423387"
ocr1_error: NULL
-- Segundo OCR (Detalles)
ocr2_success: 1
ocr2_data: '{"players": [...], "roles": {...}}'
ocr2_error: NULL
-- Matching
matches_found: 1
status: "success"
```

#### Tabla `results` - MODIFICAR (opcional) 📊

**Agregar nuevas métricas en `stats_json`:**

```json
{
  "total_hands": 147,
  "matched_hands": 208,
  "match_rate": 0.95,
  "ocr_success_rate": 0.98,
  "resolved_files": 5,
  "failed_files": 0,

  // ===== NUEVAS MÉTRICAS =====
  "ocr1_success_rate": 0.999,      // Tasa éxito Hand ID extraction
  "ocr1_failed_count": 1,          // Cuántos screenshots fallaron OCR1
  "ocr2_success_rate": 0.95,       // Tasa éxito player details extraction
  "ocr2_failed_count": 13,         // Cuántos screenshots fallaron OCR2
  "avg_ocr1_time_ms": 800,         // Tiempo promedio OCR1
  "avg_ocr2_time_ms": 2200,        // Tiempo promedio OCR2
  "total_ocr_time_seconds": 795.0, // Tiempo total de ambos OCRs
  "role_mapping_success_rate": 0.92 // Tasa éxito mapeo por roles (Fase 2)
}
```

#### Tablas que **NO** cambian

- ✅ `jobs` - Se mantiene igual (los contadores actuales sirven)
- ✅ `files` - Se mantiene igual
- ✅ `logs` - Se mantiene igual (solo el contenido de logs cambia)

#### Migración de Base de Datos

**Archivo:** `database.py`

**Agregar a la función `init_db()`:**

```python
def init_db():
    """Initialize database with schema"""
    with get_db() as conn:
        conn.executescript(SCHEMA)

        # ===== MIGRATION: Add dual OCR support =====
        cursor = conn.execute("PRAGMA table_info(screenshot_results)")
        columns = [row[1] for row in cursor.fetchall()]

        dual_ocr_migrations = []

        # Fase 1 & 2: Dual OCR fields
        if 'ocr1_success' not in columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr1_success INTEGER DEFAULT 0"
            )
        if 'ocr1_hand_id' not in columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr1_hand_id TEXT"
            )
        if 'ocr1_error' not in columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr1_error TEXT"
            )
        if 'ocr2_success' not in columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr2_success INTEGER DEFAULT 0"
            )
        if 'ocr2_data' not in columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr2_data TEXT"
            )
        if 'ocr2_error' not in columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr2_error TEXT"
            )

        for migration in dual_ocr_migrations:
            conn.execute(migration)

        if dual_ocr_migrations:
            print(f"✅ Applied {len(dual_ocr_migrations)} dual OCR migrations")
```

#### Actualización de funciones DB

**Nuevas funciones en `database.py`:**

```python
def save_ocr1_result(job_id: int, screenshot_filename: str,
                     success: bool, hand_id: str = None, error: str = None):
    """Save first OCR (Hand ID) result"""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO screenshot_results
            (job_id, screenshot_filename, ocr1_success, ocr1_hand_id, ocr1_error,
             status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (job_id, screenshot_filename, int(success), hand_id, error,
              'ocr1_completed', datetime.utcnow().isoformat()))


def save_ocr2_result(screenshot_id: int, success: bool,
                     ocr_data: dict = None, error: str = None):
    """Save second OCR (player details) result"""
    with get_db() as conn:
        conn.execute("""
            UPDATE screenshot_results
            SET ocr2_success = ?, ocr2_data = ?, ocr2_error = ?,
                status = ?
            WHERE id = ?
        """, (int(success), json.dumps(ocr_data) if ocr_data else None,
              error, 'ocr2_completed', screenshot_id))
```

---

## Preguntas Abiertas

1. **¿Todos los screenshots de PokerCraft tienen indicators visibles (D, SB, BB)?**
   - Necesitamos verificar con más screenshots
   - ¿Qué pasa si un jugador ya foldeó?

2. **¿Cómo manejamos heads-up (2 jugadores)?**
   - En heads-up: button = small blind, otro jugador = big blind
   - ¿PokerCraft muestra esto correctamente?

3. **¿Qué pasa con mesas de 6-max?**
   - Actual sistema solo soporta 3-max
   - ¿Nueva propuesta escala mejor a 6-max?

4. **¿Costo/beneficio vale la pena?**
   - 2x costo API vs mejora en match rate
   - ¿Cuántos más matches necesitamos para justificar el costo?

5. **¿Orden de extracción importa?**
   - ¿Deberíamos hacer ambos OCRs en paralelo?
   - ¿O secuencial: primero Hand ID, luego (si match) detalles?

---

## Próximos Pasos

**Inmediato:**
1. ✅ Documentar todos los descubrimientos (este archivo)
2. ⏳ Decidir si implementar Fase 1
3. ⏳ Crear feature branch para desarrollo

**Si se aprueba implementación:**
1. Implementar Fase 1 (dos OCRs separados)
2. Testear con Job #9
3. Medir métricas
4. Si exitoso → Implementar Fase 2 (mapeo por dealer button)
5. Testing completo
6. Deploy a producción

**Alternativa (no implementar):**
1. Arreglar bug del mapeo invertido en código actual
2. Mejorar prompt actual del OCR para extraer Hand ID más confiablemente
3. Mantener arquitectura actual

---

## Referencias

**Archivos modificados durante sesión:**
- `CLAUDE.md` - Correcciones sobre Hero replacement
- `docs/diagrams/ggrevealer-workflow-visualizations.md` - Visualizaciones creadas

**Archivos relevantes para implementación:**
- `ocr.py` - Gemini Vision API integration
- `matcher.py` - Hand matching y seat mapping
- `main.py` - Pipeline orchestration
- `models.py` - Data models

**Commits relevantes:**
- `72ae5a3` - docs: Correct Hero replacement documentation

**Screenshots analizados:**
- Job #9, 10 screenshots del storage/uploads/9/screenshots/

**Hand history analizado:**
- `GG20251022-1432 - 4532845328 - 0.02 - 0.04 - 3max.txt`
- Hand #SG3247423387

---

**Fin del documento**

*Última actualización: 2025-09-29*
