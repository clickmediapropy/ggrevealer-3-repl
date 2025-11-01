# GGRevealer - Quick Reference Guide

## What is GGRevealer?

A FastAPI web application that de-anonymizes GGPoker hand history files by matching them with PokerCraft screenshots using Google Gemini Vision API for OCR. Outputs PokerTracker-compatible hand history files with real player names.

**Key Achievement**: 3-5% → 90-95% name coverage improvement through dual OCR system redesign.

---

## QUICK FILE REFERENCE

| File | Lines | Purpose |
|------|-------|---------|
| **main.py** | 2564 | FastAPI REST API, processing orchestration, 11-phase pipeline |
| **parser.py** | 324 | Parse GGPoker TXT hand histories, extract seats/actions |
| **ocr.py** | 448 | Dual OCR system: OCR1 (Hand ID), OCR2 (Player names) |
| **matcher.py** | 612 | Match hands to screenshots, role-based mapping (99% accuracy) |
| **writer.py** | 427 | Generate TXT outputs, 14 regex patterns, file classification |
| **validator.py** | 1068 | PokerTracker 4 validation (12 checks), identify rejection reasons |
| **database.py** | 805 | SQLite persistence (5 tables), job tracking, OCR results |
| **logger.py** | 129 | Structured logging, colored console, DB persistence |
| **models.py** | 139 | Type definitions (10 dataclasses) |
| **config.py** | 22 | Configuration constants, API pricing |

---

## SYSTEM ARCHITECTURE AT A GLANCE

```
Browser (index.html + app.js)
    ↓↑
FastAPI REST API (main.py)
    ↓
Processing Pipeline (11 phases)
├─ Parse TXT → GGPokerParser
├─ OCR1 all screenshots → Hand IDs
├─ Match hands ↔ screenshots
├─ OCR2 matched screenshots → Player names
├─ Role-based mapping → Real names
├─ Table aggregation
├─ Write TXT files → 14 regex patterns
├─ Validate PokerTracker compatibility
├─ Create ZIP archives
├─ Export debug JSON
└─ Generate AI debug prompts
    ↓
SQLite Database (ggrevealer.db)
    ↓
Google Gemini API (gemini-2.5-flash-image)
```

---

## THE 11-PHASE PROCESSING PIPELINE

### Phase 1: Parse Hand Histories (parser.py)
- Extract hand ID, timestamp, seats, stacks, positions, actions, board cards
- Support: Cash games, tournaments, 3-max, 6-max formats
- Output: `List[ParsedHand]`

### Phase 2: OCR1 - Hand ID Extraction (ocr.py)
- Ultra-simple prompt, extract ONLY hand ID
- Run on ALL screenshots (100% coverage)
- Model: `gemini-2.5-flash-image`
- Accuracy: 99.9% expected
- Cost: Minimal (simple task)

### Phase 3: Match Hands to Screenshots (matcher.py)
1. Normalize Hand IDs (remove prefixes)
2. Primary match: Hand ID comparison (99.9%)
3. Fallback: 100-point multi-criteria scoring
4. Validation gates: Player count, hero stack ±25%, ≥50% stack alignment
5. Output: `List[HandMatch]`

### Phase 4: Discard Unmatched Screenshots
- Save API costs by skipping OCR2 on unmatched screenshots
- Result: ~50% cost savings

### Phase 5: OCR2 - Player Details Extraction (ocr.py)
- Extract player names + role indicators (D/SB/BB)
- Run ONLY on matched screenshots
- Model: `gemini-2.5-flash-image`
- Accuracy: 99%
- Output: `ScreenshotAnalysis`

### Phase 6: Role-Based Mapping (matcher.py)
- Find dealer button (D indicator)
- Auto-calculate SB, BB positions
- Map anonymized IDs → real player names
- Accuracy: 99% (vs 80% counter-clockwise)

### Phase 7: Table Aggregation
- Group mappings by table name
- Apply one screenshot's mappings to ALL hands at that table
- Result: One screenshot can map 50+ hands

