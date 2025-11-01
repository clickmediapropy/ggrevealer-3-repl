# GGRevealer Architecture & Structure Analysis

**Generated**: November 2025
**Codebase Size**: 6,538 lines of Python code (8 main modules)
**Test Coverage**: 17 test files for validation and development

---

## DIRECTORY STRUCTURE

```
ggrevealer-3-repl/
├── CORE MODULES (Production Code)
│   ├── main.py                    (2564 lines) - FastAPI app, endpoints, processing pipeline
│   ├── parser.py                  (324 lines)  - GGPoker hand history parser
│   ├── ocr.py                     (448 lines)  - Dual OCR system (OCR1 + OCR2)
│   ├── matcher.py                 (612 lines)  - Hand-to-screenshot matching + role-based mapping
│   ├── writer.py                  (427 lines)  - TXT output generation with validation
│   ├── validator.py               (1068 lines) - PokerTracker 4 validation system (12 checks)
│   ├── database.py                (805 lines)  - SQLite persistence layer
│   ├── logger.py                  (129 lines)  - Structured logging system
│   ├── models.py                  (139 lines)  - Type definitions (10 dataclasses)
│   └── config.py                  (22 lines)   - Configuration constants
│
├── FRONTEND (Web UI)
│   ├── templates/
│   │   └── index.html             (43KB) - Main application page
│   └── static/
│       ├── js/
│       │   └── app.js             (107KB) - Client-side logic
│       └── css/
│           └── styles.css         (20KB)  - Bootstrap 5 + custom styling
│
├── STORAGE (Runtime Data)
│   ├── uploads/{job_id}/
│   │   ├── txt/                   - Original hand history files
│   │   └── screenshots/           - PokerCraft screenshots
│   ├── outputs/{job_id}/
│   │   ├── {table}_resolved.txt   - Fully de-anonymized hands
│   │   ├── {table}_fallado.txt    - Hands with unmapped IDs
│   │   ├── resolved_hands.zip     - Archive of _resolved.txt
│   │   └── fallidos.zip           - Archive of _fallado.txt
│   ├── debug/
│   │   └── debug_job_{id}_{ts}.json - Auto-exported debug info
│   └── ggrevealer.db              - SQLite database
│
├── DEVELOPMENT
│   ├── test_*.py (17 files)       - Unit and integration tests
│   ├── .env                       - Environment variables (GEMINI_API_KEY)
│   ├── requirements.txt           - Python dependencies
│   └── CLAUDE.md                  - Project documentation
│
└── CONFIGURATION
    ├── .git/                      - Version control
    ├── .claude/                   - Claude Code configuration
    └── docs/                      - Planning documents


### Frontend Structure (templates/index.html)

- Single-Page Application (SPA) with Bootstrap 5
- Responsive sidebar navigation (New Job, Reprocess, History)
- API Key management modal
- Budget tracking sidebar
- Tab-based interface (Upload, Process, Results, Debug)
- Real-time status updates via WebSocket
- Debug prompt display and copy functionality


### Static Assets

js/app.js (2700+ lines):
  - Job creation and file upload
  - Real-time status polling
  - Download management
  - API Key configuration
  - Budget visualization
  - Debug prompt generation

css/styles.css:
  - Custom color scheme
  - Responsive layout
  - Status indicators
  - Progress bars
```

---

## CORE ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                   WEB FRONTEND (Browser)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  index.html (Jinja2 Template)                        │   │
│  │  - Upload form (TXT + Screenshots)                   │   │
│  │  - Real-time job status                             │   │
│  │  - Download results (ZIP files)                      │   │
│  │  - Debug info & AI-powered prompts                  │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  app.js (jQuery/Fetch API)                           │   │
│  │  - Form validation & submission                      │   │
│  │  - API calls to FastAPI backend                      │   │
│  │  - Status polling every 2 seconds                    │   │
│  │  - Download management                               │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↓↑
                    FASTAPI REST ENDPOINTS
