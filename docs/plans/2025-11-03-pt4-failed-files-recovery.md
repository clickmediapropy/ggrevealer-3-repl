# PokerTracker Failed Files Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable users to paste PokerTracker import logs, automatically extract failed files, match them to original job screenshots, and display all relevant files (original TXT, processed TXT, screenshots) in a table for easy manual correction.

**Architecture:** Two-phase failure tracking system: (1) App-detected failures (unmapped IDs) stored during processing, (2) PT4-detected failures (duplicate players, validation errors) parsed from user-uploaded logs. Smart matching algorithm connects PT4 failed filenames to original jobs by table number, auto-fetching associated screenshots and input files.

**Tech Stack:** Python 3.11+ • FastAPI • SQLite • Vanilla JS • Bootstrap 5 • Regex-based log parsing

---

## Task 1: Database Schema - PT4 Import Attempts Table

**Files:**
- Modify: `database.py:18-103` (add to SCHEMA)
- Modify: `database.py:125-250` (add migration logic)

**Step 1: Write the failing test**

Create: `tests/test_pt4_import_tracking.py`

```python
import pytest
from database import init_db, create_pt4_import_attempt, get_db

def test_create_pt4_import_attempt():
    """Test creating a PT4 import attempt record"""
    init_db()

    pt4_log = """06:58:32 pm: Import file: /path/46798_resolved.txt
06:58:32 pm: Error: GG Poker: Duplicate player...
06:58:32 pm:         + Complete (0 hands, 0 summaries, 5 errors, 0 duplicates)"""

    attempt_id = create_pt4_import_attempt(
        job_id=1,
        import_log=pt4_log,
        total_files=1,
        failed_files_count=1
    )

    assert attempt_id is not None
    assert attempt_id > 0

    # Verify stored in database
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM pt4_import_attempts WHERE id = ?",
            (attempt_id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['job_id'] == 1
        assert row['total_files'] == 1
        assert row['failed_files_count'] == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pt4_import_tracking.py::test_create_pt4_import_attempt -v`

Expected: FAIL with "no such table: pt4_import_attempts"

**Step 3: Add pt4_import_attempts table to schema**

Modify: `database.py:18-103`

Add after logs table (around line 91):

```python
-- PT4 import attempts table (second-stage failure tracking)
CREATE TABLE IF NOT EXISTS pt4_import_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    import_log TEXT NOT NULL,
    parsed_at TEXT NOT NULL,
    total_files INTEGER DEFAULT 0,
    failed_files_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pt4_attempts_job_id ON pt4_import_attempts(job_id);
```

**Step 4: Add create_pt4_import_attempt function**

Add to `database.py` after `get_job_logs()` (around line 700):

```python
def create_pt4_import_attempt(
    job_id: int,
    import_log: str,
    total_files: int,
    failed_files_count: int
) -> int:
    """Create a new PT4 import attempt record"""
    from datetime import datetime

    now = datetime.now().isoformat()

    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO pt4_import_attempts
            (job_id, import_log, parsed_at, total_files, failed_files_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, import_log, now, total_files, failed_files_count, now)
        )
        return cursor.lastrowid
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_pt4_import_tracking.py::test_create_pt4_import_attempt -v`

Expected: PASS

**Step 6: Commit**

```bash
git add database.py tests/test_pt4_import_tracking.py
git commit -m "feat: add pt4_import_attempts table for second-stage failure tracking"
```

---

## Task 2: Database Schema - PT4 Failed Files Table

**Files:**
- Modify: `database.py:18-103` (add to SCHEMA)
- Modify: `tests/test_pt4_import_tracking.py` (add test)

**Step 1: Write the failing test**

Add to `tests/test_pt4_import_tracking.py`:

```python
def test_create_pt4_failed_file():
    """Test creating a PT4 failed file record"""
    init_db()

    # Create parent import attempt
    attempt_id = create_pt4_import_attempt(
        job_id=1,
        import_log="test log",
        total_files=1,
        failed_files_count=1
    )

    # Create failed file record
    import json
    failed_file_id = create_pt4_failed_file(
        pt4_import_attempt_id=attempt_id,
        filename="46798_resolved.txt",
        table_number=46798,
        error_count=5,
        error_details=json.dumps([
            "Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247438352) (Line #5)"
        ]),
        associated_job_id=1
    )

    assert failed_file_id is not None
    assert failed_file_id > 0

    # Verify stored
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM pt4_failed_files WHERE id = ?",
            (failed_file_id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['filename'] == "46798_resolved.txt"
        assert row['table_number'] == 46798
        assert row['error_count'] == 5
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pt4_import_tracking.py::test_create_pt4_failed_file -v`

Expected: FAIL with "no such table: pt4_failed_files"

**Step 3: Add pt4_failed_files table to schema**

Modify: `database.py:18-103`

Add after pt4_import_attempts table:

```python
-- PT4 failed files table (individual failed files)
CREATE TABLE IF NOT EXISTS pt4_failed_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pt4_import_attempt_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    table_number INTEGER,
    error_count INTEGER DEFAULT 0,
    error_details TEXT,
    associated_job_id INTEGER,
    associated_original_txt_path TEXT,
    associated_processed_txt_path TEXT,
    associated_screenshot_paths TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (pt4_import_attempt_id) REFERENCES pt4_import_attempts (id) ON DELETE CASCADE,
    FOREIGN KEY (associated_job_id) REFERENCES jobs (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_pt4_failed_files_attempt_id ON pt4_failed_files(pt4_import_attempt_id);
CREATE INDEX IF NOT EXISTS idx_pt4_failed_files_table_number ON pt4_failed_files(table_number);
```

**Step 4: Add create_pt4_failed_file function**

Add to `database.py` after `create_pt4_import_attempt()`:

```python
def create_pt4_failed_file(
    pt4_import_attempt_id: int,
    filename: str,
    table_number: Optional[int],
    error_count: int,
    error_details: str,
    associated_job_id: Optional[int] = None,
    associated_original_txt_path: Optional[str] = None,
    associated_processed_txt_path: Optional[str] = None,
    associated_screenshot_paths: Optional[str] = None
) -> int:
    """Create a new PT4 failed file record"""
    from datetime import datetime

    now = datetime.now().isoformat()

    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO pt4_failed_files
            (pt4_import_attempt_id, filename, table_number, error_count, error_details,
             associated_job_id, associated_original_txt_path, associated_processed_txt_path,
             associated_screenshot_paths, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (pt4_import_attempt_id, filename, table_number, error_count, error_details,
             associated_job_id, associated_original_txt_path, associated_processed_txt_path,
             associated_screenshot_paths, now)
        )
        return cursor.lastrowid
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_pt4_import_tracking.py::test_create_pt4_failed_file -v`

