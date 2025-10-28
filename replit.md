# GGRevealer - Poker Hand De-anonymizer

## Overview
GGRevealer is a web application designed to de-anonymize GGPoker hand history files. It processes these files in conjunction with PokerCraft screenshots, utilizing Google Gemini Vision API for optical character recognition (OCR). The primary purpose is to match anonymized player IDs from hand histories with real player names extracted from screenshots, generating PokerTracker-compatible hand history files with real names. The project aims to provide a robust solution for poker players to analyze their gameplay with complete player information.

## User Preferences
I prefer simple language. I want iterative development. Ask before making major changes. I prefer detailed explanations. Do not make changes to the folder Z. Do not make changes to the file Y.

## System Architecture

### UI/UX Decisions
The application features a responsive, mobile-first design built with Bootstrap 5 and Vanilla JS. It includes drag-and-drop functionality for file uploads, real-time job status monitoring with a visual pipeline (Parsing → OCR → Matching → Writing), and expandable job history cards displaying detailed statistics. The UI provides clear feedback on file classification (resolved/failed) and guides the user through the process, indicating which files are ready and which need further attention.

### Technical Implementations
The backend is built with Python and FastAPI, handling hand history parsing, OCR integration, intelligent matching, and output generation. It uses an SQLite database for persistent storage of jobs, files, results, and detailed screenshot analysis. The OCR functionality leverages Google Gemini 2.0 Flash Vision API for text extraction from images.

### Feature Specifications
- **File Upload**: Multi-file drag-and-drop for `.txt` hand histories and screenshots.
- **Background Processing**: Asynchronous job processing with real-time status tracking and progress indicators.
- **OCR Analysis**: Utilizes Google Gemini Vision API for efficient text extraction from PokerCraft screenshots, including hand IDs.
- **Intelligent Matching**: A sophisticated scoring algorithm matches hand histories with screenshots based on multiple criteria (hero cards, board cards, timestamp, hero position, player names, stack size). Prioritizes direct Hand ID matches extracted via OCR for high accuracy.
- **Name Mapping**: Automatic seat-based mapping from anonymized IDs to real player names, including the "Hero" player.
- **Output Validation**: Comprehensive validation checks (10 critical checks) ensure PokerTracker compatibility, handling issues like line endings and cardless lines.
- **File Classification System**: All input hands are included in output. Files are classified as `_resolved.txt` (100% de-anonymized) or `_fallado.txt` (contains unmapped IDs), with separate ZIP downloads.
- **Job History**: Persistent storage and retrieval of all processing jobs with detailed statistics and diagnostic information, including per-screenshot error tracking.

### System Design Choices
The system employs a modular architecture with distinct components for parsing, OCR, matching, and writing, facilitating maintainability and scalability. Asynchronous processing and parallel OCR requests (with a Semaphore for API rate limiting) optimize performance. The `screenshot_results` table provides granular diagnostic visibility, tracking OCR success/failure and match counts per screenshot.

### Critical Fixes & Known Issues

#### Octal Interpretation Bug in Regex Replacements (Oct 2025 - FIXED)
**Problem**: PokerTracker rejected ~80% of hands when player names started with digits (e.g., "50Zoos", "9BetKing"). Seat lines were corrupted or missing entirely.

**Root Cause**: Python's regex `re.sub()` interpreted escape sequences like `\150` as octal codes when using f-string replacements like `rf'\1{real_name}\2'`. For example:
- Input: `Seat 3: 9d830e65 (625 in chips)`
- Expected: `Seat 3: 50Zoos (625 in chips)` ✅
- Actual: `hZoos (625 in chips)` ❌ (because `\150` octal = 'h')

**Solution**: Changed all affected regex patterns in `writer.py` to use explicit group references with concatenation: `r'\g<1>' + real_name + r'\g<2>'`. This prevents Python from interpreting digit sequences as octal codes.

**Affected Patterns** (5 total):
1. Pattern #1: Seat lines - `Seat X: PlayerID (stack in chips)`
2. Pattern #6: Dealt to (no cards) - `Dealt to PlayerID`
3. Pattern #7: Dealt to (with cards) - `Dealt to PlayerID [cards]`
4. Pattern #12: Summary lines - `Seat X: PlayerID (position)`
5. Pattern #13: Uncalled bet - `returned to PlayerID`

**Validation**: All 14 regex patterns in `generate_final_txt()` now safely handle player names starting with any character, including digits.

## External Dependencies
- **Google Gemini Vision API**: Used for OCR capabilities to extract text and hand IDs from PokerCraft screenshots. Requires `GEMINI_API_KEY`.
- **FastAPI**: Python web framework for building the backend REST API.
- **Uvicorn**: ASGI server to run the FastAPI application.
- **aiosqlite**: Asynchronous SQLite driver for database interactions.
- **python-dotenv**: For managing environment variables (e.g., `GEMINI_API_KEY`).
- **python-multipart**: For handling file uploads in FastAPI.
- **Jinja2**: Templating engine for the frontend.