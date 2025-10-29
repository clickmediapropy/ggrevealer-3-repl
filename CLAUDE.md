# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GGRevealer** is a FastAPI web application that de-anonymizes GGPoker hand history files by matching them with PokerCraft screenshots using Google Gemini Vision API for OCR. The system outputs PokerTracker-compatible hand history files with real player names.

**Tech Stack**: Python 3.11+ • FastAPI • SQLite • Google Gemini 2.0 Flash Exp (Dual OCR) • Vanilla JS + Bootstrap 5

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

### Core Pipeline (main.py `run_processing_pipeline`)

**MAJOR ARCHITECTURAL CHANGE (Sept 2025)**: Moved from single complex OCR to dual sequential OCR with role-based mapping and table-wide aggregation.

**Coverage Improvement**: 3-5% → 90-95% (+1800%)

#### Phase 1: Parse Hand Histories
1. **Parse TXT files** → Extract hand histories using `GGPokerParser.parse_file()`
   - Extracts hand ID, timestamp, seats, positions, board cards, actions
   - Identifies button, small blind, big blind roles from action text

#### Phase 2: OCR1 - Hand ID Extraction
2. **OCR1 - Hand ID Extraction** → Ultra-simple OCR on ALL screenshots (99.9% accuracy expected)
   - Model: `gemini-2.0-flash-exp`
   - Extracts ONLY Hand ID (single field, minimal prompt)
   - Parallel async processing (10 concurrent) with `ocr_hand_id()`
   - Stores results in `screenshot_results.ocr1_hand_id`

#### Phase 3: Match by Hand ID
3. **Match by Hand ID** → Primary key matching with validation gates
   - **PRIMARY**: Hand ID matching (OCR1 extracted) - 99.9% accuracy
   - **FALLBACK**: 100-point scoring system (hero cards 40pts, board 30pts, etc.)
   - **VALIDATION GATES**: Player count, hero stack ±25%, stack alignment ≥50%
   - Tracks matched vs unmatched screenshots

#### Phase 4: Retry Failed OCR1
4. **Retry OCR1** → One retry attempt for failed screenshots
   - Retries screenshots with `ocr1_success = 0` or `ocr1_hand_id IS NULL`
   - 1-second delay between attempts
   - Tracks retry count in `screenshot_results.ocr1_retry_count`

#### Phase 5: Discard Unmatched Screenshots
5. **Discard Unmatched** → Discard screenshots that failed to match any hand
   - Saves API costs by not running OCR2 on unmatched screenshots
   - Logs discard reason in `screenshot_results.discard_reason`
   - ~50% cost savings (OCR2 only on matched screenshots)

#### Phase 6: OCR2 - Player Details Extraction
6. **OCR2 - Player Details** → Extract player names and role indicators (MATCHED screenshots only)
   - Model: `gemini-2.0-flash-exp`
   - Extracts: Player names with role indicators (D/SB/BB), stacks, positions
   - Parallel async processing (10 concurrent) with `ocr_player_details()`
   - Stores results in `screenshot_results.ocr2_data` (JSON)

#### Phase 7: Generate Mappings (Role-Based + Table-Wide Aggregation)
7. **Generate Mappings** → Role-based mapping per hand + table-wide aggregation
   - **Per-Hand Mapping**: Use role indicators (D/SB/BB) to match players (99% accuracy)
   - **Fallback**: Counter-clockwise calculation if <2 roles available
   - **Table Grouping**: Group all hands by table name
   - **Table Aggregation**: Aggregate mappings from ALL matched screenshots for each table
   - **Apply to All Hands**: One screenshot can de-anonymize entire table session (50+ hands)
   - Duplicate name detection prevents incorrect mappings