Expected: PASS

**Step 6: Commit**

```bash
git add database.py tests/test_pt4_import_tracking.py
git commit -m "feat: add pt4_failed_files table for tracking individual failed files"
```

---

## Task 3: PT4 Log Parser Module

**Files:**
- Create: `pt4_parser.py`
- Create: `tests/test_pt4_parser.py`

**Step 1: Write the failing test**

Create: `tests/test_pt4_parser.py`

```python
import pytest
from pt4_parser import parse_pt4_import_log, PT4ParsedResult

def test_parse_pt4_log_with_errors():
    """Test parsing PT4 log with failed files"""
    log = """06:58:32 pm: Importing files from disk...
06:58:32 pm: Import file: /Users/nicodelgadob/Downloads/resolved_hands_35 (1)/46798_resolved.txt
06:58:32 pm: Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247438352) (Line #5)
06:58:32 pm: Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247438203) (Line #32)
06:58:32 pm:         + Complete (0 hands, 0 summaries, 2 errors, 0 duplicates)
06:58:32 pm: Import file: /Users/nicodelgadob/Downloads/resolved_hands_35 (1)/43746_resolved.txt
06:58:32 pm:         + Complete (9 hands, 0 summaries, 0 errors, 0 duplicates)
06:58:32 pm: Import complete. 9 hands in 2 files were imported. (2 errors, 0 duplicates)"""

    result = parse_pt4_import_log(log)

    assert result is not None
    assert result.total_files == 2
    assert result.total_hands_imported == 9
    assert result.total_errors == 2
    assert len(result.failed_files) == 1

    failed_file = result.failed_files[0]
    assert failed_file['filename'] == '46798_resolved.txt'
    assert failed_file['table_number'] == 46798
    assert failed_file['error_count'] == 2
    assert len(failed_file['errors']) == 2

def test_parse_pt4_log_no_errors():
    """Test parsing PT4 log with no errors"""
    log = """06:58:32 pm: Importing files from disk...
06:58:32 pm: Import file: /path/43746_resolved.txt
06:58:32 pm:         + Complete (9 hands, 0 summaries, 0 errors, 0 duplicates)
06:58:32 pm: Import complete. 9 hands in 1 file were imported. (0 errors, 0 duplicates)"""

    result = parse_pt4_import_log(log)

    assert result is not None
    assert result.total_files == 1
    assert result.total_errors == 0
    assert len(result.failed_files) == 0

def test_extract_table_number_from_filename():
    """Test extracting table number from filename"""
    from pt4_parser import extract_table_number

    assert extract_table_number("46798_resolved.txt") == 46798
    assert extract_table_number("12345_fallado.txt") == 12345
    assert extract_table_number("/path/to/54321_resolved.txt") == 54321
    assert extract_table_number("invalid.txt") is None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pt4_parser.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'pt4_parser'"

**Step 3: Write minimal implementation**

Create: `pt4_parser.py`

```python
"""
PokerTracker 4 import log parser
Extracts failed files from PT4 import logs
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class PT4ParsedResult:
    """Result of parsing a PT4 import log"""
    total_files: int
    total_hands_imported: int
    total_errors: int
    total_duplicates: int
    failed_files: List[Dict]


def extract_table_number(filename: str) -> Optional[int]:
    """
    Extract table number from filename like '46798_resolved.txt'

    Args:
        filename: Filename with or without path

    Returns:
        Table number as int, or None if not found
    """
    # Extract just the filename if path included
    basename = filename.split('/')[-1]

    # Match pattern: {digits}_{suffix}.txt
    match = re.match(r'^(\d+)_(?:resolved|fallado)\.txt$', basename)
    if match:
        return int(match.group(1))
    return None


def parse_pt4_import_log(log_text: str) -> Optional[PT4ParsedResult]:
    """
    Parse PokerTracker 4 import log to extract failed files

    Args:
        log_text: Raw PT4 import log text

    Returns:
        PT4ParsedResult with parsed data, or None if invalid log
    """
    lines = log_text.strip().split('\n')

    failed_files = []
    current_file = None
    current_errors = []

    total_files = 0
    total_hands = 0
    total_errors = 0
    total_duplicates = 0

    for line in lines:
        # Match: Import file: /path/to/46798_resolved.txt
        file_match = re.search(r'Import file:\s+(.+\.txt)$', line)
        if file_match:
            # Save previous file if it had errors
            if current_file and current_errors:
                filename = current_file.split('/')[-1]
                table_num = extract_table_number(filename)
                failed_files.append({
                    'filename': filename,
                    'table_number': table_num,
                    'error_count': len(current_errors),
                    'errors': current_errors.copy()
                })

            # Start new file
            current_file = file_match.group(1)
            current_errors = []
            total_files += 1
            continue

        # Match: Error: GG Poker: Duplicate player...
        error_match = re.search(r'^\d{2}:\d{2}:\d{2}\s+[ap]m:\s+Error:\s+(.+)$', line)
        if error_match:
            current_errors.append(error_match.group(1))
            continue

        # Match: + Complete (X hands, Y summaries, Z errors, W duplicates)
        complete_match = re.search(
            r'\+\s+Complete\s+\((\d+)\s+hands?,\s+\d+\s+summaries?,\s+(\d+)\s+errors?,\s+(\d+)\s+duplicates?\)',
            line
        )
        if complete_match:
            hands = int(complete_match.group(1))
            errors = int(complete_match.group(2))
            duplicates = int(complete_match.group(3))

            total_hands += hands
            total_errors += errors
            total_duplicates += duplicates

            # If errors > 0, save this file
            if errors > 0 and current_file:
                filename = current_file.split('/')[-1]
                table_num = extract_table_number(filename)
                failed_files.append({
                    'filename': filename,
                    'table_number': table_num,
                    'error_count': len(current_errors),
                    'errors': current_errors.copy()
                })

            # Reset for next file
            current_file = None
            current_errors = []
            continue

    return PT4ParsedResult(
        total_files=total_files,
        total_hands_imported=total_hands,
        total_errors=total_errors,
        total_duplicates=total_duplicates,
        failed_files=failed_files
    )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pt4_parser.py -v`

Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add pt4_parser.py tests/test_pt4_parser.py
git commit -m "feat: add PT4 import log parser for extracting failed files"
```

---

## Task 4: Smart Matching Logic - Match Failed Files to Jobs

**Files:**
- Create: `pt4_matcher.py`
- Create: `tests/test_pt4_matcher.py`
- Modify: `database.py` (add helper queries)

**Step 1: Write the failing test**

Create: `tests/test_pt4_matcher.py`

```python
import pytest
import json
from pathlib import Path
from database import init_db, create_job, add_file
from pt4_matcher import match_failed_files_to_jobs, FailedFileMatch

def test_match_failed_files_by_table_number():
    """Test matching PT4 failed files to original jobs by table number"""
    init_db()

    # Create a job with files
    job_id = create_job()

    # Add uploaded files (simulating original uploads)
    add_file(job_id, "46798.txt", "txt", f"/storage/uploads/{job_id}/txt/46798.txt")
    add_file(job_id, "screenshot_46798_001.png", "screenshot", f"/storage/uploads/{job_id}/screenshots/screenshot_46798_001.png")
    add_file(job_id, "screenshot_46798_002.png", "screenshot", f"/storage/uploads/{job_id}/screenshots/screenshot_46798_002.png")

    # Failed files from PT4 log
    failed_files = [{
        'filename': '46798_resolved.txt',
        'table_number': 46798,
        'error_count': 5,
        'errors': ['Error 1', 'Error 2']
    }]

    # Match failed files to jobs
    matches = match_failed_files_to_jobs(failed_files)

    assert len(matches) == 1

    match = matches[0]
    assert match.filename == '46798_resolved.txt'
    assert match.table_number == 46798
    assert match.matched_job_id == job_id
    assert match.original_txt_path == f"/storage/uploads/{job_id}/txt/46798.txt"
    assert match.processed_txt_path == f"/storage/outputs/{job_id}/46798_resolved.txt"
    assert len(match.screenshot_paths) == 2
    assert all('46798' in p for p in match.screenshot_paths)

def test_match_failed_files_no_match():
    """Test when failed file has no matching job"""
    init_db()

    failed_files = [{
        'filename': '99999_resolved.txt',
        'table_number': 99999,
        'error_count': 1,
        'errors': ['Error']
    }]

    matches = match_failed_files_to_jobs(failed_files)

    assert len(matches) == 1
    match = matches[0]
    assert match.matched_job_id is None
    assert match.original_txt_path is None
    assert len(match.screenshot_paths) == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pt4_matcher.py -v`

Expected: FAIL with "ModuleNotFoundError: No module named 'pt4_matcher'"

**Step 3: Add database helper functions**

Modify: `database.py` after `create_pt4_failed_file()`:

```python
def get_files_by_table_number(table_number: int) -> List[Dict]:
    """
    Get all files associated with a table number across all jobs

    Args:
        table_number: Table number to search for (e.g., 46798)

    Returns:
        List of dicts with job_id, filename, file_type, file_path
    """
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT job_id, filename, file_type, file_path
            FROM files
            WHERE filename LIKE ? OR filename LIKE ?
            ORDER BY job_id DESC, uploaded_at DESC
            """,
            (f"{table_number}.txt", f"%{table_number}%")
        )
        return [dict(row) for row in cursor.fetchall()]


