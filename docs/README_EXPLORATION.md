# GGRevealer Project Exploration Report

**Date**: November 1, 2025
**Project**: GGRevealer v1.0 (FastAPI Web Application)
**Status**: Architecture completely mapped and documented
**Documentation Created**: 3 comprehensive files

---

## What Was Explored

This report documents a complete exploration of the GGRevealer codebase, including:

1. **Directory structure** - Full mapping of all folders and files
2. **Python modules** - 10 production modules analyzed in detail
3. **Frontend** - HTML/CSS/JavaScript structure
4. **Database** - SQLite schema with 5 tables
5. **APIs** - 14+ REST endpoints documented
6. **Data flows** - Complete 11-phase processing pipeline
7. **Algorithms** - Hand matching, role-based mapping, validation
8. **External integrations** - Google Gemini API, SQLite
9. **Entry points** - 6 major execution pathways
10. **Testing** - 17 test files for coverage

---

## Documentation Created

### 1. **docs/ARCHITECTURE.md** (33 KB)
Comprehensive technical documentation covering:
- Complete directory structure with file purposes
- Core architecture diagram showing all components
- 11-phase processing pipeline data flow
- Detailed breakdown of all 10 Python modules
- Key algorithms (matching, mapping, validation)
- Database schema with 5 tables
- All 14+ API endpoints
- Dataclass hierarchy and type definitions
- Test coverage summary
- External integrations
- Critical implementation patterns
- Storage paths and file organization

**Use this for**: Deep understanding of system architecture and implementation details

---

### 2. **docs/QUICK_REFERENCE.md** (14 KB)
Condensed reference guide including:
- Quick module reference table
- System architecture at a glance
- 11-phase pipeline summary
- Key algorithms in compact form
- Dataclass types
- All API endpoints
- PokerTracker 4 validation checks
- Database schema
- External integrations
- Configuration and dependencies
- Running the application
- Storage structure
- Performance metrics
- Common issues & solutions
- Recent improvements
- Next steps for development

**Use this for**: Quick lookups and understanding the system architecture

---

### 3. **docs/ENTRY_POINTS.txt** (14 KB)
Execution flow documentation including:
- 6 major entry points explained
- Detailed execution paths for each
- Processing pipeline phases (1-11)
- Async/await execution patterns
- Database persistence patterns
- Critical execution constraints
- Error handling & recovery strategies
- Performance characteristics

**Use this for**: Understanding how the system executes and data flows through phases

---

## Project Overview

**GGRevealer** is a FastAPI web application that de-anonymizes GGPoker hand history files by:
1. Parsing hand histories from TXT files
2. Using OCR (Google Gemini Vision API) to extract hand IDs and player names from screenshots
3. Intelligently matching hands to screenshots
4. Creating name mappings using role-based indicators (dealer/SB/BB)
5. Applying mappings to generate PokerTracker-compatible output files

**Key Achievement**: Improved name coverage from 3-5% to 90-95% through dual OCR redesign (Sept 2025)

---

## Quick Statistics

| Metric | Value |
|--------|-------|
| **Codebase Size** | 6,538 lines of Python |
| **Main Modules** | 10 files |
| **Test Files** | 17 files |
| **Processing Phases** | 11 sequential phases |
| **API Endpoints** | 14+ endpoints |
| **Database Tables** | 5 tables (SQLite) |
| **Validation Checks** | 12 PokerTracker validations |
| **Name Coverage** | 90-95% (improved from 3-5%) |
| **OCR1 Accuracy** | 99.9% (hand ID extraction) |
| **OCR2 Accuracy** | 99% (player name extraction) |
| **Role-Based Mapping** | 99% (vs 80% counter-clockwise) |

---

## Module Breakdown

### Core Modules (10 files, 6,538 lines)

1. **main.py** (2564 lines)
   - FastAPI application entry point
   - REST API endpoints
   - 11-phase processing pipeline orchestration

2. **parser.py** (324 lines)
   - Parse GGPoker hand history TXT files
   - Extract hand ID, seats, stacks, actions, board cards

3. **ocr.py** (448 lines)
   - Dual OCR system (OCR1 + OCR2)
   - OCR1: Extract hand IDs (99.9% accuracy)
   - OCR2: Extract player names + roles (99% accuracy)

4. **matcher.py** (612 lines)
   - Match hands to screenshots
   - 3-part matching strategy (normalize, primary, fallback)
   - Role-based mapping (99% accuracy)

5. **writer.py** (427 lines)
   - Generate TXT output files
   - Apply 14 regex patterns for name replacement
   - File classification (_resolved.txt vs _fallado.txt)