#### Phase 8-10: Output Generation & Validation
8. **Write Outputs** → Generate per-table TXT files with 14 regex replacement patterns
9. **Validate & Classify** → Split into `_resolved.txt` (clean) and `_fallado.txt` (has unmapped IDs)
10. **Create ZIP archives** → Package resolved and failed files separately
11. **Calculate Metrics** → Comprehensive 30+ metrics across 5 categories (hands, players, tables, screenshots, mappings)
12. **Persist Logs** → Save structured logs to database for debugging
13. **Auto-Export Debug JSON** → Automatically export comprehensive debug info to `storage/debug/`

### Key Modules

**parser.py** - GGPoker hand history parser
- Extracts hand ID, timestamp, seats, positions, board cards, actions
- Supports both cash games and tournaments
- Detects 3-max vs 6-max table formats
- **NEW**: `find_seat_by_role()` - Finds seat by role (button, small blind, big blind) using regex on action text

**ocr.py** - Dual OCR System (Sept 2025 Redesign)

**CRITICAL CHANGE**: Split into two sequential OCR phases for 99.9% accuracy and 50% cost savings

**Phase 1 - Hand ID Extraction (OCR1)**:
- **Model**: `gemini-2.0-flash-exp` (ultra-fast, cost-effective)
- **Function**: `ocr_hand_id(screenshot_path, api_key)` - Ultra-simple OCR
- **Extracts**: ONLY Hand ID (single field)
- **Accuracy**: 99.9% (minimal prompt, focused task)
- **Runs on**: ALL screenshots
- **Returns**: `(success: bool, hand_id: str|None, error: str|None)`
- **Retry Logic**: `ocr_hand_id_with_retry()` - Retries once with 1s delay for transient failures

**Phase 2 - Player Details Extraction (OCR2)**:
- **Model**: `gemini-2.0-flash-exp`
- **Function**: `ocr_player_details(screenshot_path, api_key)` - Detailed extraction
- **Extracts**: Player names with role indicators (D/SB/BB), stacks, positions
- **Accuracy**: 99% for role-based mapping
- **Runs on**: ONLY matched screenshots (50% cost savings)
- **Returns**: `(success: bool, ocr_data: dict|None, error: str|None)`
- **Key Feature**: Role indicators (D = Dealer/Button, SB = Small Blind, BB = Big Blind)

**Async Processing**:
- Semaphore-based rate limiting (10 concurrent requests)
- Parallel batch processing for optimal throughput

**Location**: `ocr.py:46-210` (OCR1), `ocr.py:212-380` (OCR2)

**matcher.py** - Intelligent hand-to-screenshot matching + Role-Based Mapping (Sept 2025 Redesign)

**Hand-to-Screenshot Matching**:
- **PRIMARY**: Hand ID matching from OCR1 (99.9% accuracy) - `screenshot.hand_id == hand.hand_id`
- **FALLBACK**: 100-point scoring system (hero cards 40pts, board 30pts, timestamp 20pts, position 15pts, names 10pts, stack 5pts)
- **VALIDATION GATES**: Pre-match quality checks prevent incorrect matches (player count, hero stack ±25%, general stack alignment ≥50%)
- **Confidence threshold**: 70.0 for fallback matches
- Prevents duplicate matches with `matched_screenshots` tracking
- Returns `HandMatch` objects

**Role-Based Mapping (NEW - 99% Accuracy)**:
- **Function**: `_build_seat_mapping_by_roles(screenshot, hand, logger)` - Role-based player mapping
- **Method**: Extract role indicators (D/SB/BB) from OCR2 → Use `find_seat_by_role()` from parser → Direct 1:1 mapping
- **Accuracy**: 99% (eliminates counter-clockwise calculation errors)
- **Fallback**: Counter-clockwise calculation if <2 roles available (legacy method)
- **Validation**: Rejects matches with duplicate player names (prevents incorrect mappings)
- **Returns**: `Dict[anonymized_id, real_name]` or empty dict on conflicts
- **Location**: `matcher.py:441-573`