┌─────────────────────────────────────────────────────────────┐
│                   FASTAPI BACKEND (main.py)                  │
│                                                               │
│  REST ENDPOINTS:                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  POST   /api/upload                                 │   │
│  │  POST   /api/process/{job_id}                       │   │
│  │  GET    /api/status/{job_id}                        │   │
│  │  GET    /api/download/{job_id}                      │   │
│  │  GET    /api/download-fallidos/{job_id}             │   │
│  │  GET    /api/jobs (list all)                        │   │
│  │  DELETE /api/job/{job_id}                           │   │
│  │  POST   /api/validate (standalone validation)       │   │
│  │  POST   /api/debug/{job_id}/generate-prompt         │   │
│  │  GET    /api/debug/{job_id}                         │   │
│  │  POST   /api/debug/{job_id}/export                  │   │
│  │  POST   /api/validate-api-key                       │   │
│  │  GET    /api/config/budget                          │   │
│  │  POST   /api/config/budget                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  PROCESSING PIPELINE (run_processing_pipeline):              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ 1. Parse TXT files → Extract hands                  │   │
│  │ 2. OCR1: Extract Hand IDs from screenshots           │   │
│  │ 3. Match hands to screenshots (Hand ID matching)    │   │
│  │ 4. OCR2: Extract player details from matched SS     │   │
│  │ 5. Role-based mapping (D/SB/BB → seat numbers)      │   │
│  │ 6. Table aggregation (apply all mappings)           │   │
│  │ 7. Write outputs (TXT files with replacements)      │   │
│  │ 8. Validate PokerTracker compatibility              │   │
│  │ 9. Create ZIP archives                              │   │
│  │ 10. Auto-export debug JSON                          │   │
│  │ 11. Generate AI debug prompts (optional)             │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
          ↓↑              ↓↑              ↓↑
    PARSER       MATCHER      WRITER    VALIDATOR
┌──────────────┬────────────┬──────────┬─────────────┐
│ parser.py    │ matcher.py │writer.py │ validator.py│
└──────────────┴────────────┴──────────┴─────────────┘
          ↓↑              ↓↑
      OCR SYSTEM       DATABASE
┌──────────────────┬──────────────────┐
│ ocr.py (Dual)    │ database.py      │
│ - OCR1: Hand ID  │ - jobs table     │
│ - OCR2: Players  │ - files table    │
└──────────────────┴──────────────────┘
          ↓↑              ↓↑
   GOOGLE GEMINI    SQLITE (ggrevealer.db)