def get_job_outputs_path(job_id: int) -> Optional[str]:
    """Get the outputs directory path for a job"""
    from pathlib import Path
    outputs_path = Path("storage/outputs") / str(job_id)
    if outputs_path.exists():
        return str(outputs_path)
    return None
```

**Step 4: Write matcher implementation**

Create: `pt4_matcher.py`

```python
"""
Smart matcher for PT4 failed files to original GGRevealer jobs
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path
import json

from database import get_files_by_table_number, get_job_outputs_path


@dataclass
class FailedFileMatch:
    """Match result for a PT4 failed file"""
    filename: str
    table_number: Optional[int]
    error_count: int
    errors: List[str]
    matched_job_id: Optional[int]
    original_txt_path: Optional[str]
    processed_txt_path: Optional[str]
    screenshot_paths: List[str]


def match_failed_files_to_jobs(failed_files: List[Dict]) -> List[FailedFileMatch]:
    """
    Match PT4 failed files to original GGRevealer jobs

    Strategy:
    1. Extract table number from failed filename (e.g., 46798_resolved.txt → 46798)
    2. Search database for files matching that table number
    3. Find original TXT input (46798.txt)
    4. Find processed output (46798_resolved.txt in outputs/)
    5. Find all screenshots containing that table number

    Args:
        failed_files: List of dicts from PT4 parser

    Returns:
        List of FailedFileMatch objects with matched paths
    """
    matches = []

    for failed_file in failed_files:
        filename = failed_file['filename']
        table_number = failed_file['table_number']
        error_count = failed_file['error_count']
        errors = failed_file['errors']

        # Initialize match with no associations
        match = FailedFileMatch(
            filename=filename,
            table_number=table_number,
            error_count=error_count,
            errors=errors,
            matched_job_id=None,
            original_txt_path=None,
            processed_txt_path=None,
            screenshot_paths=[]
        )

        # If no table number, can't match
        if table_number is None:
            matches.append(match)
            continue

        # Search for files with this table number
        files = get_files_by_table_number(table_number)

        if not files:
            matches.append(match)
            continue

        # Group files by job_id (prefer most recent job)
        job_files = {}
        for file in files:
            job_id = file['job_id']
            if job_id not in job_files:
                job_files[job_id] = []
            job_files[job_id].append(file)

        # Use most recent job (highest job_id)
        most_recent_job_id = max(job_files.keys())
        job_file_list = job_files[most_recent_job_id]

        # Extract paths
        match.matched_job_id = most_recent_job_id

        # Find original TXT (input)
        for file in job_file_list:
            if file['file_type'] == 'txt' and f"{table_number}.txt" in file['filename']:
                match.original_txt_path = file['file_path']
                break

        # Find processed TXT (output)
        outputs_path = get_job_outputs_path(most_recent_job_id)
        if outputs_path:
            processed_path = Path(outputs_path) / f"{table_number}_resolved.txt"
            if processed_path.exists():
                match.processed_txt_path = str(processed_path)
            else:
                # Try fallado version
                fallado_path = Path(outputs_path) / f"{table_number}_fallado.txt"
                if fallado_path.exists():
                    match.processed_txt_path = str(fallado_path)

        # Find screenshots
        for file in job_file_list:
            if file['file_type'] == 'screenshot' and str(table_number) in file['filename']:
                match.screenshot_paths.append(file['file_path'])

        matches.append(match)

    return matches
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_pt4_matcher.py -v`

Expected: PASS (all 2 tests)

**Step 6: Commit**

```bash
git add pt4_matcher.py tests/test_pt4_matcher.py database.py
git commit -m "feat: add smart matcher for PT4 failed files to original jobs"
```

---

## Task 5: Backend API - Upload PT4 Log Endpoint

**Files:**
- Modify: `main.py` (add new endpoint)
- Create: `tests/test_pt4_api.py`

**Step 1: Write the failing test**

Create: `tests/test_pt4_api.py`

```python
import pytest
from fastapi.testclient import TestClient
from main import app
from database import init_db, create_job, add_file

client = TestClient(app)

def test_upload_pt4_log_success():
    """Test uploading PT4 log and parsing failed files"""
    init_db()

    # Create a job with files first
    job_id = create_job()
    add_file(job_id, "46798.txt", "txt", f"/storage/uploads/{job_id}/txt/46798.txt")
    add_file(job_id, "screenshot_46798_001.png", "screenshot", f"/storage/uploads/{job_id}/screenshots/screenshot_46798_001.png")

    pt4_log = """06:58:32 pm: Importing files from disk...
