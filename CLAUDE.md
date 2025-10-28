# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GGRevealer** is a FastAPI web application that de-anonymizes GGPoker hand history files by matching them with PokerCraft screenshots using Google Gemini Vision API for OCR. The system outputs PokerTracker-compatible hand history files with real player names.

**Tech Stack**: Python 3.11+ • FastAPI • SQLite • Google Gemini 2.5 Flash Vision • Vanilla JS + Bootstrap 5

## Development Commands

### Running the Application
```bash
# Start the server (port 5000)
python main.py

# Alternative with uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 5000 --reload
```

### Testing
```bash
# Run CLI test suite (tests parser, writer, and API key configuration)
python test_cli.py
```

### Environment Setup
Create `.env` file with:
```
GEMINI_API_KEY=your_api_key_here
```
Get API key from: https://makersuite.google.com/app/apikey

## Architecture & Data Flow

### Core Pipeline (main.py:268-543 `run_processing_pipeline`)

1. **Parse TXT files** → Extract hand histories using `GGPokerParser.parse_file()`
2. **OCR Screenshots** → Parallel async processing (10 concurrent) with `ocr_screenshot()`
3. **Match Hands** → Primary key matching using Hand ID, fallback to 100-point scoring
4. **Generate Mappings** → Build seat-based anonymized_id → real_name mappings
5. **Write Outputs** → Generate per-table TXT files with 14 regex replacement patterns
6. **Validate & Classify** → Split into `_resolved.txt` (clean) and `_fallado.txt` (has unmapped IDs)

### Key Modules

**parser.py** - GGPoker hand history parser
- Extracts hand ID, timestamp, seats, positions, board cards, actions
- Supports both cash games and tournaments
- Detects 3-max vs 6-max table formats

**ocr.py** - Google Gemini Vision OCR
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

### File Classification System (CRITICAL - Never Lose Hands)

ALL hands from input TXT files are included in outputs. Files are classified per-table:

- **`_resolved.txt`** → 100% de-anonymized, ready for PokerTracker import (packaged in `resolved_hands.zip`)
- **`_fallado.txt`** → Contains unmapped anonymous IDs, needs more screenshots (packaged in `fallidos.zip`)

The system tracks `unmapped_ids` list per file and provides transparent reporting in UI.

### API Endpoints (main.py:62-266)

- `POST /api/upload` → Upload TXT files + screenshots, creates job
- `POST /api/process/{job_id}` → Start background processing
- `GET /api/status/{job_id}` → Real-time status with OCR progress (ocr_processed/ocr_total), statistics, successful_files, failed_files
- `GET /api/download/{job_id}` → Download `resolved_hands.zip` (clean files)
- `GET /api/download-fallidos/{job_id}` → Download `fallidos.zip` (files with unmapped IDs)
- `GET /api/job/{job_id}/screenshots` → Detailed screenshot results (OCR errors, match counts)
- `DELETE /api/job/{job_id}` → Delete job and files

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

### Hand ID Matching Strategy (matcher.py:37-76)
1. Check `screenshot.hand_id == hand.hand_id` (OCR extracted) → 100 points
2. Check `hand.hand_id in screenshot.screenshot_id` (filename) → 100 points
3. Fallback to multi-criteria scoring → 0-100 points

## Common Development Patterns

### Adding a new regex pattern to writer.py
1. Insert in correct order (most specific first)
2. Use `re.escape(anon_id)` to prevent regex injection
3. Use `rf'...'` for raw f-strings with regex
4. Test with `re.MULTILINE` flag if matching line starts (`^`)
5. Add negative lookaheads to prevent over-matching

### Modifying OCR prompt (ocr.py:46-117)
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
└── outputs/{job_id}/
    ├── {table}_resolved.txt     # Clean files (all IDs mapped)
    ├── {table}_fallado.txt      # Failed files (unmapped IDs)
    ├── resolved_hands.zip       # ZIP of all _resolved.txt files
    └── fallidos.zip             # ZIP of all _fallado.txt files
```

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

### Check OCR results
```python
# In ocr.py, print raw Gemini response
print(f"Raw response: {response.text}")
```

### Check matching scores
```python
# In matcher.py, already logs to console:
print(f"✅ Hand ID match: {hand.hand_id} ↔ {screenshot.screenshot_id}")
print(f"⚠️  Fallback match: {hand.hand_id} ↔ {screenshot.screenshot_id} (score: {best_score:.1f})")
```

### Inspect unmapped IDs
```python
# Check writer.py validation output
unmapped_ids = detect_unmapped_ids_in_text(final_txt)
print(f"Unmapped: {unmapped_ids}")
```

### Review job processing logs
Server console shows detailed pipeline logs:
```
[JOB {id}] Starting processing...
[JOB {id}] Parsed {n} hands
[JOB {id}] OCR completed: {n} screenshots analyzed
[JOB {id}] Found {n} matches
[JOB {id}] Generated {n} name mappings
```

## Known Limitations

1. **GEMINI_API_KEY required** - OCR returns mock data if not configured
2. **Rate limits** - Semaphore set to 10 concurrent requests (adjust if needed)
3. **Hero protection** - "Hero" is NEVER replaced (PokerTracker requirement, not a bug)
4. **Hand count preservation** - All hands from input appear in output (matched or unmatched)
5. **Table name extraction** - Uses regex on `Table 'Name'` format; fails if format differs