```

---

## DATA FLOW DIAGRAM

```
USER UPLOADS FILES
       ↓
   ┌───────────────────────────┐
   │ upload_form (POST /upload)│
   │ - TXT files (hand histories)
   │ - PNG files (screenshots) │
   └───────────────┬───────────┘
                   ↓
           DATABASE (jobs table)
           - Create new job
           - Store file references
           ↓
    USER CLICKS "PROCESS JOB"
           ↓
    ┌──────────────────────────────┐
    │ run_processing_pipeline()    │  ← Background task
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ PHASE 1: Parse Hand Histories│  parser.py
    │ GGPokerParser.parse_file()   │
    │ - Extract hand ID            │
    │ - Extract seats & stacks     │
    │ - Extract actions            │
    │ → List[ParsedHand]           │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ PHASE 2: OCR1 - Hand ID Only │  ocr.py
    │ ocr_hand_id() [ALL screenshots]
    │ - Ultra-simple Gemini prompt │
    │ - Extract: Hand ID only      │
    │ - 99.9% accuracy expected    │
    │ → {screenshot: hand_id}      │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ PHASE 3: Match Hands ↔ SS    │  matcher.py
    │ find_best_matches()          │
    │ 1. Normalize Hand IDs        │
    │ 2. Primary: Hand ID match    │
    │ 3. Fallback: 100-point score │
    │ 4. Validate match quality    │
    │ → List[HandMatch]            │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ PHASE 4: Discard Unmatched   │
    │ - Skip OCR2 on unmatched SS  │
    │ - 50% cost savings           │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ PHASE 5: OCR2 - Player Names │  ocr.py
    │ ocr_player_details() [MATCHED only]
    │ - Extract player names       │
    │ - Extract role indicators    │
    │ → ScreenshotAnalysis         │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ PHASE 6: Role-Based Mapping  │  matcher.py
    │ _build_seat_mapping_by_roles()
    │ - Find dealer button         │
    │ - Auto-calculate SB/BB       │
    │ - Map {anon_id: real_name}   │
    │ → Dict[str, str] per hand    │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ PHASE 7: Table Aggregation   │
    │ - Group mappings by table    │
    │ - Apply to ALL hands/table   │
    │ - One screenshot → many hands│
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ PHASE 8: Write Output Files  │  writer.py
    │ generate_txt_files_by_table()│
    │ - Apply 14 regex patterns    │
    │ - Replace anon IDs w/ names  │
    │ - Per-table output files     │
    │ → {table_name: txt_content}  │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ PHASE 9: Validate PT4        │  validator.py
    │ GGPokerHandHistoryValidator  │
    │ - 12 validation checks       │
    │ - Pot size, blinds, etc.     │
    │ - File classification        │
    │ → _resolved.txt vs _fallado  │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ PHASE 10: Create ZIPs        │
    │ - resolved_hands.zip         │
    │ - fallidos.zip               │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ PHASE 11: Export Debug JSON  │  main.py
    │ - Auto-export to storage/    │
    │ - Full job context           │
    │ - All metrics & errors       │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ OPTIONAL: AI Debug Prompts   │  main.py
    │ POST /api/debug/{id}/gen...  │
    │ - Analyze metrics            │
    │ - Gemini 2.5 Flash generation│
    │ - Actionable debugging steps │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ DATABASE PERSIST ALL         │  database.py
    │ - Job status = completed     │
    │ - Save statistics            │
    │ - Save logs                  │
    └──────────────────────────────┘
           ↓
    ┌──────────────────────────────┐
    │ USER DOWNLOADS RESULTS       │  FastAPI
    │ - ZIP files                  │
    │ - Ready for PT4 import       │
    └──────────────────────────────┘