06:58:32 pm: Import file: /Users/nicodelgadob/Downloads/resolved_hands_35 (1)/46798_resolved.txt
06:58:32 pm: Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247438352) (Line #5)
06:58:32 pm:         + Complete (0 hands, 0 summaries, 1 error, 0 duplicates)
06:58:32 pm: Import complete. 0 hands in 1 file were imported. (1 error, 0 duplicates)"""

    response = client.post(
        "/api/pt4-log/upload",
        data={"log_text": pt4_log, "job_id": job_id}
    )

    assert response.status_code == 200
    data = response.json()

    assert data['success'] is True
    assert data['attempt_id'] is not None
    assert data['total_files'] == 1
    assert data['failed_files_count'] == 1
    assert len(data['failed_files']) == 1

    failed_file = data['failed_files'][0]
    assert failed_file['filename'] == '46798_resolved.txt'
    assert failed_file['table_number'] == 46798
    assert failed_file['matched_job_id'] == job_id
    assert failed_file['original_txt_path'] is not None
    assert len(failed_file['screenshot_paths']) > 0

def test_upload_pt4_log_no_failures():
    """Test uploading PT4 log with no errors"""
    init_db()

    pt4_log = """06:58:32 pm: Importing files from disk...
06:58:32 pm: Import file: /path/43746_resolved.txt
06:58:32 pm:         + Complete (9 hands, 0 summaries, 0 errors, 0 duplicates)
06:58:32 pm: Import complete. 9 hands in 1 file were imported. (0 errors, 0 duplicates)"""

    response = client.post(
        "/api/pt4-log/upload",
        data={"log_text": pt4_log}
    )

    assert response.status_code == 200
    data = response.json()

    assert data['success'] is True
    assert data['failed_files_count'] == 0
    assert len(data['failed_files']) == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pt4_api.py::test_upload_pt4_log_success -v`

Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Add upload PT4 log endpoint**

Modify: `main.py` after `/api/debug/{job_id}/generate-prompt` endpoint (around line 740):

```python
@app.post("/api/pt4-log/upload")
async def upload_pt4_log(
    log_text: str = Form(...),
    job_id: Optional[int] = Form(None)
):
    """
    Upload and parse PokerTracker 4 import log

    This endpoint:
    1. Parses PT4 log to extract failed files
    2. Matches failed files to original jobs by table number
    3. Stores PT4 import attempt and failed files in database
    4. Returns matched files with paths to original TXT, processed TXT, and screenshots
    """
    from pt4_parser import parse_pt4_import_log
    from pt4_matcher import match_failed_files_to_jobs
    from database import create_pt4_import_attempt, create_pt4_failed_file
    import json

    # Parse PT4 log
    parsed_result = parse_pt4_import_log(log_text)

    if not parsed_result:
        raise HTTPException(status_code=400, detail="Invalid PT4 log format")

    # Match failed files to jobs
    matches = match_failed_files_to_jobs(parsed_result.failed_files)

    # Create PT4 import attempt record (use provided job_id if available)
    attempt_id = create_pt4_import_attempt(
        job_id=job_id if job_id else (matches[0].matched_job_id if matches else None),
        import_log=log_text,
        total_files=parsed_result.total_files,
        failed_files_count=len(parsed_result.failed_files)
    )

    # Save each failed file match
    failed_files_response = []
    for match in matches:
        # Store in database
        failed_file_id = create_pt4_failed_file(
            pt4_import_attempt_id=attempt_id,
            filename=match.filename,
            table_number=match.table_number,
            error_count=match.error_count,
            error_details=json.dumps(match.errors),
            associated_job_id=match.matched_job_id,
            associated_original_txt_path=match.original_txt_path,
            associated_processed_txt_path=match.processed_txt_path,
            associated_screenshot_paths=json.dumps(match.screenshot_paths)
        )

        # Build response
        failed_files_response.append({
            'id': failed_file_id,
            'filename': match.filename,
            'table_number': match.table_number,
            'error_count': match.error_count,
            'errors': match.errors,
            'matched_job_id': match.matched_job_id,
            'original_txt_path': match.original_txt_path,
            'processed_txt_path': match.processed_txt_path,
            'screenshot_paths': match.screenshot_paths
        })

    return {
        'success': True,
        'attempt_id': attempt_id,
        'total_files': parsed_result.total_files,
        'total_hands_imported': parsed_result.total_hands_imported,
        'total_errors': parsed_result.total_errors,
        'failed_files_count': len(parsed_result.failed_files),
        'failed_files': failed_files_response
    }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pt4_api.py::test_upload_pt4_log_success -v`

Expected: PASS

**Step 5: Commit**

```bash
git add main.py tests/test_pt4_api.py
git commit -m "feat: add API endpoint for uploading PT4 import logs"
```

---

## Task 6: Backend API - Get Failed Files Endpoint

**Files:**
- Modify: `main.py` (add endpoint)
- Modify: `database.py` (add query functions)
- Modify: `tests/test_pt4_api.py` (add test)

**Step 1: Write the failing test**

Add to `tests/test_pt4_api.py`:

```python
def test_get_failed_files_for_job():
    """Test retrieving all failed files for a job"""
    init_db()

    # Create job and upload PT4 log
    job_id = create_job()
    add_file(job_id, "46798.txt", "txt", f"/storage/uploads/{job_id}/txt/46798.txt")

    pt4_log = """06:58:32 pm: Import file: /path/46798_resolved.txt
06:58:32 pm: Error: GG Poker: Duplicate player
06:58:32 pm:         + Complete (0 hands, 0 summaries, 1 error, 0 duplicates)"""

    # Upload log
    upload_response = client.post(
        "/api/pt4-log/upload",
        data={"log_text": pt4_log, "job_id": job_id}
    )
    assert upload_response.status_code == 200

    # Get failed files for job
    response = client.get(f"/api/pt4-log/failed-files/{job_id}")

    assert response.status_code == 200
    data = response.json()

    assert len(data['failed_files']) == 1
    assert data['failed_files'][0]['filename'] == '46798_resolved.txt'
    assert data['app_failures'] is not None

def test_get_all_failed_files():
    """Test retrieving all failed files across all jobs"""
    init_db()

    response = client.get("/api/pt4-log/failed-files")

    assert response.status_code == 200
    data = response.json()
    assert 'failed_files' in data
    assert 'total_count' in data
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pt4_api.py::test_get_failed_files_for_job -v`

Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Add database query functions**

Modify: `database.py` after `get_files_by_table_number()`:

```python
def get_pt4_failed_files_for_job(job_id: int) -> List[Dict]:
    """
    Get all PT4 failed files associated with a job

    Args:
        job_id: Job ID to filter by

    Returns:
        List of dicts with failed file details
    """
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT pff.*, pia.import_log, pia.parsed_at
            FROM pt4_failed_files pff
            JOIN pt4_import_attempts pia ON pff.pt4_import_attempt_id = pia.id
            WHERE pff.associated_job_id = ?
            ORDER BY pff.created_at DESC
            """,
            (job_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_all_pt4_failed_files() -> List[Dict]:
    """Get all PT4 failed files across all jobs"""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT pff.*, pia.import_log, pia.parsed_at, j.created_at as job_created_at
            FROM pt4_failed_files pff
            JOIN pt4_import_attempts pia ON pff.pt4_import_attempt_id = pia.id
            LEFT JOIN jobs j ON pff.associated_job_id = j.id
            ORDER BY pff.created_at DESC
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def get_app_failed_files_for_job(job_id: int) -> List[Dict]:
    """
    Get app-detected failed files (with unmapped IDs) for a job

    Args:
        job_id: Job ID to query

    Returns:
        List of dicts with table name and unmapped_ids
    """
    result = get_result(job_id)
    if not result or not result.get('stats_json'):
        return []

    import json
    stats = json.loads(result['stats_json'])

    return stats.get('failed_files', [])
```

**Step 4: Add GET endpoints**

Modify: `main.py` after `/api/pt4-log/upload`:

```python
@app.get("/api/pt4-log/failed-files/{job_id}")
async def get_failed_files_for_job(job_id: int):
    """
    Get all failed files for a specific job

    Returns both:
    - PT4 import failures (user-reported)
    - App-detected failures (unmapped IDs from processing)
    """
    from database import get_pt4_failed_files_for_job, get_app_failed_files_for_job
    import json

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get PT4 failures
    pt4_failures = get_pt4_failed_files_for_job(job_id)

    # Parse JSON fields
    for failure in pt4_failures:
        if failure.get('error_details'):
            failure['errors'] = json.loads(failure['error_details'])
        if failure.get('associated_screenshot_paths'):
            failure['screenshot_paths'] = json.loads(failure['associated_screenshot_paths'])

    # Get app-detected failures
    app_failures = get_app_failed_files_for_job(job_id)

    return {
        'job_id': job_id,
        'pt4_failures': pt4_failures,
        'app_failures': app_failures,
        'total_pt4_failures': len(pt4_failures),
        'total_app_failures': len(app_failures)
    }


@app.get("/api/pt4-log/failed-files")
async def get_all_failed_files():
    """
    Get all failed files across all jobs

    Useful for global "Failed Files Recovery" view
    """
    from database import get_all_pt4_failed_files
    import json

    failed_files = get_all_pt4_failed_files()

    # Parse JSON fields
    for failure in failed_files:
        if failure.get('error_details'):
            failure['errors'] = json.loads(failure['error_details'])
        if failure.get('associated_screenshot_paths'):
            failure['screenshot_paths'] = json.loads(failure['associated_screenshot_paths'])

    return {
        'failed_files': failed_files,
        'total_count': len(failed_files)
    }
```

**Step 5: Run test to verify it passes**

Run: `pytest tests/test_pt4_api.py -v`

Expected: PASS (all tests)

**Step 6: Commit**

```bash
git add main.py database.py tests/test_pt4_api.py
git commit -m "feat: add API endpoints for retrieving failed files"
```

---

## Task 7: Frontend - Add Sidebar Navigation Link

**Files:**
- Modify: `templates/index.html:41-53` (sidebar navigation)
- Modify: `static/js/app.js` (add navigation handler)

**Step 1: Add sidebar link**

Modify: `templates/index.html` in sidebar navigation (around line 50):

```html
<a href="#" class="sidebar-link" id="nav-history">
    <i class="bi bi-clock-history"></i>
    <span>Historial</span>
</a>
<a href="#" class="sidebar-link" id="nav-failed-files">
    <i class="bi bi-exclamation-triangle"></i>
    <span>Archivos Fallidos</span>
</a>
```

**Step 2: Add click handler in app.js**

Modify: `static/js/app.js` after history navigation handler (around line 150):

```javascript
// Failed Files navigation
document.getElementById('nav-failed-files').addEventListener('click', (e) => {
    e.preventDefault();
    showFailedFilesView();
    updateActiveNavLink('nav-failed-files');
});

function updateActiveNavLink(activeId) {
    // Remove active class from all links
    document.querySelectorAll('.sidebar-link').forEach(link => {
        link.classList.remove('active');
    });
    // Add active class to clicked link
    document.getElementById(activeId).classList.add('active');
}
```

**Step 3: Test manually**

Run: `python main.py`

Open: http://localhost:8000/app

Expected: Sidebar shows "Archivos Fallidos" link, clicking it updates active state

**Step 4: Commit**

```bash
git add templates/index.html static/js/app.js
git commit -m "feat: add 'Archivos Fallidos' sidebar navigation link"
```

---

## Task 8: Frontend - Failed Files View Container

**Files:**
- Modify: `templates/index.html` (add new view container)
- Modify: `static/css/styles.css` (add styles)

**Step 1: Add failed files view container**

Modify: `templates/index.html` after history view container (around line 500):

```html
<!-- Failed Files Recovery View -->
<div id="failed-files-view" class="view-container" style="display: none;">
    <div class="container-fluid">
        <div class="row mb-4">
            <div class="col">
                <h2><i class="bi bi-exclamation-triangle text-warning"></i> Recuperación de Archivos Fallidos</h2>
                <p class="text-muted">Sube el log de importación de PokerTracker para identificar archivos que fallaron y encontrar sus screenshots asociados.</p>
            </div>
        </div>

        <!-- Upload PT4 Log Section -->
        <div class="row mb-4">
            <div class="col-md-8">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="bi bi-upload"></i> Subir Log de PokerTracker</h5>
                    </div>
                    <div class="card-body">
                        <form id="pt4-log-form">
                            <div class="mb-3">
                                <label for="pt4-log-text" class="form-label">Pega el log de importación de PT4:</label>
                                <textarea
                                    class="form-control font-monospace"
                                    id="pt4-log-text"
                                    rows="10"
                                    placeholder="06:58:32 pm: Import file: /path/46798_resolved.txt
06:58:32 pm: Error: GG Poker: Duplicate player...
06:58:32 pm:         + Complete (0 hands, 0 summaries, 5 errors, 0 duplicates)"
                                    required
                                ></textarea>
                            </div>
                            <div class="mb-3">
                                <label for="pt4-job-id" class="form-label">Job ID (opcional):</label>
                                <input
                                    type="number"
                                    class="form-control"
                                    id="pt4-job-id"
                                    placeholder="Dejar vacío para auto-detectar"
                                >
                                <small class="text-muted">Si conoces el Job ID que generó estos archivos, ingrésalo para mejor precisión.</small>
                            </div>
                            <button type="submit" class="btn btn-primary">
                                <i class="bi bi-search"></i> Analizar Log
                            </button>
                        </form>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="card bg-light">
                    <div class="card-body">
                        <h6><i class="bi bi-info-circle"></i> ¿Cómo funciona?</h6>
                        <ol class="small">
                            <li>Copia el log de importación de PokerTracker</li>
                            <li>Pégalo en el área de texto</li>
                            <li>El sistema extrae los archivos que fallaron</li>
                            <li>Busca automáticamente los screenshots asociados</li>
                            <li>Muestra todo en una tabla para corrección manual</li>
                        </ol>
                    </div>
                </div>
            </div>
        </div>

        <!-- Failed Files Table -->
        <div class="row" id="failed-files-results" style="display: none;">
            <div class="col">
                <div class="card">
                    <div class="card-header">
                        <h5><i class="bi bi-table"></i> Archivos Fallidos Detectados</h5>
                    </div>
                    <div class="card-body">
                        <div class="table-responsive">
                            <table class="table table-hover">
                                <thead>
                                    <tr>
                                        <th>Archivo</th>
                                        <th>Mesa</th>
                                        <th>Errores</th>
                                        <th>TXT Original</th>
                                        <th>TXT Procesado</th>
                                        <th>Screenshots</th>
                                    </tr>
                                </thead>
                                <tbody id="failed-files-tbody">
                                    <!-- Populated by JavaScript -->
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
```

**Step 2: Add styles**

Modify: `static/css/styles.css`:

```css
/* Failed Files View */
#failed-files-view .view-container {
    padding: 2rem;
}

#failed-files-view .font-monospace {
    font-size: 0.9rem;
}

