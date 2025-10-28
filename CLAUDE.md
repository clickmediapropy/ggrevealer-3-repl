# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GGRevealer** is a FastAPI web application that de-anonymizes GGPoker hand history files by matching them with PokerCraft screenshots using Google Gemini Vision API for OCR. The system outputs PokerTracker-compatible hand history files with real player names.

**Tech Stack**: Python 3.11+ • FastAPI • SQLite • Google Gemini 2.5 Flash Vision • Vanilla JS + Bootstrap 5

## User Preferences

- Prefer simple language
- Want iterative development
- Ask before making major changes
- Prefer detailed explanations

## Development Commands

### Running the Application
```bash
# Start the server (port 5000)
python main.py

# Alternative with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 5000 --reload

# Quick restart (kills port 8000 and restarts - NOTE: restart.sh uses port 8000, main.py uses port 5000)
./restart.sh
```

### Testing
```bash
# Run CLI test suite (tests parser, writer, and API key configuration)
python test_cli.py

# Run matching tests
python test_matching_simple.py
python test_job3_matching.py
python test_full_matching.py
```

### Environment Setup
Create `.env` file with:
```
GEMINI_API_KEY=your_api_key_here
```
Get API key from: https://makersuite.google.com/app/apikey

## Architecture & Data Flow

### Core Pipeline (main.py:740-1144 `run_processing_pipeline`)

1. **Parse TXT files** → Extract hand histories using `GGPokerParser.parse_file()`
2. **OCR Screenshots** → Parallel async processing (10 concurrent) with `ocr_screenshot()`
3. **Match Hands** → Primary key matching using Hand ID (with normalization), fallback to 100-point scoring
4. **Generate Mappings** → Build seat-based anonymized_id → real_name mappings with duplicate detection
5. **Write Outputs** → Generate per-table TXT files with 14 regex replacement patterns
6. **Validate & Classify** → Split into `_resolved.txt` (clean) and `_fallado.txt` (has unmapped IDs)
7. **Create ZIP archives** → Package resolved and failed files separately
8. **Persist Logs** → Save structured logs to database for debugging
9. **Auto-Export Debug JSON** → Automatically export comprehensive debug info to `storage/debug/` (runs on both success and failure)

### Key Modules

**parser.py** - GGPoker hand history parser
- Extracts hand ID, timestamp, seats, positions, board cards, actions
- Supports both cash games and tournaments
- Detects 3-max vs 6-max table formats

**ocr.py** - Google Gemini Vision OCR
- **REQUIRED MODEL**: `models/gemini-2.5-flash-image` (tested at 98% confidence, optimal for vision tasks)
- 78-line optimized prompt for poker screenshot analysis
- Extracts: hand ID, player names, hero cards, board cards, stacks, positions
- Async processing with semaphore-based rate limiting (10 concurrent requests)
- Returns `ScreenshotAnalysis` dataclass

**matcher.py** - Intelligent hand-to-screenshot matching
- **PRIMARY**: Hand ID matching from OCR (99.9% accuracy) - `screenshot.hand_id == hand.hand_id`
- **FALLBACK**: 100-point scoring system (hero cards 40pts, board 30pts, timestamp 20pts, position 15pts, names 10pts, stack 5pts)
- Prevents duplicate matches with `matched_screenshots` tracking
- Returns `HandMatch` objects with auto-generated seat mappings

**writer.py** - Output generation with PokerTracker validation
- **14 regex patterns** for name replacement (most specific first):
  1. Seat lines: `Seat 1: PlayerID ($100 in chips)`
  2. Blind posts: `PlayerID: posts small blind $0.1` (MUST come before general actions)
  3. Actions with amounts: `calls/bets/raises $10`
  4. Actions without amounts: `folds/checks`
  5. All-in actions: `raises $10 to $20 and is all-in`
  6-14. Dealt to, collected, shows, mucks, doesn't show, summary, uncalled bet, EV cashout
- **CRITICAL**: Never replaces "Hero" (PokerTracker requirement)
- **10 validations**: Hero preservation, line count, hand ID, timestamp, currency symbols, summary section, table info, seat count, chip format, unmapped IDs detection

**database.py** - SQLite persistence
- **jobs** table: Tracks status (pending/processing/completed/failed), file counts, statistics, processing time
- **files** table: Uploaded TXT and screenshot references
- **results** table: Final outputs, mappings JSON, stats JSON
- **screenshot_results** table: Per-screenshot OCR success/failure, match counts, errors (diagnostic granularity)
- **logs** table: Structured logs with job_id, level, timestamp, message, and extra_data (JSON)

