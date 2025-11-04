# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GGRevealer** is a FastAPI web application that de-anonymizes GGPoker hand history files by matching them with PokerCraft screenshots using Google Gemini Vision API for OCR. Outputs PokerTracker-compatible hand history files with real player names.

**Tech Stack**: Python 3.11+ • FastAPI • SQLite • Google Gemini 2.5 Flash • Vanilla JS + Bootstrap 5

## Quick Start

### Running
```bash
python main.py                    # Port 5000 (dev), 8000 (live)
pytest tests/ -v                  # Run all tests
python test_validator.py -v       # Test PT4 validation rules
```

### Setup
Create `.env`:
```
GEMINI_API_KEY=your_api_key_here
```

## Architecture

### Core Pipeline (main.py: `run_processing_pipeline`)

**Phase 1-7**: Parse TXT → OCR1 (hand IDs) → Match by ID → Retry failed → Discard unmatched → OCR2 (player details) → Generate mappings

**Key Modules**:
- **parser.py**: GGPoker hand history extraction (ParsedHand objects with seats, positions, actions)
- **ocr.py**: Dual-phase OCR (OCR1: extract hand ID only; OCR2: player names + roles) using `gemini-2.5-flash-image`
- **matcher.py**: Hand-to-screenshot matching (99.9% via hand ID, fallback scoring) + role-based name mapping
- **writer.py**: 14 regex patterns to replace anonymized IDs; 10 PokerTracker validations
- **database.py**: SQLite persistence (jobs, files, results, screenshot_results, logs, pt4_import_attempts, pt4_failed_files)
- **validator.py**: Replicates PT4's 12 validations (pot size, blinds, cards, game type, etc.)

### Data Flow
```
TXT Upload → parser.py (ParsedHand) → ocr.py (OCR1+2) → matcher.py (mappings) → writer.py (output TXT) → database.py
```

## Critical Rules

### Regex Replacement Order (writer.py:174-282)
1. Blind posts BEFORE general actions
2. Actions with amounts BEFORE without amounts
3. Most specific patterns (lookaheads) first
4. Use `r'\g<1>' + name + r'\g<2>'` for names starting with digits (prevents octal interpretation)

### Hand ID Matching (matcher.py:11-240)
1. Normalize hand IDs (strip prefixes: SG, HH, MT, TT)
2. PRIMARY: `screenshot.hand_id == hand.hand_id` (100 pts)
3. FALLBACK: Multi-criteria scoring (70.0 threshold)
4. VALIDATION GATES (applied before accepting any match):
   - Player count match
   - Hero stack within ±25%
   - ≥50% stacks within ±30%

### Unmapped ID Detection (writer.py:78-98, 373-395)
- Pattern: `\b[a-f0-9]{6,8}\b` (6-8 char hex)
- Verify context: not timestamps/cards/hand IDs
- Presence → file classified as `_fallado.txt`

### Hero Replacement
"Hero" IS replaced with real player name (e.g., "Hero" → "TuichAAreko"). Matcher creates `"Hero" → "Real Name"` mapping applied like any other ID.

### OCR Parallelization
Use `asyncio.Semaphore(10)` for max 10 concurrent Gemini requests (critical for rate limiting).

## Common Patterns

### Adding Regex Pattern to writer.py
1. Insert in correct order (most specific first)
2. Use `re.escape(anon_id)` to prevent regex injection
3. Use `rf'...'` for raw f-strings
4. Use `re.MULTILINE` if matching line starts (`^`)