6. **validator.py** (1068 lines)
   - PokerTracker 4 validation (12 checks)
   - Identify PT4 rejection reasons
   - Support for detecting Cash Drop fees, Run It Three Times, etc.

7. **database.py** (805 lines)
   - SQLite persistence layer
   - 5 main tables (jobs, files, results, screenshot_results, logs)
   - Auto-migration on startup

8. **logger.py** (129 lines)
   - Structured logging system
   - Colored console output
   - Database persistence with buffering

9. **models.py** (139 lines)
   - Type definitions (10 dataclasses)
   - ParsedHand, ScreenshotAnalysis, HandMatch, etc.

10. **config.py** (22 lines)
    - Configuration constants
    - API pricing, model selection

### Frontend (3 files)
- **templates/index.html** - Jinja2 template, Bootstrap 5 SPA
- **static/js/app.js** - Client-side logic (2700+ lines)
- **static/css/styles.css** - Responsive styling

### Testing (17 files)
- Unit tests for all modules
- Integration tests for workflows
- Regression tests for specific jobs
- Test coverage for validation system

---

## The 11-Phase Processing Pipeline

The system processes jobs through 11 sequential phases:

1. **Parse Hand Histories** - Extract structured data from TXT files
2. **OCR1 (Hand ID)** - Extract ONLY hand ID from screenshots (99.9%)
3. **Match Hands** - Find best screenshot match for each hand
4. **Discard Unmatched** - Skip OCR2 on unmatched (cost savings)
5. **OCR2 (Players)** - Extract player names + roles (99%)
6. **Role-Based Mapping** - Map anonymized IDs to real names (99%)
7. **Table Aggregation** - Apply mappings to all hands in table
8. **Write Outputs** - Generate TXT files with 14 regex patterns
9. **Validate PT4** - 12 validation checks, classify files
10. **Create ZIPs** - Package resolved_hands.zip + fallidos.zip
11. **Export Debug** - Auto-export debug JSON, optional AI prompts

---

## Key Algorithms

### Hand Matching (3-Part Strategy)
1. **Normalize**: Remove ID prefixes (SG, HH, etc.)
2. **Primary**: Hand ID exact match (99.9% accuracy)
3. **Fallback**: 100-point multi-criteria scoring
4. **Validate**: Player count, hero stack ±25%, ≥50% stack alignment

### Role-Based Mapping (99% Accuracy)
1. Extract dealer button (D), SB, BB from OCR2
2. Auto-calculate SB/BB positions from dealer
3. Map anonymized_id → real_player_name
4. Aggregate across all hands in table

### Name Replacement (14 Patterns)
- Order-critical: Most specific patterns first
- Patterns: Seat lines, blind posts, actions, shows, etc.
- Protection: Avoid octal interpretation bugs

---

## Database Schema

**5 Main Tables:**

1. **jobs** - Job tracking (status, counts, statistics)
2. **files** - File references (TXT/screenshot)
3. **results** - Final output files and mappings
4. **screenshot_results** - Per-screenshot OCR tracking
5. **logs** - Structured logging (console + DB)

---

## API Endpoints (14+)

### Job Management
- POST /api/upload - Upload files, create job
- POST /api/process/{job_id} - Start processing
- GET /api/status/{job_id} - Real-time status
- DELETE /api/job/{job_id} - Delete job

### Download
- GET /api/download/{job_id} - Download resolved_hands.zip
- GET /api/download-fallidos/{job_id} - Download fallidos.zip

### Validation & Config
- POST /api/validate - Standalone validation
- GET /api/config/budget - Get budget config
- POST /api/config/budget - Set budget config

### Debugging
- GET /api/debug/{job_id} - Full debug info
- POST /api/debug/{job_id}/generate-prompt - AI debugging
- POST /api/debug/{job_id}/export - Export debug JSON
- GET /api/job/{job_id}/screenshots - Detailed OCR results

---

## External Integrations

### Google Gemini API
- Model: `gemini-2.5-flash-image` (optimized for dual OCR)
- OCR1: Hand ID extraction (99.9% accuracy, minimal cost)
- OCR2: Player names + roles (99% accuracy)
- Rate Limiting: Free (14 req/min), Paid (10 concurrent, unlimited)
- Cost: $0.0164 per screenshot (dual OCR average)

### SQLite Database
- File: `ggrevealer.db`
- Auto-migration on startup
- 5 main tables with proper indexing
- Buffered writes for performance

### Frontend Libraries
- Bootstrap 5.3 (responsive UI)
- Fetch API + jQuery (AJAX)
- Jinja2 (server-side templating)

---

## Entry Points & Execution Flows

### 6 Major Entry Points:

1. **FastAPI Application** (main.py)
   - Initializes database on startup
   - Serves web interface
   - Handles REST requests