**writer.py** - Output generation with PokerTracker validation
- **14 regex patterns** for name replacement (most specific first):
  1. Seat lines: `Seat 1: PlayerID ($100 in chips)`
  2. Blind posts: `PlayerID: posts small blind $0.1` (MUST come before general actions)
  3. Actions with amounts: `calls/bets/raises $10`
  4. Actions without amounts: `folds/checks`
  5. All-in actions: `raises $10 to $20 and is all-in`
  6-14. Dealt to, collected, shows, mucks, doesn't show, summary, uncalled bet, EV cashout
- **Hero Replacement**: Hero IS replaced with real player name extracted from OCR (e.g., "Hero" → "TuichAAreko")
- **10 validations**: Hero count unchanged, line count, hand ID, timestamp, currency symbols, summary section, table info, seat count, chip format, unmapped IDs detection

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

### Hero Replacement Behavior
The system DOES replace "Hero" with the real player name extracted from OCR screenshots. The matcher creates a mapping entry `"Hero" → "Real Name"` (e.g., "Hero" → "TuichAAreko"), and the writer applies all 14 regex patterns to this mapping just like any other anonymized ID. This allows PokerTracker to import hands with actual player names instead of the generic "Hero" identifier.

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

### Hand ID Matching Strategy (matcher.py:11-240)
1. **Normalize Hand IDs** → Remove prefixes like "SG", "HH", "MT", "TT" (handles OCR/parser differences)
2. **PRIMARY**: Check `_normalize_hand_id(screenshot.hand_id) == _normalize_hand_id(hand.hand_id)` (OCR extracted) → 100 points
3. **LEGACY**: Check `hand.hand_id in screenshot.screenshot_id` (filename) → 100 points
4. **FALLBACK**: Multi-criteria scoring → 0-100 points (hero cards 40pts, board 30pts, hero position 15pts, player names 10pts, stack 5pts), threshold: 70.0
5. **VALIDATION GATES** (applied BEFORE accepting any match):
   - Player count match (hand seats vs screenshot players)
   - Hero stack similarity (±25% tolerance, accounts for blinds/antes)
   - General stack alignment (≥50% of stacks within ±30%)
6. **Duplicate Prevention**: `_build_seat_mapping()` validates mappings and returns empty dict if duplicate names detected within same hand

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
1. Hero mention count unchanged (CRITICAL) - The number of times the hero player is mentioned must remain the same, even though "Hero" is replaced with real name
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

### Match Quality Validation Enhancement (Oct 2025 - FIXED) 🆕
**Problem**: Analysis of Job #26 revealed ~21% of screenshots (57 of 265) were matched to incorrect hands, resulting in failed mappings and 58 tables with unmapped IDs. System matched 265 screenshots but only 208 tables (78.5%) were fully de-anonymized.

**Root Cause Analysis**:
- **Hand ID matches** (197): Generally reliable when OCR extracts Hand ID correctly
- **Filename matches** (5): Reliable
- **Fallback matches** (63): ~90% of incorrect matches originated here due to weak validation
  - Screenshots matched to hands with different player counts (e.g., 2-player hand → 3-player screenshot)
  - Hero stack mismatches (e.g., $260 in hand vs $100 in screenshot)
  - Screenshots from completely different hands accepted based on superficial similarities

**Evidence from Logs**:
```
Hand: 2 players (Hero + 869d60cc)
Screenshot: 3 players (TheKingOfVe..., TuichAAreko, Rareseanu)
Result: Player count mismatch → match accepted → mapping fails
```

**Solution**: Added `validate_match_quality()` function in `matcher.py:32-88` with three validation gates applied BEFORE accepting any match:

1. **Player Count Validation**: Hand and screenshot must have same number of players
2. **Hero Stack Validation**: Hero stack must match within ±25% tolerance (accounts for blinds/antes)
3. **Stack Alignment Validation**: At least 50% of player stacks must align within ±30% tolerance

**Additional Changes**:
- Increased fallback matching confidence threshold from 50.0 to 70.0 points
- Enhanced logging to show rejection reasons for debugging
- Validation applied to all three matching paths: Hand ID, Filename, and Fallback