### Modifying OCR Prompt (ocr.py:46-117)
- Model: `gemini-2.5-flash-image` (don't change - tested)
- Output must match `ScreenshotAnalysis` dataclass
- Hand ID extraction is highest priority for matching accuracy

### Database Migrations (database.py:95-123)
- Check if column exists: `PRAGMA table_info(table_name)`
- Add with `ALTER TABLE ... ADD COLUMN ... DEFAULT ...`
- Prevents breaking existing rows

### Testing Batch Uploads with curl

```bash
# 1. Initialize job
JOB_ID=$(curl -s -X POST http://localhost:8000/api/upload/init -F "api_tier=free" | jq -r '.job_id')

# 2. Upload batch 1
curl -X POST http://localhost:8000/api/upload/batch/$JOB_ID \
  -F "txt_files=@file1.txt" \
  -F "txt_files=@file2.txt"

# 3. Upload batch 2
curl -X POST http://localhost:8000/api/upload/batch/$JOB_ID \
  -F "screenshots=@screenshot1.png" \
  -F "screenshots=@screenshot2.png"

# 4. Start processing
curl -X POST http://localhost:8000/api/process/$JOB_ID \
  -H "X-Gemini-API-Key: your_key_here"
```

## Storage Structure

```
storage/
├── uploads/{job_id}/txt/*.txt              # Original hand histories
├── uploads/{job_id}/screenshots/*.png      # PokerCraft screenshots
├── outputs/{job_id}/{table}_resolved.txt   # Clean (100% mapped)
├── outputs/{job_id}/{table}_fallado.txt    # Unmapped IDs (needs more screenshots)
├── outputs/{job_id}/resolved_hands.zip     # All _resolved.txt
├── outputs/{job_id}/fallidos.zip           # All _fallado.txt
└── debug/debug_job_{id}_{timestamp}.json   # Auto-exported debug info
```

Database: `ggrevealer.db` (SQLite)

## PokerTracker Validation (10 Rules)

Hand must pass these to import successfully:
1. Hero count unchanged (CRITICAL)
2. Line count ±2 variance
3. Hand ID unchanged
4. Timestamp unchanged
5. No double currency symbols (`$$`)
6. Summary section preserved
7. Table name unchanged
8. Seat count match
9. Chip value count preserved
10. No unmapped anonymous IDs (CRITICAL)

Violations #1 or #10 cause rejection.

## Recent Changes & Pending Work

### Recent (Nov 2025)
- **PT4 Failed Files Recovery**: Parse PT4 import logs, extract failed files, match to original jobs
- **Batch Upload**: Support chunked file uploads for large jobs
- **Screenshot URL Handling**: Fixed path encoding issues in API endpoints
- **Job ID Selection**: Matcher respects user-specified job ID preference

### Pending
- **Hand-ID-Based Screenshot Matching** (pt4_matcher.py:110-114)
  - Problem: Some jobs have screenshots named by hand ID, not table number
  - Solution: Extract hand IDs from TXT, search screenshots by hand ID, fallback to table number
  - Status: TODO - implement in pt4_matcher.py

## Known Issues Fixed (Oct 2025)

| Issue | Root Cause | Fix | Impact |
|-------|-----------|-----|--------|
| Names starting with digits corrupted | `\150` interpreted as octal | Use `r'\g<1>'` groups | PT4 rejection prevention |
| Duplicate player in same hand | Incorrect screenshot matching | Added duplicate name detection | 100% mapping reliability |
| Only 1/5 tables fully de-anonymized | Only matched hand's players extracted | Extract ALL visible players | 3.4% → ~100% match rate |
| ~21% incorrect matches | Weak fallback matching validation | Added 3 validation gates | 21% → 4% incorrect matches |
| OCR role assignment failures | Relied on inconsistent SB/BB badges | Dealer-first role mapping | 80% → 100% resolution |

## Debugging

### Auto-Generated Debug Info
After each job: `storage/debug/debug_job_{id}_{timestamp}.json` (complete job state + logs)

### Manual Checks
```python
# OCR results: check ocr.py raw_response
print(f"Raw response: {response.text}")

# Matching scores: matcher.py already logs
# ✅ Hand ID match: {hand.hand_id} ↔ {screenshot.screenshot_id}
# ⚠️  Fallback match: {hand.hand_id} ↔ {screenshot.screenshot_id} (score: {best_score:.1f})

# Unmapped IDs
unmapped_ids = detect_unmapped_ids_in_text(final_txt)
print(f"Unmapped: {unmapped_ids}")
```

### API Endpoints

**Core Workflow:**
- `POST /api/upload` → Upload TXT files + screenshots, creates job (legacy single upload)
- `POST /api/process/{job_id}` → Start background processing
- `GET /api/status/{job_id}` → Real-time status with statistics
- `GET /api/download/{job_id}` → Download `resolved_hands.zip`
- `GET /api/download-fallidos/{job_id}` → Download `fallidos.zip`

**Batch Upload System (Nov 2025):**

**Problem**: Replit's nginx proxy has ~100 MB upload limit, causing 413 errors for large uploads even though app supports 300 MB.

**Solution**: Batch upload system splits files into ~50-60 MB chunks uploaded sequentially.

**Workflow:**
1. Frontend: Split files into size-based batches using `createFileBatches()`
2. `POST /api/upload/init` → Create job, return job_id (no files uploaded yet)
3. Loop: `POST /api/upload/batch/{job_id}` → Upload each batch sequentially
4. `POST /api/process/{job_id}` → Start processing after all batches uploaded

**New Endpoints:**
- `POST /api/upload/init` → Initialize job without files
  - Input: `api_tier` (free/paid)
  - Output: `{ job_id, status: "initialized" }`

- `POST /api/upload/batch/{job_id}` → Upload file batch to existing job
  - Input: `txt_files[]`, `screenshots[]` (multipart files)
  - Output: `{ job_id, batch_txt_count, batch_screenshot_count, total_txt_count, total_screenshot_count }`
  - Validates: File count limits (cumulative across all batches)
  - Rejects: Jobs not in 'pending' or 'initialized' status

**Frontend Implementation:**
- `createFileBatches(files, maxSize)` - Split files into size-based batches
- `calculateTotalSize(files)` - Get total size in bytes
- `formatBytes(bytes)` - Format to human-readable (e.g., "12.5 MB")
- Batch progress UI with animated progress bar
- Error handling with automatic cleanup

**Constants:**
- `MAX_BATCH_SIZE_MB = 55` (55 MB to stay safely under 60 MB with overhead)
- `MAX_BATCH_SIZE_BYTES = 55 * 1024 * 1024`

**Location**: `main.py:210-350` (endpoints), `static/js/app.js:1-100,295-373` (frontend)

**Debugging & Diagnostics:**
- `POST /api/debug/{job_id}/export` - Manual debug export
- `POST /api/debug/{job_id}/generate-prompt` - AI debugging via Gemini
- `POST /api/validate` - Validate TXT file before processing

## Module Reference

**parser.py**: `GGPokerParser.parse_file()` → `ParsedHand` objects. Key: `find_seat_by_role()` identifies button/SB/BB from action text.

**ocr.py**: `ocr_hand_id()` (phase 1), `ocr_player_details()` (phase 2). Returns (success, data, error).

**matcher.py**: `find_best_matches()` (hand-to-screenshot), `_build_seat_mapping_by_roles()` (role-based name mapping). Validation: `validate_match_quality()`.

**writer.py**: `generate_output_files()` applies 14 patterns. Validation: `validate_output_hand_history()` checks 10 rules.

**database.py**: `get_job()`, `save_job_results()`, `get_failed_files_for_job()`, etc. Key: async batch writes for performance.

**validator.py**: `GGPokerHandHistoryValidator` class with 12 critical validations. Modes: strict (rejects like PT4) or permissive (only logs).

## Development Notes

- User prefers simple language and iterative development
- Ask before major changes (architecture, breaking API changes)
- Git: commit + push after each feature (siempre hacer commit y push)
- Paths with leading slashes need special handling (JavaScript/FastAPI interop)
- Never lose hands: all input hands appear in output (_resolved.txt or _fallado.txt)
- use restart.sh to restart the server. we use port 8000 for local development, and 5000 for replit. so you should always use only 8000