#failed-files-view .table {
    font-size: 0.9rem;
}

#failed-files-view .btn-download {
    padding: 0.25rem 0.5rem;
    font-size: 0.875rem;
}

.error-badge {
    background-color: #dc3545;
    color: white;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-size: 0.875rem;
}
```

**Step 3: Add view switching function**

Modify: `static/js/app.js`:

```javascript
function showFailedFilesView() {
    // Hide all views
    document.getElementById('upload-view').style.display = 'none';
    document.getElementById('history-view').style.display = 'none';
    document.getElementById('reprocess-view').style.display = 'none';

    // Show failed files view
    document.getElementById('failed-files-view').style.display = 'block';
}
```

**Step 4: Test manually**

Run app and click "Archivos Fallidos" link

Expected: Shows upload PT4 log form with textarea

**Step 5: Commit**

```bash
git add templates/index.html static/css/styles.css static/js/app.js
git commit -m "feat: add failed files recovery view with PT4 log upload form"
```

---

## Task 9: Frontend - PT4 Log Submission Handler

**Files:**
- Modify: `static/js/app.js` (add form handler and API call)

**Step 1: Add form submission handler**

Modify: `static/js/app.js` after `showFailedFilesView()`:

```javascript
// PT4 Log Form Submission
document.getElementById('pt4-log-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const logText = document.getElementById('pt4-log-text').value.trim();
    const jobId = document.getElementById('pt4-job-id').value.trim();

    if (!logText) {
        alert('Por favor ingresa el log de PokerTracker');
        return;
    }

    // Disable submit button
    const submitBtn = e.target.querySelector('button[type="submit"]');
    const originalText = submitBtn.innerHTML;
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Analizando...';

    try {
        // Upload PT4 log
        const formData = new FormData();
        formData.append('log_text', logText);
        if (jobId) {
            formData.append('job_id', jobId);
        }

        const response = await fetch('/api/pt4-log/upload', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Error al analizar el log');
        }

        const data = await response.json();

        // Display results
        displayFailedFilesResults(data);

        // Show success message
        showToast('success', `${data.failed_files_count} archivo(s) fallido(s) detectado(s)`);

    } catch (error) {
        console.error('Error uploading PT4 log:', error);
        showToast('error', 'Error al analizar el log de PokerTracker');
    } finally {
        // Re-enable submit button
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }
});