**Expected Impact**:
- Reduce incorrect matches from ~57 (21%) to <10 (4%)
- Improve fully de-anonymized table rate from 78.5% to >95%
- Prevent mapping failures caused by mismatched hands
- Better diagnostic logging for rejected matches

**Implementation**: `matcher.py:32-88` (`validate_match_quality()`), applied in `matcher.py:90-240` (`find_best_matches()`)

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

### OCR Model Upgrade (Oct 2025) 🆕
**Lesson Learned**: Upgraded from `gemini-2.0-flash-exp` to `gemini-2.5-flash-image` for improved visual recognition accuracy. The newer model provides better handling of poker table layouts and role indicator detection, particularly for identifying the yellow/white dealer button and player positions in PokerCraft screenshots. Implementation: `ocr.py:39,128` (both OCR1 and OCR2 phases now use gemini-2.5-flash-image).

### Dealer-First Role Mapping (Oct 2025) 🆕
**Problem Solved**: OCR2 previously extracted `positions` as null and sometimes assigned the same player to multiple roles (SB/BB), causing TypeError in counter-clockwise mapping and 20% mapping failures. Root cause was relying on SB/BB badges which aren't always visible, and reading from action history panel instead of visual table indicators. **Solution**: Implemented dealer-first approach where OCR only identifies the highly-visible yellow/white dealer button, then automatically calculates SB/BB positions using clockwise formula: `SB = (dealer_index + 1) % total_players`, `BB = (dealer_index + 2) % total_players`. This increased Table 12614 mapping from 0/3 to 3/3 players and Job 22 resolution rate from 80% to 100%. Implementation: `ocr.py:134-192` (prompt enhancements), `main.py:2244-2266` (auto-calculation logic).

### Duplicate Role Prevention (Oct 2025) 🆕
**Problem Solved**: OCR2 extracted the same player name for both SB and BB roles (e.g., "50Zoos" for both), which correctly triggered duplicate detection but prevented valid mapping. This occurred when OCR read from the action history panel at the bottom of screenshots instead of visual role indicators on the poker table itself. **Solution**: Enhanced OCR2 prompt with explicit instructions to extract role indicators ONLY from the poker table visual layout (player avatars with D/SB/BB badges) and ignore the action history panel. Added concrete examples showing correct vs incorrect role extraction patterns. This eliminated all duplicate role assignments and improved mapping reliability. Implementation: `ocr.py:145-163` (enhanced role extraction instructions).

## PT4 Validation System (Oct 2025) 🆕

**Feature**: Comprehensive PokerTracker 4 validation system with 12 critical validations

GGRevealer now includes a complete validation system that replicates the exact validations that PokerTracker 4 (PT4) performs on hand histories. This helps identify why PT4 might reject hands (common 78% rejection rate for GGPoker files).

### Architecture

**Core Module**: `validator.py` (~1000 lines)
- **Class**: `GGPokerHandHistoryValidator`
- **Modes**: Strict (rejects like PT4) or Permissive (only logs)
- **Result Types**: SUCCESS, WARNING, ERROR
- **Severity Levels**: LOW, MEDIUM, HIGH, CRITICAL

### The 12 Critical Validations

#### 1. Pot Size Validation (MOST CRITICAL - 40% of failures)
**Validates**: `Total pot = Sum(all bets) - Rake - Jackpot fees`

**Common failure**: Cash Drop (1BB fee on pots > 30BB) not accounted for in hand history

**Error message**: `Invalid pot size (X vs pot:Y rake:Z jpt:W)`

**Implementation**: `validator.py:184-258` (`validate_pot_size()`)

#### 2. Blind Consistency
**Validates**: Stated blinds (header) = Posted blinds (actions)

**PT4 version**: v4.15.35+ made this validation stricter

**Error message**: `Stated blinds (X/Y) != Posted blinds (A/B)`

**Implementation**: `validator.py:260-318` (`validate_blinds()`)

#### 3. Stack Sizes
**Validates**: All stacks > $0

**Error message**: `Players with invalid stacks`