**logger.py** - Structured logging system
- Job-specific loggers with console output and database persistence
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Buffered logging with `flush_to_db()` for batch persistence
- Colored console output for different log levels

### File Classification System (CRITICAL - Never Lose Hands)

ALL hands from input TXT files are included in outputs. Files are classified per-table:

- **`_resolved.txt`** → 100% de-anonymized, ready for PokerTracker import (packaged in `resolved_hands.zip`)
- **`_fallado.txt`** → Contains unmapped anonymous IDs, needs more screenshots (packaged in `fallidos.zip`)

The system tracks `unmapped_ids` list per file and provides transparent reporting in UI.

### API Endpoints (main.py:84-738)

**Core Workflow:**
- `POST /api/upload` → Upload TXT files + screenshots, creates job
- `POST /api/process/{job_id}` → Start background processing (supports reprocessing completed/failed jobs)
- `GET /api/status/{job_id}` → Real-time status with OCR progress (ocr_processed/ocr_total), statistics, successful_files, failed_files
- `GET /api/download/{job_id}` → Download `resolved_hands.zip` (clean files)
- `GET /api/download-fallidos/{job_id}` → Download `fallidos.zip` (files with unmapped IDs)
- `GET /api/jobs` → List all jobs
- `DELETE /api/job/{job_id}` → Delete job and files

**Debugging & Diagnostics:**
- `GET /api/job/{job_id}/screenshots` → Detailed screenshot results (OCR errors, match counts)
- `GET /api/debug/{job_id}` → Comprehensive debug information (job, files, results, logs)
- `POST /api/debug/{job_id}/export` → Export debug info to JSON file in `storage/debug/`
- `POST /api/debug/{job_id}/generate-prompt` → Generate AI-powered debugging prompt using Gemini 2.5 Flash (analyzes job metrics, errors, and provides actionable debugging steps)

**Frontend:**
- `GET /` → Redirect to `/app`
- `GET /app` → Serve main application page (Jinja2 template)

## Critical Implementation Rules

### Name Replacement Order (writer.py:174-282)
Regex patterns MUST be applied in this order to avoid ID conflicts:
1. Blind posts BEFORE general actions (prevents `: posts` from matching other patterns)
2. Actions with amounts BEFORE actions without amounts
3. Most specific patterns (with lookaheads/negations) first

### Hero Protection (writer.py:168-169)
```python
if anon_id.lower() == 'hero':
    continue  # NEVER replace Hero - PokerTracker requirement
```

### Unmapped ID Detection (writer.py:78-98, 373-395)
- Pattern: `\b[a-f0-9]{6,8}\b` (6-8 character hex strings)
- Must verify context: `^{anon_id}:|Seat \d+: {anon_id}` (not timestamps/cards/hand IDs)
- Presence of unmapped IDs classifies file as `_fallado.txt`

### OCR Parallelization (main.py:296-357)
```python
semaphore = asyncio.Semaphore(10)  # Max 10 concurrent Gemini API requests
async def process_single_screenshot(screenshot_file):
    async with semaphore:
        result = await ocr_screenshot(...)
```
Prevents API rate limit violations while maximizing throughput.

### Hand ID Matching Strategy (matcher.py:11-162)
1. **Normalize Hand IDs** → Remove prefixes like "SG", "HH", "MT", "TT" (handles OCR/parser differences)
2. **PRIMARY**: Check `_normalize_hand_id(screenshot.hand_id) == _normalize_hand_id(hand.hand_id)` (OCR extracted) → 100 points
3. **LEGACY**: Check `hand.hand_id in screenshot.screenshot_id` (filename) → 100 points
4. **FALLBACK**: Multi-criteria scoring → 0-100 points (hero cards 40pts, board 30pts, hero position 15pts, player names 10pts, stack 5pts)
5. **Duplicate Prevention**: `_build_seat_mapping()` validates mappings and returns empty dict if duplicate names detected within same hand

## Common Development Patterns

### Adding a new regex pattern to writer.py
1. Insert in correct order (most specific first)
2. Use `re.escape(anon_id)` to prevent regex injection
3. Use `rf'...'` for raw f-strings with regex
4. Test with `re.MULTILINE` flag if matching line starts (`^`)
5. Add negative lookaheads to prevent over-matching