function displayFailedFilesResults(data) {
    const resultsDiv = document.getElementById('failed-files-results');
    const tbody = document.getElementById('failed-files-tbody');

    // Clear previous results
    tbody.innerHTML = '';

    if (data.failed_files_count === 0) {
        tbody.innerHTML = '<tr><td colspan="6" class="text-center">No se detectaron archivos fallidos</td></tr>';
        resultsDiv.style.display = 'block';
        return;
    }

    // Populate table
    data.failed_files.forEach(file => {
        const row = document.createElement('tr');

        // Filename
        const filenameCell = document.createElement('td');
        filenameCell.textContent = file.filename;
        row.appendChild(filenameCell);

        // Table number
        const tableCell = document.createElement('td');
        tableCell.textContent = file.table_number || 'N/A';
        row.appendChild(tableCell);

        // Error count
        const errorCell = document.createElement('td');
        errorCell.innerHTML = `<span class="error-badge">${file.error_count} error(es)</span>`;
        row.appendChild(errorCell);

        // Original TXT
        const originalCell = document.createElement('td');
        if (file.original_txt_path) {
            originalCell.innerHTML = `<button class="btn btn-sm btn-outline-primary btn-download" onclick="downloadFile('${file.original_txt_path}')">
                <i class="bi bi-download"></i> Descargar
            </button>`;
        } else {
            originalCell.innerHTML = '<span class="text-muted">No encontrado</span>';
        }
        row.appendChild(originalCell);

        // Processed TXT
        const processedCell = document.createElement('td');
        if (file.processed_txt_path) {
            processedCell.innerHTML = `<button class="btn btn-sm btn-outline-primary btn-download" onclick="downloadFile('${file.processed_txt_path}')">
                <i class="bi bi-download"></i> Descargar
            </button>`;
        } else {
            processedCell.innerHTML = '<span class="text-muted">No encontrado</span>';
        }
        row.appendChild(processedCell);

        // Screenshots
        const screenshotsCell = document.createElement('td');
        if (file.screenshot_paths && file.screenshot_paths.length > 0) {
            screenshotsCell.innerHTML = `<span class="badge bg-info">${file.screenshot_paths.length} screenshot(s)</span>
                <button class="btn btn-sm btn-link" onclick="showScreenshots(${JSON.stringify(file.screenshot_paths).replace(/"/g, '&quot;')})">
                    Ver
                </button>`;
        } else {
            screenshotsCell.innerHTML = '<span class="text-muted">No encontrados</span>';
        }
        row.appendChild(screenshotsCell);

        tbody.appendChild(row);
    });

    // Show results table
    resultsDiv.style.display = 'block';

    // Scroll to results
    resultsDiv.scrollIntoView({ behavior: 'smooth' });
}