**Implementation**: `validator.py:320-352` (`validate_stack_sizes()`)

#### 4. Hand Metadata
**Validates**: Hand ID format (RC/OM/TM/HD prefix + digits) and timestamp format (YYYY/MM/DD HH:MM:SS)

**Known prefixes**: RC (Rush & Cash), OM (Omaha), TM/HD (Tournaments), MT/SG/TT (other formats)

**Implementation**: `validator.py:354-417` (`validate_hand_metadata()`)

#### 5. Player Identifiers
**Validates**: Players have correct GGPoker format (Hero or 6-8 char hex IDs)

**Format**: `Hero` or `[0-9a-f]{6,8}` (e.g., "478db80b", "5a3f9e2c")

**Implementation**: `validator.py:419-480` (`validate_player_identifiers()`)

#### 6. Card Validation
**Validates**: No duplicate cards, valid format `[2-9TJQKA][hdcs]`

**Error message**: `Duplicate cards in deck: [...]`

**Implementation**: `validator.py:482-542` (`validate_cards()`)

#### 7. Game Type Support
**Validates**: Game type is supported by PT4

**Supported**: Hold'em NL/PL, Omaha PL, PLO-5, PLO-6

**NOT Supported**: Run It Three Times, Mixed Games (Razz, Stud, Draw)

**Critical rejection**: Run It Three Times (hands with `*** THIRD FLOP ***`)

**Implementation**: `validator.py:544-603` (`validate_game_type()`)

#### 8. Action Sequence
**Validates**: Actions follow logical poker rules (e.g., "calls" requires prior bet/raise)

**Error message**: `Call action without prior bet/raise on STREET`

**Implementation**: `validator.py:605-648` (`validate_action_sequence()`)

#### 9. Stack Consistency
**Validates**: Final stacks = Initial stacks ± actions

**Status**: Placeholder (complex validation, requires full action tracking)

**Implementation**: `validator.py:650-665` (`validate_stack_consistency()`)

#### 10. Split Pots
**Validates**: Side pots and multiple winners add up correctly

**Format**: `Total pot X | Main pot Y. Side pot Z.`

**Validation**: `Main pot + Side pot(s) = Total pot`

**Implementation**: `validator.py:667-726` (`validate_split_pots()`)

#### 11. EV Cashout Detection (GGPoker Exclusive)
**Detects**: `Chooses to EV Cashout` in hand history

**PT4 Bug**: Shows full pot as won instead of cashout amount (incorrect winnings calculation)

**Severity**: HIGH (PT4 imports but calculates wrong statistics)

**Implementation**: `validator.py:728-763` (`detect_ev_cashout()`)

#### 12. All-in with Straddle
**Detects**: Edge case of all-in hands with straddles

**PT4 Bug History**: Fixed in v4.18.13 (older versions had incorrect pot calculations)

**Severity**: MEDIUM (recommend PT4 v4.18.13+)

**Implementation**: `validator.py:765-788` (`validate_all_in_with_straddle()`)

### API Endpoint

**Endpoint**: `POST /api/validate`

**Purpose**: Validate hand history files independently (no processing)

**Request**: Multipart file upload (TXT file)

**Response**:
```json
{
  "success": true,
  "filename": "hand.txt",
  "valid": true,
  "pt4_would_reject": false,
  "pt4_error_message": null,
  "errors": [],
  "warnings": [],
  "validation_summary": {
    "total_validations": 12,
    "errors": 0,
    "warnings": 1,
    "critical": 0,
    "would_reject": false,
    "results": [...]
  }
}
```

**Implementation**: `main.py:1152-1227` (`validate_hand_history()`)

### Usage Examples

#### Via API (curl)
```bash
# Validate a single hand history file
curl -X POST http://localhost:5000/api/validate \
  -F "file=@hand_history.txt"
```