### Modifying OCR prompt (ocr.py:46-117)
- **ALWAYS use model**: `models/gemini-2.5-flash-image` (do not change - tested and verified)
- Prompt is structured: CRITICAL INSTRUCTIONS → HAND ID EXTRACTION → CARD FORMAT → OUTPUT FORMAT → VALIDATION RULES
- Hand ID is MOST IMPORTANT for matching accuracy
- JSON output must match `ScreenshotAnalysis` dataclass structure
- Include validation rules to guide model

### Database migrations (database.py:95-123)
- Check if column exists: `PRAGMA table_info(table_name)`
- Add with `ALTER TABLE` if missing
- Default values prevent breaking existing rows

## Storage Structure

```
storage/
├── uploads/{job_id}/
│   ├── txt/*.txt           # Original hand history files
│   └── screenshots/*.png   # PokerCraft screenshots
├── outputs/{job_id}/
│   ├── {table}_resolved.txt     # Clean files (all IDs mapped)
│   ├── {table}_fallado.txt      # Failed files (unmapped IDs)
│   ├── resolved_hands.zip       # ZIP of all _resolved.txt files
│   └── fallidos.zip             # ZIP of all _fallado.txt files
└── debug/
    └── debug_job_{id}_{timestamp}.json  # Exported debug info
```

**Database:** `ggrevealer.db` (SQLite) - Contains jobs, files, results, screenshot_results, and logs tables

## PokerTracker Compatibility

Hand histories MUST pass these validations (writer.py:287-404):
1. Hero count unchanged (CRITICAL)
2. Line count within ±2 variance
3. Hand ID unchanged
4. Timestamp unchanged
5. No double currency symbols (`$$`)
6. Summary section preserved
7. Table name unchanged
8. Seat count match
9. Chip value count preserved
10. No unmapped anonymous IDs (6-8 char hex)

Violation of validation #1 or #10 will cause PokerTracker to REJECT the hand history file.

## Debugging Tips

### AI-Powered Debugging (Recommended)

**IMPORTANT**: After every job completes (success or failure), a debug JSON is **automatically exported** to `storage/debug/debug_job_{id}_{timestamp}.json`

```bash
# Use the built-in AI debugging endpoint
curl -X POST http://localhost:5000/api/debug/{job_id}/generate-prompt
```

This generates a Claude Code debugging prompt that:
- **References the auto-exported debug JSON file** (instructs Claude Code to read it first)
- Analyzes job metrics (match rate, OCR success rate, etc.)
- Identifies specific problems (matching issues, OCR failures, etc.)
- Suggests concrete files and functions to review
- Provides actionable debugging steps

**UI Features**:
- Debug prompts are shown automatically in the frontend when errors occur
- **"Regenerate" button**: Retry prompt generation if it comes empty or fails
- **"Copy" button**: Copy the generated prompt to clipboard for use in Claude Code
- Auto-exported JSON path is included in all prompts for easy reference

### Manual Debugging

#### Check OCR results
```python
# In ocr.py, print raw Gemini response
print(f"Raw response: {response.text}")
```

#### Check matching scores
```python
# In matcher.py, already logs to console:
print(f"✅ Hand ID match: {hand.hand_id} ↔ {screenshot.screenshot_id}")
print(f"⚠️  Fallback match: {hand.hand_id} ↔ {screenshot.screenshot_id} (score: {best_score:.1f})")
```

#### Inspect unmapped IDs
```python
# Check writer.py validation output
unmapped_ids = detect_unmapped_ids_in_text(final_txt)
print(f"Unmapped: {unmapped_ids}")
```

#### Review job processing logs
Server console shows detailed pipeline logs:
```
[JOB {id}] [INFO] Starting processing...
[JOB {id}] [INFO] Parsed {n} hands
[JOB {id}] [INFO] OCR completed: {n} screenshots analyzed
[JOB {id}] [INFO] Found {n} matches
[JOB {id}] [WARNING] Unmapped seats: Seat 2 (abc123)
```

Logs are also persisted to database and can be retrieved via:
- `GET /api/debug/{job_id}` → Returns logs with filtering by level
- Database: `SELECT * FROM logs WHERE job_id = ? ORDER BY timestamp DESC`

#### Export full debug report
**Note**: Debug JSON is **automatically exported** after every job completion.

Manual export (if needed):
```bash
# Export complete debug info to storage/debug/
curl -X POST http://localhost:5000/api/debug/{job_id}/export
```
Includes: job details, files, results, screenshot analysis, logs, and statistics

The auto-exported file is named: `debug_job_{id}_{timestamp}.json`

## Critical Bug Fixes & Implementation Notes