2. **Frontend User Actions** (browser)
   - Upload files → POST /api/upload
   - Process job → POST /api/process/{job_id}
   - Poll status → GET /api/status/{job_id}
   - Download → GET /api/download/{job_id}

3. **Processing Pipeline** (run_processing_pipeline)
   - Main orchestrator for all 11 phases
   - Coordinates parser, OCR, matcher, writer, validator
   - Background task execution

4. **Validation System** (optional)
   - Standalone hand history validation
   - 12 PokerTracker 4 checks
   - No database persistence

5. **Debugging & Diagnostics**
   - Full job debug information
   - AI-powered debugging prompts
   - Debug JSON export

6. **Configuration & Settings**
   - Budget configuration
   - API key validation
   - Rate limiting settings

---

## Performance Characteristics

| Metric | Value |
|--------|-------|
| **Typical Job Size** | 300 TXT files + 300 screenshots |
| **Phase 1 (Parse)** | ~10 seconds |
| **Phase 2 (OCR1)** | 10 min (free) / 3 min (paid) |
| **Phase 3 (Match)** | ~30 seconds |
| **Phase 5 (OCR2)** | ~5 minutes (if 50% matched) |
| **Phase 8 (Write)** | ~1 minute |
| **Phase 9 (Validate)** | ~2 minutes |
| **Total Time** | 15-30 minutes |
| **Total Cost** | ~$5 for 300 screenshots |

---

## How to Use These Documents

### For Understanding System Architecture
Start with **docs/QUICK_REFERENCE.md** for overview, then **docs/ARCHITECTURE.md** for details

### For Understanding Execution Flows
Read **docs/ENTRY_POINTS.txt** for how data flows through the system

### For Development
- Reference **docs/QUICK_REFERENCE.md** for module purposes
- Consult **docs/ARCHITECTURE.md** for implementation details
- Use **docs/ENTRY_POINTS.txt** for execution flow understanding

### For Debugging
- Use **docs/ENTRY_POINTS.txt** to understand phase execution
- Refer to error handling section for recovery strategies
- Check API section for debugging endpoints

---

## Key Findings

1. **Well-Structured Codebase**
   - Clear separation of concerns
   - Type safety with dataclasses
   - Comprehensive database layer

2. **Sophisticated Algorithms**
   - Dual OCR system (99.9% + 99% accuracy)
   - Role-based mapping (99% accuracy)
   - Multi-criteria matching with validation gates

3. **Production-Ready Features**
   - Structured logging with persistence
   - PokerTracker 4 validation (12 checks)
   - Rate limiting and budget tracking
   - Auto-export debug information
   - AI-powered debugging prompts

4. **Async/Concurrent Processing**
   - Semaphore-based rate limiting
   - Parallel OCR processing
   - 50% cost savings through intelligent discarding

5. **Comprehensive Testing**
   - 17 test files covering all modules
   - Regression testing for specific jobs
   - Validation testing for PokerTracker compatibility

---

## Recommendations for Future Development

1. **Enhanced Testing**
   - More integration tests
   - End-to-end workflow tests
   - Performance benchmarking

2. **UI/UX Improvements**
   - Better visualization of OCR results
   - Real-time progress updates via WebSocket
   - Batch processing management

3. **Feature Expansion**
   - Support for other poker apps (PT5, HM3, etc.)
   - Manual mapping UI
   - Advanced filtering and search
   - Export format customization

4. **Performance Optimization**
   - Database query optimization
   - Caching layer for repeated operations
   - Batch processing of multiple jobs

5. **Monitoring & Analytics**
   - Job completion tracking
   - Success rate analytics
   - Cost tracking dashboard
   - Error pattern analysis

---

## Documentation Files Summary

| File | Size | Purpose |
|------|------|---------|
| docs/ARCHITECTURE.md | 33 KB | Complete technical architecture |
| docs/QUICK_REFERENCE.md | 14 KB | Quick lookup reference |
| docs/ENTRY_POINTS.txt | 14 KB | Execution flows and entry points |

All three documents work together to provide a comprehensive understanding of the GGRevealer system.

---

## Conclusion

The GGRevealer project is a well-architected FastAPI application with a sophisticated dual OCR system for de-anonymizing poker hand histories. The codebase is well-organized with clear separation of concerns, comprehensive testing, and production-ready features.

The complete architecture has been documented in three comprehensive files that can be used for:
- Understanding the system design
- Onboarding new developers
- Debugging issues
- Planning future enhancements
- API integration

For questions about specific components, refer to the appropriate documentation file listed above.

---

**Exploration Completed**: November 1, 2025
**Documentation Status**: Complete and verified
**Ready for**: Development, debugging, enhancement planning