```

---

## PYTHON MODULE BREAKDOWN

### 1. **main.py** (2564 lines)
   - **Purpose**: FastAPI application entry point and REST API
   - **Key Functions**:
     - `@app.post("/api/upload")` - File upload handler
     - `@app.post("/api/process/{job_id}")` - Start processing pipeline
     - `@app.get("/api/status/{job_id}")` - Real-time status updates
     - `@app.get("/api/download/{job_id}")` - Download resolved ZIP
     - `run_processing_pipeline()` - Main processing orchestration (11 phases)
     - `_analyze_debug_data()` - Analyze job metrics for debugging
     - `_generate_fallback_prompt()` - Fallback prompt generation
   - **Integrations**:
     - FastAPI (REST framework)
     - Google Gemini API (via genai library)
     - Background tasks (asyncio)

### 2. **parser.py** (324 lines)
   - **Purpose**: Parse GGPoker hand history TXT files
   - **Main Class**: `GGPokerParser`
   - **Key Methods**:
     - `parse_file(content)` - Parse multiple hands from text
     - `parse_hand(text)` - Parse single hand
     - `_parse_seats()` - Extract seat information
     - `_parse_board_cards()` - Extract community cards
     - `_parse_actions()` - Extract player actions
     - `find_seat_by_role()` - Find seat by role (D/SB/BB)
   - **Returns**: `List[ParsedHand]` dataclass objects

### 3. **ocr.py** (448 lines)
   - **Purpose**: Dual OCR system for screenshot analysis
   - **Key Async Functions**:
     - `ocr_hand_id()` - Phase 1: Extract ONLY hand ID
     - `ocr_player_details()` - Phase 2: Extract player names + roles
     - `ocr_screenshot()` - Legacy: Combined OCR (deprecated)
   - **Model**: `gemini-2.5-flash-image` (Dual OCR optimized)
   - **Returns**: `ScreenshotAnalysis` dataclass

### 4. **matcher.py** (612 lines)
   - **Purpose**: Match hands to screenshots + role-based mapping
   - **Key Functions**:
     - `find_best_matches()` - Main matching algorithm
     - `validate_match_quality()` - Pre-match validation gates
     - `_calculate_match_score()` - 100-point scoring system
     - `_build_seat_mapping()` - Map anonymized IDs to names
     - `_build_seat_mapping_by_roles()` - Role-based mapping (99% accuracy)
     - `_normalize_hand_id()` - Remove OCR/parser prefixes
   - **Returns**: `List[HandMatch]` objects

### 5. **writer.py** (427 lines)
   - **Purpose**: Generate TXT output files with name replacement
   - **Key Functions**:
     - `generate_txt_files_by_table()` - Group hands by table
     - `generate_final_txt()` - Apply 14 regex replacement patterns
     - `detect_unmapped_ids_in_text()` - Find remaining anon IDs
     - `validate_output_format()` - 10 PokerTracker validations
     - `extract_table_name()` - Extract table name from hand
   - **Regex Patterns**: 14 patterns for name replacement (exact order critical)

### 6. **validator.py** (1068 lines)
   - **Purpose**: PokerTracker 4 validation system
   - **Main Class**: `GGPokerHandHistoryValidator`
   - **12 Validation Checks**:
     1. Pot size (40% of failures)
     2. Blind consistency
     3. Stack sizes
     4. Hand metadata
     5. Player identifiers
     6. Card validation
     7. Game type support
     8. Action sequence
     9. Stack consistency
     10. Split pots
     11. EV cashout detection
     12. All-in with straddle
   - **Returns**: `PT4ValidationResult` with errors/warnings

### 7. **database.py** (805 lines)
   - **Purpose**: SQLite persistence layer
   - **Tables**:
     - `jobs` - Job tracking (status, counts, stats)
     - `files` - Uploaded TXT/PNG references
     - `results` - Output files and mappings
     - `screenshot_results` - Per-screenshot OCR results
     - `logs` - Structured job logs
   - **Key Functions**:
     - `init_db()` - Create/migrate schema
     - `create_job()` - Create new job record
     - `save_screenshot_result()` - Persist OCR results
     - `update_job_stats()` - Update statistics
     - `save_budget_config()` - Store API budget settings

### 8. **logger.py** (129 lines)
   - **Purpose**: Structured logging system
   - **Main Class**: `Logger`
   - **Log Levels**: DEBUG, INFO, WARNING, ERROR, CRITICAL
   - **Features**:
     - Colored console output
     - Database persistence
     - Buffered writes for batch persistence
     - Job-specific loggers with context

### 9. **models.py** (139 lines)
   - **Purpose**: Type definitions (dataclasses)
   - **10 Main Classes**:
     1. `Seat` - Player seat info
     2. `BoardCards` - Community cards
     3. `Action` - Player action
     4. `TournamentInfo` - Tournament details
     5. `ParsedHand` - Parsed hand from TXT
     6. `PlayerStack` - Stack from OCR
     7. `ScreenshotAnalysis` - OCR result
     8. `HandMatch` - Hand ↔ Screenshot match
     9. `NameMapping` - Anonymized ↔ Real name
     10. `ValidationResult` - Validation output

### 10. **config.py** (22 lines)
   - **Purpose**: Configuration constants
   - **Key Constants**:
     - `GEMINI_COST_PER_IMAGE` = $0.0164 (dual OCR average)
     - `GEMINI_MODEL` = "gemini-2.5-flash-image"
     - Updated with real billing data (Oct 2025)

---

## KEY ALGORITHMS & WORKFLOWS

### Hand Matching Algorithm (matcher.py)

```
1. NORMALIZE HAND IDs
   "SG3260934198" → "3260934198"
   "HH1234567890" → "1234567890"

2. PRIMARY MATCH (Hand ID from OCR1)
   IF screenshot.hand_id == hand.hand_id:
       confidence = 100 points ✅

3. FALLBACK MATCH (100-point scoring)
   score = 0
   IF hero_cards_match:     score += 40
   IF board_cards_match:    score += 30
   IF hero_position_match:  score += 15
   IF player_names_match:   score += 10
   IF stack_similar:        score += 5
   IF timestamp_within_2min: score += 20
   
   IF score >= 70.0:
       confidence = score points ✅

4. VALIDATION GATES (before accepting match)
   Check 1: Player count must match
   Check 2: Hero stack within ±25%
   Check 3: ≥50% of stacks within ±30%