### Octal Interpretation Bug in Regex Replacements (Oct 2025 - FIXED)
**Problem**: PokerTracker rejected ~80% of hands when player names started with digits (e.g., "50Zoos", "9BetKing"). Seat lines were corrupted.

**Root Cause**: Python's `re.sub()` interpreted escape sequences like `\150` as octal codes when using f-string replacements like `rf'\1{real_name}\2'`. Example:
- Input: `Seat 3: 9d830e65 (625 in chips)`
- Expected: `Seat 3: 50Zoos (625 in chips)` ✅
- Actual: `hZoos (625 in chips)` ❌ (because `\150` octal = 'h')

**Solution**: Changed all affected regex patterns in `writer.py` to use explicit group references: `r'\g<1>' + real_name + r'\g<2>'`

**Affected Patterns** (5 of 14 total):
1. Seat lines: `Seat X: PlayerID (stack in chips)`
2. Dealt to (no cards): `Dealt to PlayerID`
3. Dealt to (with cards): `Dealt to PlayerID [cards]`
4. Summary lines: `Seat X: PlayerID (position)`
5. Uncalled bet: `returned to PlayerID`

### Duplicate Player Name Mapping Bug (Oct 2025 - FIXED)
**Problem**: Multiple anonymized IDs mapped to same real name within a single hand (e.g., "TuichAAreko" appearing in multiple seats), causing PokerTracker rejections.

**Root Cause**: The matcher sometimes assigned screenshots to incorrect hands, and the mapping creation logic didn't verify if a `resolved_name` was already used for a different player within the same hand.

**Solution**: Enhanced `_build_seat_mapping()` in `matcher.py` to:
1. Track `used_names` while building mappings for each hand
2. Reject matches that create duplicate names within the same hand (return empty mapping)
3. Allow same player across different hands/tables (per-hand scoping)

**Important Note**: Hero position validation was NOT added because PokerCraft always displays Hero at bottom visually, regardless of actual seat number in hand history.

**Impact**: Prevents duplicate player names by rejecting incorrect screenshot matches at the source. Rejected matches are logged with warnings including hand_id.

### PokerCraft Visual Position Mapping Bug (Oct 2025 - FIXED) ⭐
**Problem**: Only 1 out of 5 tables fully de-anonymized. The other 4 had 1 unmapped player each despite having screenshots. Match rate appeared as 3.4% (5 matched hands / 147 total hands), suggesting a data coverage problem, but the real issue was incomplete name extraction.

**Example from Job 3 - Table 12253:**
- Hand history: Seat 1: `e3efcaed`, Seat 2: `5641b4a0`, Seat 3: `Hero`
- Screenshot extracted: All 3 players (Hero, v1[nn]1, Gyodong22)
- **OLD**: Only 2 players mapped (Hero → TuichAAreko, 5641b4a0 → v1[nn]1)
- **NEW**: All 3 players mapped (e3efcaed → Gyodong22 included) ✅

**Root Cause**: PokerCraft reorganizes visual positions with Hero always at position 1, regardless of real seat number. The old `_build_seat_mapping()` function used direct position matching (`screenshot.position == seat.seat_number`), which failed when visual positions didn't match real seat numbers.

**Solution**: Implemented counter-clockwise seat calculation in `matcher.py:260-341`:
1. Find Hero's real seat number in hand history (e.g., Seat 3)
2. Calculate real seat for each visual position using formula: `real_seat = hero_seat - (visual_position - 1)` with wrap-around
3. Map ALL players from screenshot (not just those in the matched hand)
4. Extract names for every seat position at the table

**Calculation Example (Hero at Seat 3 in 3-max):**
- Visual Position 1 → Seat 3 (Hero)
- Visual Position 2 → Seat 2 (counter-clockwise from Hero)
- Visual Position 3 → Seat 1 (counter-clockwise from Seat 2)

**Impact**:
- **Before**: 7 name mappings, 4 unmapped players, 1 resolved file, 4 failed files
- **After**: 11 name mappings (+57%), 0 unmapped players (-100%), 5 resolved files (+400%), 0 failed files ✅
- Effective match rate increased from 3.4% to ~100% for tables with screenshots
- Each screenshot now provides ALL player names at the table, not just the matched hand's players

**Key Insight**: The screenshots were always sufficient to de-anonymize entire tables. The issue was that the system only used player names that appeared in the specific matched hand, ignoring other players visible in the screenshot. Now it extracts ALL visible players and applies them to ALL hands at that table.