### Phase 8: Write Output Files (writer.py)
- Apply 14 regex replacement patterns in exact order
- Replace anonymized IDs with real names
- Generate per-table TXT files
- Output: `{table_name: txt_content}`

### Phase 9: Validate PokerTracker Compatibility (validator.py)
- 12 critical checks (pot size, blinds, cards, etc.)
- Classify files: `_resolved.txt` (clean) or `_fallado.txt` (unmapped IDs)
- Detect common PT4 rejection reasons

### Phase 10: Create ZIP Archives
- `resolved_hands.zip` - Ready for PokerTracker import
- `fallidos.zip` - Files with unmapped IDs (need more screenshots)

### Phase 11: Auto-Export Debug JSON & Optional AI Prompts
- Export complete job context to `storage/debug/debug_job_{id}_{ts}.json`
- Optionally generate AI-powered debugging prompt (Gemini 2.5 Flash)

---

## KEY ALGORITHMS

### Hand Matching: 3-Part Strategy

**Part 1: Normalize Hand IDs**
- "SG3260934198" → "3260934198" (remove prefixes)

**Part 2: Match Strategy**
- Primary (99.9%): `screenshot.hand_id == hand.hand_id`
- Fallback (0-100 pts): Hero cards (40), board (30), position (15), names (10), stack (5)

**Part 3: Validation Gates**
- Player count must match
- Hero stack within ±25%
- ≥50% of stacks within ±30%

### Role-Based Mapping: Find Real Names

**Step 1**: Extract role indicators from OCR2
- D = Dealer button (yellow badge)
- SB = Small blind player
- BB = Big blind player

**Step 2**: Map to real names
```
"5641b4a0" (anonymized ID) → "v1[nn]1" (extracted name)
"e3efcaed" (anonymized ID) → "Gyodong22" (extracted name)
"Hero" (special player) → "TuichAAreko" (from screenshot)
```

**Step 3**: Apply to entire table
- All hands at Table X use mappings from ANY screenshot of Table X

### Name Replacement: 14 Regex Patterns

**Critical Order** (most specific first):
1. Seat lines: `Seat 1: PlayerID ($100 in chips)`
2. Blind posts: `PlayerID: posts small blind $0.1` ← BEFORE general actions!
3-14. More patterns for actions, shows, etc.

**Key Detail**: Use `r'\g<1>'` syntax to avoid octal interpretation bugs

---

## DATACLASSES & TYPE HIERARCHY

```python
# From TXT parsing
ParsedHand
├── hand_id: str
├── seats: Seat[] (seat_number, player_id, stack, position)
├── board_cards: BoardCards (flop, turn, river)
├── actions: Action[] (street, player, action, amount)
└── raw_text: str

# From OCR screenshots
ScreenshotAnalysis
├── hand_id: str (from OCR1)
├── player_names: str[]
├── all_player_stacks: PlayerStack[] (name, stack, position)
├── hero_name: str (from OCR2)
├── dealer_player: str (from OCR2 role detection)
├── small_blind_player: str
└── big_blind_player: str

# Match result
HandMatch
├── hand_id: str
├── screenshot_id: str
├── confidence: float (0-100)
└── auto_mapping: {anonymized_id → real_name}

# Final mapping
NameMapping
├── anonymized_identifier: str
├── resolved_name: str
├── source: str ('auto-match', 'manual', 'imported')
└── confidence: float
```

---

## API ENDPOINTS

### Core Workflow
- `POST /api/upload` - Upload TXT + screenshot files
- `POST /api/process/{job_id}` - Start/reprocess job
- `GET /api/status/{job_id}` - Real-time status
- `GET /api/download/{job_id}` - Download `resolved_hands.zip`
- `GET /api/download-fallidos/{job_id}` - Download `fallidos.zip`

### Debugging
- `GET /api/debug/{job_id}` - Full debug info
- `POST /api/debug/{job_id}/generate-prompt` - AI debugging prompt
- `POST /api/debug/{job_id}/export` - Export debug JSON

### Validation
- `POST /api/validate` - Standalone hand validation
- `POST /api/validate-api-key` - Check Gemini API key