5. DUPLICATE PREVENTION
   Reject if multiple anon IDs → same real name
   (within same hand only)
```

### Role-Based Mapping (matcher.py)

```
OCR2 Extracts: Player names + role indicators (D/SB/BB)

METHOD:
1. Find dealer button (D indicator)
2. Calculate positions:
   SB = (dealer_index + 1) % total_players
   BB = (dealer_index + 2) % total_players

3. Map anonymized IDs to real names:
   "5641b4a0" (seat 2) → "v1[nn]1" (SB)
   "e3efcaed" (seat 1) → "Gyodong22" (BB)
   "Hero" (seat 3) → "TuichAAreko" (D)

4. Table Aggregation:
   Apply mappings from screenshot to ALL hands at that table
   One screenshot can de-anonymize 50+ hands

ACCURACY: 99% (vs 80% with counter-clockwise calculation)
```

### Name Replacement Regex (writer.py)

```
14 PATTERNS (in order - most specific first):

1. Seat lines with money:
   "Seat 1: 5641b4a0 ($100 in chips)" 
   → "Seat 1: TuichAAreko ($100 in chips)"

2. Blind posts (BEFORE general actions):
   "5641b4a0: posts small blind $0.1"
   → "TuichAAreko: posts small blind $0.1"

3-14. More patterns for actions, shows, collects, etc.

CRITICAL: 
- Apply in exact order
- Use raw f-strings to avoid octal interpretation
- Most specific patterns first
- Prevent ID conflicts
```

### PokerTracker 4 Validation (validator.py)

```
12 CRITICAL CHECKS:

CRITICAL SEVERITY (hand rejected):
✗ Invalid pot size (Cash Drop fees)
✗ Duplicate cards in deck
✗ Run It Three Times detected
✗ Negative stack amounts

HIGH SEVERITY (warning shown):
⚠ Blind posting mismatch
⚠ EV Cashout detected
⚠ Unsupported game type

MEDIUM SEVERITY (may import):
⚠ Straddle with all-in
⚠ Invalid Hand ID format

LOW SEVERITY (informational):
ℹ Unknown hand prefix
ℹ Cosmetic issues
```

---

## API ENDPOINTS

### Job Management
- `POST   /api/upload` - Upload TXT + screenshot files, create job
- `POST   /api/process/{job_id}` - Start/reprocess job
- `GET    /api/status/{job_id}` - Real-time status + progress
- `DELETE /api/job/{job_id}` - Delete job and files
- `GET    /api/jobs` - List all jobs

### Download Results
- `GET    /api/download/{job_id}` - Download resolved_hands.zip
- `GET    /api/download-fallidos/{job_id}` - Download fallidos.zip

### Validation & Configuration
- `POST   /api/validate` - Standalone hand history validation
- `POST   /api/validate-api-key` - Verify Gemini API key
- `GET    /api/config/budget` - Get budget config
- `POST   /api/config/budget` - Set budget limits

### Debugging & Diagnostics
- `GET    /api/debug/{job_id}` - Full debug information
- `POST   /api/debug/{job_id}/export` - Export debug JSON
- `POST   /api/debug/{job_id}/generate-prompt` - AI-powered debugging prompt
- `GET    /api/job/{job_id}/screenshots` - Detailed screenshot results

---

## EXTERNAL INTEGRATIONS

### Google Gemini API
- **Model**: `gemini-2.5-flash-image` (Dual OCR optimized)
- **OCR1**: Extract Hand ID (99.9% accuracy)
- **OCR2**: Extract player names + roles (99% accuracy)
- **Async Processing**: 10 concurrent requests (free tier: 1 concurrent)
- **Cost**: $0.0164 per screenshot (dual OCR average)
- **Rate Limiting**: Free tier 14 req/min, Paid tier unlimited

### Database (SQLite)
- **File**: `ggrevealer.db`
- **Tables**: 5 main tables + auto-migration
- **Persistence**: Jobs, files, results, OCR data, logs

### Frontend Libraries
- **Bootstrap 5.3** - Responsive UI
- **Bootstrap Icons** - Icon library
- **jQuery/Fetch API** - AJAX requests
- **Jinja2** - Server-side templating

---

## DATACLASS HIERARCHY

```
ParsedHand (from parser.py)
├── hand_id: str
├── timestamp: datetime
├── seats: List[Seat]
│   ├── seat_number: int
│   ├── player_id: str (e.g., "5641b4a0" or "Hero")
│   ├── stack: float
│   └── position: Position (BTN, SB, BB, etc.)
├── board_cards: BoardCards
│   ├── flop: List[str]
│   ├── turn: str
│   └── river: str
├── actions: List[Action]
│   ├── street: Street
│   ├── player: str
│   ├── action: ActionType
│   └── amount: float
└── raw_text: str (original TXT)