#### In Python
```python
from validator import GGPokerHandHistoryValidator

# Create validator in permissive mode (only logs)
validator = GGPokerHandHistoryValidator(strict_mode=False)

# Read hand history
with open('hand.txt', 'r') as f:
    hand_history = f.read()

# Run all validations
results = validator.validate(hand_history)

# Check if PT4 would reject
if validator.should_reject_hand():
    print(f"❌ PT4 would reject: {validator.get_pt4_error_message()}")
else:
    print("✅ PT4 would accept")

# Get detailed summary
summary = validator.get_validation_summary()
print(f"Errors: {summary['errors']}, Warnings: {summary['warnings']}")
```

### Error Severity Levels

| Severity | PT4 Behavior | Example Errors |
|----------|--------------|----------------|
| **CRITICAL** | Hand rejected | Invalid pot size, duplicate cards, RIT3, negative stacks |
| **HIGH** | Warning shown, might reject | Missing blinds, EV Cashout detected, unsupported game |
| **MEDIUM** | Warning shown, imports | Blind posting issues, straddle edge cases |
| **LOW** | Informational | Unknown hand prefix, cosmetic issues |

### Common Rejection Causes (% of 78% overall rejection rate)

1. **Cash Drop / Jackpot Fees (40%)**: Pots > 30BB in Rush & Cash have 1BB jackpot fee not shown in hand history
2. **Run It Three Times (15%)**: PT4 simply doesn't support this feature
3. **Dual Tournament Import (20%)**: Importing both hand histories and tournament summaries counts winnings twice
4. **Blind/Straddle Posting (10%)**: Stated blinds don't match posted amounts
5. **Outdated PT4 Version (15%)**: Using PT4 < v4.18.x with known bugs

### Testing

**Test Suite**: `test_validator.py` (16 unit tests)

**Run tests**:
```bash
pytest test_validator.py -v
```

**Test coverage**:
- Valid tournament hands
- Valid cash game hands
- Invalid pot sizes (Cash Drop scenario)
- Blind mismatches
- Duplicate cards
- Run It Three Times rejection
- EV Cashout detection
- Negative stacks
- Invalid Hand ID formats
- Strict vs Permissive modes

### Integration Points

**Current**: Independent endpoint (no pipeline integration)

**Future integration options**:
1. **Pre-processing**: Validate input files before matching
2. **Post-processing**: Validate output files after desanonimization
3. **Filtering**: Skip processing of files that would fail PT4 import
4. **Reporting**: Include validation results in job status/debug info

### Known Issues & Limitations

1. **Stack Consistency**: Not fully implemented (complex, requires full action tracking)
2. **Action Sequence**: Basic validation only (doesn't catch all illogical sequences)
3. **Jackpot Fee Detection**: Infers from summary line, doesn't calculate from pot size/game type
4. **Tournament vs Cash**: Some validations are cash-game specific

### Recommended PT4 Version

**Minimum**: PT4 v4.15.35 (Sept 2021) - Stricter blind validation
**Recommended**: PT4 v4.18.13+ (March 2023) - All known GGPoker bugs fixed
**Latest**: PT4 v4.18.10+ (2025) - Most stable

### References

**Document**: `notas-nico.md` (technical validation document from user)
- Complete PT4 validation rules
- Error message catalog
- Edge case documentation
- Implementation patterns

**Related Files**:
- `validator.py` - Core validation logic
- `test_validator.py` - Unit tests
- `main.py:1152-1227` - API endpoint

## Known Limitations

1. **GEMINI_API_KEY required** - OCR returns mock data if not configured
2. **Rate limits** - Semaphore set to 10 concurrent requests (adjust if needed)
3. **Hero replacement behavior** - "Hero" IS replaced with real player name from OCR (e.g., "Hero" → "TuichAAreko")
4. **Hand count preservation** - All hands from input appear in output (matched or unmatched)
5. **Table name extraction** - Uses regex on `Table 'Name'` format; fails if format differs
6. **Hero position validation disabled** - PokerCraft's visual layout doesn't match seat numbers
7. **Port discrepancy** - `main.py` uses port 5000, `restart.sh` uses port 8000 (update restart.sh if needed)