### Configuration
- `GET /api/config/budget` - Get budget limits
- `POST /api/config/budget` - Set budget limits

---

## PokerTracker 4 VALIDATION (12 Checks)

| # | Check | Severity | PT4 Impact |
|---|-------|----------|-----------|
| 1 | Pot size (Cash Drop fees) | CRITICAL | ❌ Rejects |
| 2 | Blind consistency | HIGH | ⚠ May reject |
| 3 | Stack sizes (no negatives) | CRITICAL | ❌ Rejects |
| 4 | Hand metadata format | HIGH | ⚠ Warns |
| 5 | Player ID format | HIGH | ⚠ Warns |
| 6 | Card validation (no dupes) | CRITICAL | ❌ Rejects |
| 7 | Game type support | HIGH | ⚠ Unsupported |
| 8 | Action sequence logic | MEDIUM | ⚠ May reject |
| 9 | Stack consistency | MEDIUM | ⚠ Warns |
| 10 | Split pots calculation | MEDIUM | ⚠ May reject |
| 11 | EV Cashout detection | HIGH | ⚠ Wrong stats |
| 12 | All-in with straddle | MEDIUM | ⚠ Bug in v4.18.x |

**Common Rejection Causes**:
- Cash Drop fees (1BB on pots > 30BB) not in hand history (40% of failures)
- Run It Three Times format (PT4 doesn't support) (15%)
- Blind posting mismatches (10%)
- Outdated PT4 version (15%)

---

## DATABASE SCHEMA (ggrevealer.db)

```sql
-- Jobs tracking
jobs (id, status, txt_files_count, screenshot_files_count, 
      matched_hands, name_mappings_count, ocr_processed_count, 
      ocr_total_count, api_tier, processing_time_seconds, ...)

-- File references
files (id, job_id, filename, file_type, file_path, uploaded_at)

-- Final results
results (id, job_id, output_txt_path, mappings_json, stats_json, ...)

-- Per-screenshot OCR tracking
screenshot_results (id, job_id, screenshot_filename, 
                   ocr1_success, ocr1_hand_id, ocr1_retry_count,
                   ocr2_success, ocr2_data, matches_found, 
                   discard_reason, ...)

-- Structured logs
logs (id, job_id, level, timestamp, message, extra_data_json)
```

---

## EXTERNAL INTEGRATIONS

### Google Gemini API
- **Model**: `gemini-2.5-flash-image` (optimized for dual OCR)
- **OCR1**: Hand ID extraction (99.9% accuracy, minimal cost)
- **OCR2**: Player names + roles (99% accuracy)
- **Rate Limiting**:
  - Free tier: 14 requests/minute
  - Paid tier: 10 concurrent, unlimited
- **Cost**: $0.0164 per screenshot (dual OCR average)
- **Async**: Semaphore-based concurrency control

### SQLite Database
- **File**: `ggrevealer.db`
- **Auto-migration**: Schema updates on startup
- **Context managers**: Safe connection handling
- **Buffered writes**: Batch persistence for performance

### Frontend
- **Framework**: Bootstrap 5.3 (responsive)
- **Icons**: Bootstrap Icons
- **Requests**: Fetch API + jQuery
- **Templating**: Jinja2 (server-side)

---

## IMPORTANT CONFIGURATION

### Key Constants (config.py)
```python
GEMINI_COST_PER_IMAGE = 0.0164  # Real billing data (Oct 2025)
GEMINI_MODEL = "gemini-2.5-flash-image"
```

### Environment Variables (.env)
```
GEMINI_API_KEY=your_api_key_here
```

### Upload Limits (main.py)
```python
MAX_TXT_FILES = 300
MAX_SCREENSHOT_FILES = 300
MAX_UPLOAD_SIZE_MB = 300
```

---

## RUNNING THE APPLICATION

### Start Server
```bash
python main.py
# or
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

### Run Tests
```bash
pytest test_*.py -v                    # All tests
pytest test_validator.py -v            # Validation tests only
```

### Manual Validation
```bash
# Validate standalone hand history
curl -X POST http://localhost:5000/api/validate \
  -F "file=@hand_history.txt"
```

---

## STORAGE STRUCTURE

```
storage/
├── uploads/{job_id}/
│   ├── txt/*.txt                     # Original hand histories
│   └── screenshots/*.png             # PokerCraft screenshots
│
├── outputs/{job_id}/
│   ├── TableName_resolved.txt         # 100% de-anonymized ✅
│   ├── TableName_fallado.txt          # Has unmapped IDs
│   ├── resolved_hands.zip             # Ready for PT4
│   └── fallidos.zip                   # Need more screenshots
│
├── debug/
│   └── debug_job_123_2025-10-29T14-30-45.json
│
└── ggrevealer.db                      # SQLite database
```

---

## KEY PERFORMANCE METRICS

| Metric | Value | Notes |
|--------|-------|-------|
| **Name Coverage** | 90-95% | Improved from 3-5% |
| **OCR1 Accuracy** | 99.9% | Hand ID extraction |
| **OCR2 Accuracy** | 99% | Player name extraction |
| **Role-Based Mapping** | 99% | Dealer/SB/BB detection |
| **Cost Savings** | ~50% | OCR2 only on matched SS |
| **Time per Job** | <30 min | For 300 screenshots |
| **Max Concurrent** | 10 (paid) / 1 (free) | Gemini API |
| **Cost per Screenshot** | $0.0164 | Dual OCR average |

---

## COMMON ISSUES & SOLUTIONS

### Problem: Low match rate (< 50%)
**Solution**: Check OCR1 results in database `screenshot_results` table
- Is `ocr1_success = 1`?
- Is `ocr1_hand_id` populated?
- Run `GET /api/debug/{job_id}/screenshots` to see OCR errors

### Problem: Unmapped player IDs in output
**Solution**: Check screenshot extraction in `screenshot_results`
- Is `ocr2_success = 1`?
- Check `ocr2_data` JSON for player names
- Verify `matches_found > 0` (screenshot actually matched hands)

### Problem: PokerTracker rejects output
**Solution**: Run validation:
```bash
curl -X POST http://localhost:5000/api/validate \
  -F "file=@output.txt"
```
Check for CRITICAL severity errors (pot size, duplicate cards, etc.)

### Problem: Timeout on large batch
**Solution**: Increase rate limiting
- Check `api_tier` in database
- Free tier: 14 req/min
- Upgrade to paid tier for faster processing

---

## TEST COVERAGE

17 test files covering:
- Parser (role detection, hand extraction)
- OCR (model selection, retry logic)
- Matcher (hand ID normalization, scoring, validation gates)
- Writer (regex patterns, file classification)
- Validator (PokerTracker compatibility, 12 checks)
- Role-based mapping (dealer detection, position calculation)
- Table aggregation (cross-hand mapping)
- Prompt generation (AI debugging)

Run all: `pytest test_*.py -v`

---

## RECENT IMPROVEMENTS (Oct-Nov 2025)

1. **Dual OCR System Redesign** - Separated Hand ID (OCR1) from player details (OCR2)
2. **Role-Based Mapping** - Dealer button detection, auto-calculated positions (99% accuracy)
3. **Match Quality Validation** - 3 gates prevent incorrect matches
4. **Structured Logging** - Database persistence, colored console output
5. **AI-Powered Debugging** - Gemini 2.5 Flash generates actionable prompts
6. **Auto-Export Debug JSON** - Every job exports complete context for analysis
7. **Smart Rate Limiting** - Free tier (14 req/min), Paid tier (unlimited)
8. **Budget Tracking** - Per-user API key, monthly spend limits

---

## NEXT STEPS FOR DEVELOPMENT

1. **Full Stack Testing** - More integration tests
2. **UI Enhancements** - Better visualization of OCR results
3. **Export Formats** - Support PT5, Holdem Manager, etc.
4. **Batch Processing** - Process multiple jobs in parallel
5. **ML Improvements** - Fine-tune prompts based on failure patterns