ScreenshotAnalysis (from ocr.py)
├── screenshot_id: str
├── hand_id: str (from OCR1)
├── player_names: List[str]
├── all_player_stacks: List[PlayerStack]
│   ├── player_name: str
│   ├── stack: float
│   └── position: int
├── hero_name: str (from OCR2)
├── dealer_player: str (from OCR2)
├── small_blind_player: str (from OCR2)
└── big_blind_player: str (from OCR2)

HandMatch (from matcher.py)
├── hand_id: str
├── screenshot_id: str
├── confidence: float (0-100)
└── auto_mapping: Dict[str, str]
    └── "5641b4a0" → "TuichAAreko"

NameMapping (from writer.py)
├── anonymized_identifier: str
├── resolved_name: str
├── source: str ('auto-match', 'manual', 'imported')
└── confidence: float
```

---

## TEST COVERAGE (17 Test Files)

```
test_cli.py                    - CLI configuration tests
test_full_matching.py          - End-to-end matching tests
test_job3_matching.py          - Job #3 regression tests
test_matching_simple.py        - Basic matching scenarios
test_metrics.py                - Metric calculation tests
test_ocr1_retry.py             - OCR1 retry logic
test_ocr_fix.py                - OCR fixes and edge cases
test_ocr_model.py              - Model selection tests
test_parser_roles.py           - Parser role detection
test_priority1_fixes.py        - Priority fixes validation
test_prompt_generation.py      - Debug prompt generation
test_role_based_mapping.py     - Role-based mapping tests
test_seat_mapping.py           - Seat mapping logic
test_table_wide_mapping.py     - Table aggregation tests
test_task7_dual_ocr.py         - Dual OCR system tests
test_validator.py              - PokerTracker validation (16 cases)
analyze_job9_txt.py            - Job analysis utility
```

---

## CONFIGURATION & DEPENDENCIES

### Python Dependencies (requirements.txt)
```
google-genai>=1.27.0          - Google Gemini API
python-dotenv>=1.0.0          - Environment variables
fastapi>=0.104.0              - Web framework
uvicorn>=0.24.0               - ASGI server
python-multipart>=0.0.6       - File upload handling
aiosqlite>=0.19.0             - Async SQLite
jinja2>=3.1.0                 - HTML templating
```

### Environment Variables (.env)
```
GEMINI_API_KEY=your_api_key   - Google Gemini API key
```

### Running the Application
```bash
# Start server
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 5000 --reload

# Run tests
python -m pytest test_*.py -v