## Recent Features & Enhancements

### Hand ID Normalization (Oct 2025)
**Feature**: Automatic normalization of hand IDs to handle OCR/parser prefix differences
- Strips prefixes like "SG", "HH", "MT", "TT" before comparison
- Significantly improves matching accuracy when OCR omits hand ID prefixes
- Location: `matcher.py:11-30` (`_normalize_hand_id()`)

### Structured Logging System (Oct 2025)
**Feature**: Comprehensive logging with database persistence and colored console output
- Job-specific loggers with buffered writes
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- Persistent storage in SQLite for post-mortem analysis
- Location: `logger.py`, `database.py` (logs table)

### AI-Powered Debugging (Oct 2025)
**Feature**: Gemini 2.5 Flash-powered debugging prompt generation
- Analyzes job metrics, error logs, and screenshot failures
- Generates actionable debugging prompts for Claude Code
- Identifies specific problems (low match rate, OCR failures, etc.)
- Endpoint: `POST /api/debug/{job_id}/generate-prompt`
- Location: `main.py:418-717`

### Job Reprocessing (Oct 2025)
**Feature**: Ability to reprocess completed or failed jobs
- Clears previous results from database and filesystem
- Useful for testing fixes without re-uploading files
- Endpoint: `POST /api/process/{job_id}` (detects and handles reprocessing)
- Location: `main.py:121-148`

### Automatic Debug JSON Export (Oct 2025) 🆕
**Feature**: Automatic export of comprehensive debug information after every job
- **Triggers**: Runs automatically at end of `run_processing_pipeline()` (both success and failure)
- **Location**: Exports to `storage/debug/debug_job_{id}_{timestamp}.json`
- **Contents**: Complete job info, logs, screenshot results, statistics, errors
- **Integration**: `_export_debug_json()` helper function for reusability
- **Logging**: Confirms export with filepath in console and database logs
- **Implementation**: `main.py:335-415` (helper), `main.py:1194-1201` (success), `main.py:1215-1222` (failure)

### JSON-Referenced Debug Prompts (Oct 2025) 🆕
**Feature**: AI-generated prompts include explicit reference to debug JSON file
- **Gemini Integration**: Instructs Gemini AI to tell Claude Code to read the JSON first
- **Fallback Support**: Even fallback prompts include JSON reference section
- **User Benefit**: Claude Code gets full context from JSON before debugging
- **Format**: Prompts start with "Lee el archivo {debug_json_path} para obtener información completa"
- **Auto-Export**: JSON is exported before prompt generation to ensure it exists
- **Implementation**: `main.py:570-576` (Gemini instruction), `main.py:706-720` (fallback)

### UI Prompt Regeneration (Oct 2025) 🆕
**Feature**: "Regenerate" button for retrying failed or empty prompt generation
- **UI Elements**: Blue "Regenerar" button next to "Copiar" in both error sections
- **Functionality**: Calls `/api/debug/{job_id}/generate-prompt` again on click
- **Visual Feedback**: Shows spinning icon with "Regenerando..." text during request
- **Error Handling**: Button stays enabled even after errors to allow unlimited retries
- **Use Cases**: Empty prompts, Gemini API timeouts, transient errors
- **Implementation**: `templates/index.html:186-188,280-282`, `static/js/app.js:643-647,721-736`

### Copy Prompt Button Fix (Oct 2025) 🆕
**Feature**: Reliable prompt copying with data attribute persistence
- **Problem Fixed**: Previous implementation lost prompt text in JavaScript scope
- **Solution**: Store prompt in button's `data-prompt-text` attribute
- **Validation**: Checks for empty prompts and throws error to trigger regeneration
- **Feedback**: Button changes to "✓ Copiado" in green for 2 seconds
- **Logging**: Console shows prompt length for debugging
- **Implementation**: `static/js/app.js:598-602,701-705`

## Known Limitations

1. **GEMINI_API_KEY required** - OCR returns mock data if not configured
2. **Rate limits** - Semaphore set to 10 concurrent requests (adjust if needed)
3. **Hero protection** - "Hero" is NEVER replaced (PokerTracker requirement, not a bug)
4. **Hand count preservation** - All hands from input appear in output (matched or unmatched)
5. **Table name extraction** - Uses regex on `Table 'Name'` format; fails if format differs
6. **Hero position validation disabled** - PokerCraft's visual layout doesn't match seat numbers
7. **Port discrepancy** - `main.py` uses port 5000, `restart.sh` uses port 8000 (update restart.sh if needed)