function downloadFile(filepath) {
    // Create temporary link to download file
    const link = document.createElement('a');
    link.href = '/api/download-file?path=' + encodeURIComponent(filepath);
    link.download = filepath.split('/').pop();
    link.click();
}

function showScreenshots(screenshotPaths) {
    // Create modal to display screenshots
    const modal = document.createElement('div');
    modal.className = 'modal fade';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Screenshots Asociados</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    ${screenshotPaths.map(path => `
                        <div class="mb-3">
                            <p class="small text-muted">${path.split('/').pop()}</p>
                            <img src="/api/screenshot/${encodeURIComponent(path)}" class="img-fluid border" alt="Screenshot">
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
    const bsModal = new bootstrap.Modal(modal);
    bsModal.show();

    // Clean up when closed
    modal.addEventListener('hidden.bs.modal', () => {
        modal.remove();
    });
}

function showToast(type, message) {
    // Simple toast notification (reuse existing if available)
    alert(message); // Replace with proper toast implementation
}
```

**Step 2: Test manually**

Run app, go to "Archivos Fallidos", paste sample PT4 log, submit

Expected: Table populates with failed files, download buttons work

**Step 3: Commit**

```bash
git add static/js/app.js
git commit -m "feat: add PT4 log submission handler and results display"
```

---

## Task 10: Backend API - File Download Endpoints

**Files:**
- Modify: `main.py` (add file download and screenshot view endpoints)

**Step 1: Add file download endpoint**

Modify: `main.py` after failed files endpoints:

```python
@app.get("/api/download-file")
async def download_file(path: str):
    """
    Download a file by path

    Security: Only allow downloads from storage/ directory
    """
    from pathlib import Path

    file_path = Path(path)

    # Security check: ensure path is within storage directory
    storage_abs = Path("storage").resolve()
    file_abs = file_path.resolve()

    if not str(file_abs).startswith(str(storage_abs)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type='application/octet-stream'
    )


@app.get("/api/screenshot/{path:path}")
async def view_screenshot(path: str):
    """
    View a screenshot image

    Security: Only allow viewing from storage/ directory
    """
    from pathlib import Path

    file_path = Path(path)

    # Security check
    storage_abs = Path("storage").resolve()
    file_abs = file_path.resolve()

    if not str(file_abs).startswith(str(storage_abs)):
        raise HTTPException(status_code=403, detail="Access denied")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        media_type='image/png'
    )
```

**Step 2: Test manually**

Try downloading a file: `http://localhost:8000/api/download-file?path=storage/uploads/1/txt/46798.txt`

Expected: File downloads

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add file download and screenshot view endpoints"
```

---

## Task 11: Integration - Link Failed Files to Job History

**Files:**
- Modify: `templates/index.html` (add failed files section to job details)
- Modify: `static/js/app.js` (load failed files when viewing job)

**Step 1: Add failed files section to job details modal**

Modify: `templates/index.html` in job details modal (around line 450):

Add after statistics section:

```html
<!-- Failed Files Section -->
<div class="mt-4" id="job-failed-files-section" style="display: none;">
    <h6><i class="bi bi-exclamation-triangle text-warning"></i> Archivos Fallidos</h6>
    <div class="alert alert-warning">
        <strong>PT4 Failures:</strong> <span id="job-pt4-failures-count">0</span> archivo(s)<br>
        <strong>App Failures:</strong> <span id="job-app-failures-count">0</span> archivo(s)
    </div>
    <button class="btn btn-sm btn-outline-primary" onclick="viewJobFailedFiles()">
        Ver Detalles
    </button>
</div>
```

**Step 2: Add function to load failed files for job**

Modify: `static/js/app.js`:

```javascript
async function loadJobFailedFiles(jobId) {
    try {
        const response = await fetch(`/api/pt4-log/failed-files/${jobId}`);
        if (!response.ok) return;

        const data = await response.json();

        const pt4Count = data.total_pt4_failures || 0;
        const appCount = data.total_app_failures || 0;

        if (pt4Count > 0 || appCount > 0) {
            document.getElementById('job-failed-files-section').style.display = 'block';
            document.getElementById('job-pt4-failures-count').textContent = pt4Count;
            document.getElementById('job-app-failures-count').textContent = appCount;

            // Store for later viewing
            window.currentJobFailedFiles = data;
        }
    } catch (error) {
        console.error('Error loading failed files:', error);
    }
}

function viewJobFailedFiles() {
    if (!window.currentJobFailedFiles) return;

    // Switch to failed files view and populate with this job's data
    showFailedFilesView();
    updateActiveNavLink('nav-failed-files');

    // Display the failed files
    displayFailedFilesResults({
        failed_files_count: window.currentJobFailedFiles.total_pt4_failures,
        failed_files: window.currentJobFailedFiles.pt4_failures
    });
}
```

**Step 3: Call loadJobFailedFiles when viewing job details**

Modify existing job details display function to call:

```javascript
// In existing showJobDetails function
await loadJobFailedFiles(jobId);
```

**Step 4: Test manually**

View a job with failed files in history

Expected: Shows failed files count and "Ver Detalles" button

**Step 5: Commit**

```bash
git add templates/index.html static/js/app.js
git commit -m "feat: integrate failed files display into job history view"
```

---

## Task 12: Documentation & Final Testing

**Files:**
- Modify: `CLAUDE.md` (add feature documentation)
- Create: `docs/pt4-failed-files-recovery.md` (user guide)

**Step 1: Update CLAUDE.md**

Modify: `CLAUDE.md` add after "Recent Features & Enhancements" section:

```markdown
### PT4 Failed Files Recovery (Nov 2025) 🆕
**Feature**: PokerTracker import log parsing and smart file matching
- Upload PT4 import logs to identify files rejected during import
- Automatic extraction of failed filenames and error messages
- Smart matching algorithm connects failed files to original jobs by table number
- Display failed files with associated screenshots and original/processed TXT files
- Two-phase failure tracking: app-detected (unmapped IDs) + user-reported (PT4 errors)
- **Endpoint**: `POST /api/pt4-log/upload` - Upload and parse PT4 log
- **Endpoint**: `GET /api/pt4-log/failed-files/{job_id}` - Get failed files for specific job
- **Endpoint**: `GET /api/pt4-log/failed-files` - Get all failed files across jobs
- **Implementation**: `pt4_parser.py`, `pt4_matcher.py`, `database.py` (new tables)
```

**Step 2: Create user guide**

Create: `docs/pt4-failed-files-recovery.md`

```markdown
# PokerTracker Failed Files Recovery Guide

## Overview

The PT4 Failed Files Recovery feature helps you quickly identify and fix files that failed during PokerTracker import.

## How It Works

1. **Process files normally** with GGRevealer
2. **Import to PokerTracker** and copy the import log
3. **Upload the log** to GGRevealer's "Archivos Fallidos" section
4. **View results** with automatic matching to original screenshots

## Step-by-Step Guide

### Step 1: Copy PT4 Import Log

When PokerTracker completes import, copy the entire log output from the PT4 console window.

Example log:
```
06:58:32 pm: Import file: /path/46798_resolved.txt
06:58:32 pm: Error: GG Poker: Duplicate player: TuichAAreko
06:58:32 pm:         + Complete (0 hands, 0 summaries, 5 errors, 0 duplicates)
```

### Step 2: Upload Log to GGRevealer

1. Click **"Archivos Fallidos"** in the sidebar
2. Paste the log into the text area
3. (Optional) Enter Job ID if you know which job generated these files
4. Click **"Analizar Log"**

### Step 3: View Results

The system displays a table with:
- **Archivo**: Failed filename
- **Mesa**: Table number
- **Errores**: Error count
- **TXT Original**: Download button for original input file
- **TXT Procesado**: Download button for processed output file
- **Screenshots**: View associated screenshots

### Step 4: Manual Correction

1. Click "Descargar" to get the original TXT and processed TXT files
2. Click "Ver" to view associated screenshots
3. Manually correct the processed file using screenshot information
4. Re-import corrected file to PokerTracker

## Common Errors

### "Duplicate player" Error

**Cause**: Screenshot was matched to wrong hand, causing same player name in multiple seats

**Fix**: Review screenshot, verify it matches the hand, manually correct player names

### "No encontrado" (Not found)

**Cause**: Table number doesn't match any uploaded files

**Solution**: Ensure you're using the correct Job ID, or upload was incomplete

## Tips

- Keep Job IDs organized (note which job corresponds to which PT4 import)
- Upload PT4 logs immediately after import to maintain context
- Use "Ver Detalles" button in job history to see job-specific failures
```

**Step 3: Run full test suite**

Run: `pytest tests/ -v`

Expected: All tests pass

**Step 4: Manual end-to-end test**

1. Start app: `python main.py`
2. Upload files and process a job
3. Simulate PT4 import with errors
4. Upload PT4 log to "Archivos Fallidos"
5. Verify table displays correctly
6. Download files and view screenshots

**Step 5: Commit**

```bash
git add CLAUDE.md docs/pt4-failed-files-recovery.md
git commit -m "docs: add PT4 failed files recovery feature documentation"
```

---

## Summary

This implementation plan provides:
1. **Database schema** for tracking PT4 import attempts and failed files
2. **PT4 log parser** for extracting failed filenames and errors
3. **Smart matcher** for connecting failed files to original jobs
4. **Backend API** for uploading logs and retrieving failed files
5. **Frontend UI** for user-friendly file recovery workflow
6. **Integration** with existing job history view

**Key Features**:
- Two-phase failure tracking (app + PT4)
- Automatic screenshot matching by table number
- Direct file downloads from UI
- Modal screenshot viewer
- Comprehensive error details

**Testing**:
- Unit tests for parser, matcher, database functions
- Integration tests for API endpoints
- Manual end-to-end testing

**Total Estimated Time**: ~4-6 hours (assuming TDD workflow with frequent commits)