# Standalone validation
python -m pytest test_validator.py -v
```

---

## KEY FEATURES SUMMARY

### Input Processing (Parser)
- Parse GGPoker hand history TXT files
- Extract: hand ID, timestamp, seats, stacks, actions, board cards
- Support: Cash games & tournaments, 3-max & 6-max formats

### Dual OCR System (Optimized Sept 2025)
- **Phase 1 (OCR1)**: Ultra-simple prompt, Extract Hand ID only (99.9% accuracy)
- **Phase 2 (OCR2)**: Extract player names + role indicators (99% accuracy)
- **Result**: 90-95% name coverage (vs 3-5% before)
- **Cost Savings**: ~50% (OCR2 only on matched screenshots)

### Intelligent Matching
- Primary: Hand ID matching (99.9% accuracy via OCR1)
- Fallback: 100-point multi-criteria scoring
- Validation: 3 gates prevent incorrect matches
- Table Aggregation: One screenshot maps entire table

### Role-Based Mapping
- Dealer button detection (D indicator)
- Auto-calculate SB/BB positions
- 99% accuracy (vs 80% with counter-clockwise)
- Eliminates position calculation errors

### Output Generation
- 14 regex patterns for name replacement
- Per-table file generation
- File classification: _resolved.txt vs _fallado.txt
- ZIP archive creation

### PokerTracker 4 Compatibility
- 12 critical validation checks
- Identifies PT4 rejection reasons
- Detects Cash Drop fees, Run It Three Times, etc.
- Real PT4 error messages

### Debugging & Monitoring
- Structured logging with database persistence
- Auto-exported debug JSON per job
- AI-powered debugging prompt generation (Gemini 2.5 Flash)
- Real-time status updates
- Comprehensive metrics (30+ metrics across 5 categories)

### Budget & Rate Limiting
- Per-user API key support
- Monthly budget tracking
- Free tier: 14 requests/minute (smart rate limiting)
- Paid tier: Unlimited concurrent requests
- Cost calculation: $0.0164 per screenshot

---

## ENTRY POINTS & EXECUTION FLOW

```
ENTRY POINT: main.py
  └─ app = FastAPI()
      └─ startup_event() → init_db()
          └─ Create/migrate SQLite schema
              ├─ jobs table
              ├─ files table
              ├─ results table
              ├─ screenshot_results table
              └─ logs table

WORKFLOW: User starts job
  1. Frontend: POST /api/upload
     └─ main.py: Save TXT + screenshot files
        └─ database.py: Create job record

  2. Frontend: POST /api/process/{job_id}
     └─ main.py: run_processing_pipeline()
        ├─ parser.py: Parse hands
        ├─ ocr.py: OCR1 all screenshots
        ├─ matcher.py: Find best matches
        ├─ ocr.py: OCR2 matched screenshots
        ├─ matcher.py: Role-based mapping
        ├─ writer.py: Generate TXT files
        ├─ validator.py: Validate output
        ├─ main.py: Create ZIPs
        ├─ main.py: Export debug JSON
        ├─ database.py: Persist results
        └─ logger.py: Save logs

  3. Frontend: GET /api/status/{job_id}
     └─ database.py: Fetch job status

  4. Frontend: GET /api/download/{job_id}
     └─ FastAPI: Serve ZIP file
```

---

## CRITICAL IMPLEMENTATION PATTERNS

### Async/Await Pattern (ocr.py)
```python
async def ocr_hand_id(screenshot_path, api_key):
    async with semaphore:  # Rate limiting
        response = await client.aio.models.generate_content()
        return (success, hand_id, error)
```

### Database Context Manager (database.py)
```python
@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        yield conn
    finally:
        conn.close()
```

### Structured Logging (logger.py)
```python
logger = get_job_logger(job_id)
logger.info("Message", extra_key=value)  # Logged to console + DB
logger.flush_to_db()  # Batch persist
```

### Dataclass-based Type Safety (models.py)
```python
@dataclass
class ParsedHand:
    hand_id: str
    seats: List[Seat]
    # ...
```

---

## STORAGE PATHS & FILE ORGANIZATION

```
storage/
├── uploads/{job_id}/
│   ├── txt/filename.txt        → Original hand history
│   └── screenshots/filename.png → PokerCraft screenshot

├── outputs/{job_id}/
│   ├── Table_Name_resolved.txt  → 100% de-anonymized (ready for PT4)
│   ├── Table_Name_fallado.txt   → Has unmapped IDs
│   ├── resolved_hands.zip       → All _resolved.txt files
│   └── fallidos.zip             → All _fallado.txt files

├── debug/
│   └── debug_job_123_2025-10-29T14-30-45.json
        ├── job_info
        ├── statistics
        ├── screenshot_results
        ├── file_results
        ├── errors
        └── logs

└── ggrevealer.db              → SQLite database
    ├── jobs(id, status, stats, ...)
    ├── files(id, job_id, filename, ...)
    ├── results(job_id, output_txt, stats, ...)
    ├── screenshot_results(screenshot_id, ocr1, ocr2, ...)
    └── logs(level, message, job_id, ...)
```

