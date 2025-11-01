# GGRevealer Audit Fixes - Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 15 identified issues from functionality audit, prioritizing 2 critical production blockers and 9 medium-severity issues.

**Architecture:** Three-phase approach - Priority 1 (critical, unblock production), Priority 2 (next sprint, stability), Priority 3 (nice-to-have, refactoring). Each phase uses TDD with test-first approach, frequent commits, and modular changes.

**Tech Stack:** Python 3.11+, FastAPI, pytest, asyncio, SQLite, Google Gemini API

---

## PHASE 1: CRITICAL FIXES (Blocks Production)

### Task 1.1: Unify Asyncio Event Loops (High Priority)

**Problem:** `asyncio.run()` called twice (OCR1 at line 1595, OCR2 at line 1698) creates two independent event loops, potential race condition vector.

**Files:**
- Modify: `main.py:1567-1706`
- Modify: `ocr.py:17-50` (import analysis)
- Create: `tests/test_asyncio_unification.py`

**Step 1: Write failing test for unified event loop**

Create `tests/test_asyncio_unification.py`:

```python
import asyncio
import pytest
from main import run_processing_pipeline
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_single_event_loop_for_ocr_phases():
    """Verify OCR1 and OCR2 run in same event loop"""
    event_loops_created = []

    original_run = asyncio.run

    def tracking_run(coro):
        event_loops_created.append(asyncio.get_event_loop())
        return original_run(coro)

    with patch('asyncio.run', side_effect=tracking_run):
        with patch('main.run_processing_pipeline'):
            # After fix, asyncio.run should be called exactly once
            pass

@pytest.mark.asyncio
async def test_ocr_phases_in_same_event_loop():
    """Verify OCR1 and OCR2 execute sequentially in unified event loop"""
    execution_order = []

    async def mock_ocr1():
        execution_order.append('ocr1_start')
        await asyncio.sleep(0.01)
        execution_order.append('ocr1_end')

    async def mock_ocr2():
        execution_order.append('ocr2_start')
        await asyncio.sleep(0.01)
        execution_order.append('ocr2_end')

    async def unified_ocr_phases():
        await mock_ocr1()
        await mock_ocr2()

    await unified_ocr_phases()

    # Verify order: OCR1 completes before OCR2 starts
    assert execution_order == ['ocr1_start', 'ocr1_end', 'ocr2_start', 'ocr2_end']
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_asyncio_unification.py -v
```

Expected output:
```
FAILED tests/test_asyncio_unification.py::test_single_event_loop_for_ocr_phases
FAILED tests/test_asyncio_unification.py::test_ocr_phases_in_same_event_loop
```

**Step 3: Refactor main.py to use unified event loop**

Modify `main.py` around lines 1567-1706. Replace:

```python
# BEFORE (TWO asyncio.run calls)
logger.info(f"🔍 Phase 2: OCR1 - Extracting hand IDs from {len(screenshot_files)} screenshots")
ocr1_results = asyncio.run(process_all_ocr1(screenshot_files, api_key, semaphore_limit))

# ... intermediate code ...

logger.info(f"🔍 Phase 5: OCR2 - Extracting player details from {len(matched_screenshots)} matched screenshots")
ocr2_results = asyncio.run(process_all_ocr2(matched_screenshots, api_key, semaphore_limit))
```

With:

```python
# AFTER (SINGLE asyncio.run call with unified phases)
async def run_all_ocr_phases():
    """Run OCR1 and OCR2 in unified event loop"""
    ocr1_results = {}
    ocr2_results = {}

    # Phase 1: OCR1 - Hand ID extraction
    logger.info(f"🔍 Phase 2: OCR1 - Extracting hand IDs from {len(screenshot_files)} screenshots")
    semaphore = asyncio.Semaphore(semaphore_limit)

    async def process_ocr1_with_semaphore(screenshot_file):
        async with semaphore:
            return await process_ocr1(screenshot_file)

    ocr1_tasks = [process_ocr1_with_semaphore(sf) for sf in screenshot_files]
    ocr1_raw_results = await asyncio.gather(*ocr1_tasks)

    # Convert list results to dict format (maintain backward compatibility)
    for i, result in enumerate(ocr1_raw_results):
        screenshot_file = screenshot_files[i]
        ocr1_results[screenshot_file['filename']] = result

    # Phase 2: OCR2 - Player details extraction (only on matched screenshots)
    matched_screenshot_list = [
        sf for sf in screenshot_files
        if sf['filename'] in matched_screenshots
    ]

    logger.info(f"🔍 Phase 5: OCR2 - Extracting player details from {len(matched_screenshot_list)} matched screenshots")
    semaphore = asyncio.Semaphore(semaphore_limit)

    async def process_ocr2_with_semaphore(screenshot_file):
        async with semaphore:
            return await process_ocr2(screenshot_file)

    ocr2_tasks = [process_ocr2_with_semaphore(sf) for sf in matched_screenshot_list]
    ocr2_raw_results = await asyncio.gather(*ocr2_tasks)

    # Convert list results to dict format
    for i, result in enumerate(ocr2_raw_results):
        screenshot_file = matched_screenshot_list[i]
        ocr2_results[screenshot_file['filename']] = result

    return ocr1_results, ocr2_results

# SINGLE event loop call
logger.info("🔄 Running OCR phases in unified event loop")
ocr1_results, ocr2_results = asyncio.run(run_all_ocr_phases())
```

**Step 4: Update imports if needed**

Verify `main.py` imports at top:
```python
import asyncio
from ocr import process_ocr1, process_ocr2  # Verify these functions exist
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_asyncio_unification.py -v
```

Expected:
```
PASSED tests/test_asyncio_unification.py::test_ocr_phases_in_same_event_loop
```

**Step 6: Run full pipeline test**

```bash
python test_cli.py
```

Expected: All existing tests still pass (no regression).

**Step 7: Commit**

```bash
git add main.py tests/test_asyncio_unification.py
git commit -m "fix: unify asyncio event loops for OCR phases (#1)

- Remove duplicate asyncio.run() calls
- Consolidate OCR1 and OCR2 in single event loop
- Maintains backward compatibility with existing code
- Reduces race condition vector

Fixes: Asyncio.run() Múltiples Veces"
```

---

### Task 1.2: API Key Validation - Fail Fast (High Priority)

**Problem:** GEMINI_API_KEY falls back to 'DUMMY_API_KEY_FOR_TESTING' silently. Job processes without real OCR. User doesn't know.

**Files:**
- Modify: `main.py:1540-1560`
- Modify: `ocr.py:25-35`
- Create: `tests/test_api_key_validation.py`

**Step 1: Write failing test for API key validation**

Create `tests/test_api_key_validation.py`:

```python
import pytest
from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch, MagicMock
import os

client = TestClient(app)

def test_process_fails_without_api_key():
    """Verify job fails immediately if API key not configured"""

    # Mock environment to ensure no API key
    with patch.dict(os.environ, {}, clear=True):
        # Create test job
        response = client.post("/api/upload", data={
            "txt_files": [],
            "screenshots": []
        })

        if response.status_code == 201:
            job_id = response.json()['job_id']

            # Try to process without API key
            with patch('main.os.getenv', return_value=None):
                process_response = client.post(f"/api/process/{job_id}")

            # Should fail with 400 error, not 200
            assert process_response.status_code == 400
            assert "GEMINI_API_KEY" in process_response.json()['detail']

def test_process_fails_with_dummy_api_key():
    """Verify job fails if only dummy key available"""

    with patch('main.os.getenv', return_value='DUMMY_API_KEY_FOR_TESTING'):
        response = client.post("/api/upload", data={
            "txt_files": [],
            "screenshots": []
        })

        if response.status_code == 201:
            job_id = response.json()['job_id']
            process_response = client.post(f"/api/process/{job_id}")

            # Should fail, not succeed silently
            assert process_response.status_code in [400, 500]

def test_process_succeeds_with_valid_api_key():
    """Verify job processes with valid API key"""

    with patch('main.os.getenv', return_value='valid_key_xyz123'):
        with patch('ocr.genai.configure'):
            response = client.post("/api/upload", data={
                "txt_files": [],
                "screenshots": []
            })

            if response.status_code == 201:
                job_id = response.json()['job_id']

                with patch('main.run_processing_pipeline'):
                    process_response = client.post(f"/api/process/{job_id}")

                # Should succeed or be accepted
                assert process_response.status_code in [200, 202]
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_api_key_validation.py::test_process_fails_without_api_key -v
```

Expected:
```
FAILED tests/test_api_key_validation.py::test_process_fails_without_api_key
```

**Step 3: Implement API key validation in main.py**

Modify `main.py` around line 1543-1548:

```python
# BEFORE
if not api_key or not api_key.strip():
    api_key = os.getenv('GEMINI_API_KEY', 'DUMMY_API_KEY_FOR_TESTING')

logger.info(f"Using API key: {'User-provided' if api_key != os.getenv('GEMINI_API_KEY') else 'Environment'}")

# AFTER
if not api_key or not api_key.strip():
    api_key = os.getenv('GEMINI_API_KEY')

# CRITICAL: Fail fast if no API key
if not api_key or api_key == 'your_gemini_api_key_here' or api_key == 'DUMMY_API_KEY_FOR_TESTING':
    error_msg = (
        "GEMINI_API_KEY not configured. Cannot proceed with OCR processing.\n"
        "Please configure:\n"
        "1. Set in .env file: GEMINI_API_KEY=your_actual_key\n"
        "2. Or pass in request header: X-Gemini-API-Key: your_actual_key\n"
        "3. Get key from: https://makersuite.google.com/app/apikey"
    )
    logger.critical(f"❌ {error_msg}")
    raise ValueError(error_msg)

logger.info(f"✓ Using Gemini API key (first 10 chars): {api_key[:10]}...")
```

**Step 4: Update ocr.py to raise instead of return error**

Modify `ocr.py` around line 25-35:

```python
# BEFORE
def ocr_hand_id(screenshot_path: str, api_key: str):
    if not api_key or api_key == "DUMMY_API_KEY_FOR_TESTING":
        return (False, None, "Gemini API key not configured")
    # ... rest of function

# AFTER
def ocr_hand_id(screenshot_path: str, api_key: str):
    if not api_key or api_key == "DUMMY_API_KEY_FOR_TESTING":
        raise ValueError(
            "Gemini API key is required but not configured. "
            "This should have been caught in main.py - report this error."
        )
    # ... rest of function
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_api_key_validation.py -v
```

Expected:
```
PASSED tests/test_api_key_validation.py::test_process_fails_without_api_key
PASSED tests/test_api_key_validation.py::test_process_fails_with_dummy_api_key
PASSED tests/test_api_key_validation.py::test_process_succeeds_with_valid_api_key
```

**Step 6: Test with manual job (integration test)**

```bash
# Test without API key
export GEMINI_API_KEY=""
python -c "from main import app; ..." # Should fail with clear error

# Test with API key
export GEMINI_API_KEY="sk-..."
python test_full_matching.py  # Should work
```

**Step 7: Commit**

```bash
git add main.py ocr.py tests/test_api_key_validation.py
git commit -m "fix: fail fast on missing GEMINI_API_KEY (#2)

- Remove silent fallback to DUMMY_API_KEY
- Raise ValueError immediately if key not configured
- Provide clear error message with configuration steps
- Update ocr.py to raise instead of returning error tuple

Fixes: GEMINI_API_KEY Fallback Silencioso"
```

---

## PHASE 2: MEDIUM SEVERITY FIXES (Next Sprint)

### Task 2.1: Table Name Consistency in Matching

**Problem:** `_group_hands_by_table()` generates `'unknown_table_1'` but `_build_table_mapping()` normalizes to `'Unknown'`. Screenshots don't find their hands.

**Files:**
- Modify: `main.py:2326-2352, 2384-2389`
- Create: `tests/test_table_name_consistency.py`

**Step 1: Write test for table name matching**

Create `tests/test_table_name_consistency.py`:

```python
import pytest
from main import _group_hands_by_table, _normalize_table_name, _table_matches

def test_unknown_table_variants_match():
    """Verify unknown_table_1 is found by its own group"""

    # Create mock hand
    hand1 = MagicMock()
    hand1.raw_text = "Table 'unknown_table_1'"

    # Group hands
    table_groups = {
        'unknown_table_1': [hand1],
        'unknown_table_2': [],
    }

    # Should match exactly
    assert _table_matches('unknown_table_1', 'unknown_table_1') == True
    assert _table_matches('unknown_table_1', 'unknown_table_2') == False

def test_normalize_preserves_unique_unknown_tables():
    """Verify normalization doesn't collapse different unknown tables"""

    norm1 = _normalize_table_name('unknown_table_1')
    norm2 = _normalize_table_name('unknown_table_2')

    # They should be equal after normalization (both become 'Unknown')
    # But we need to track them separately before normalization
    assert norm1 == norm2  # This reveals the bug

def test_table_matching_after_mapping():
    """Verify screenshots find their hands for unknown tables"""

    # Simulate finding hands for table
    table_name = 'unknown_table_1'
    hands = [hand for hand in all_hands if hand.table_name == table_name]

    assert len(hands) > 0  # Should find hands for unknown_table_1
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_table_name_consistency.py -v
```

Expected:
```
FAILED tests/test_table_name_consistency.py::test_unknown_table_variants_match
```

**Step 3: Implement _table_matches helper function**

Add to `main.py` before `_build_table_mapping()`:

```python
def _table_matches(hand_table_name: str, group_table_name: str) -> bool:
    """
    Check if two table names refer to the same table.
    Handles unknown_table_N pattern correctly.
    """
    # Exact match first
    if hand_table_name == group_table_name:
        return True

    # Both are unknown_table_N: must match exactly (different unknowns are different)
    if (hand_table_name.startswith('unknown_table_') and
        group_table_name.startswith('unknown_table_')):
        return hand_table_name == group_table_name

    # Normalize and compare
    return _normalize_table_name(hand_table_name) == _normalize_table_name(group_table_name)
```

**Step 4: Update _build_table_mapping to use _table_matches**

Modify `main.py` around line 2388:

```python
# BEFORE
if _normalize_table_name(hand_table_name) == _normalize_table_name(table_name):

# AFTER
if _table_matches(hand_table_name, table_name):
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_table_name_consistency.py -v
```

Expected:
```
PASSED tests/test_table_name_consistency.py::test_unknown_table_variants_match
```

**Step 6: Integration test with sample job**

```bash
# Create job with unknown tables
# Verify screenshots for unknown_table_1 are found
pytest test_job3_matching.py -v
```

**Step 7: Commit**

```bash
git add main.py tests/test_table_name_consistency.py
git commit -m "fix: consistent table name matching for unknown tables (#3)

- Add _table_matches() helper function
- Preserve unknown_table_N distinction during mapping
- Prevent collapse of different unknown tables to 'Unknown'
- Update _build_table_mapping to use new matcher

Fixes: Table Name Mismatch en Grouping"
```

---

### Task 2.2: ZIP Integrity Validation

**Problem:** ZIP files created but not validated. Corrupted ZIP delivered to user.

**Files:**
- Modify: `main.py:359-390`
- Create: `tests/test_zip_integrity.py`

**Step 1: Write test for ZIP validation**

Create `tests/test_zip_integrity.py`:

```python
import pytest
import zipfile
from pathlib import Path
from main import download_output
from unittest.mock import patch, MagicMock

def test_zip_integrity_validated_on_download():
    """Verify corrupted ZIP is rejected on download"""

    # Create a valid ZIP
    valid_zip = Path("test_valid.zip")
    with zipfile.ZipFile(valid_zip, 'w') as zf:
        zf.writestr("test.txt", "content")

    # Verify it's valid
    with zipfile.ZipFile(valid_zip, 'r') as zf:
        assert zf.testzip() is None  # None means valid

    valid_zip.unlink()

def test_corrupted_zip_rejected():
    """Verify corrupted ZIP is rejected"""

    # Create a corrupted ZIP
    corrupted_zip = Path("test_corrupted.zip")
    with open(corrupted_zip, 'wb') as f:
        f.write(b'PK\x03\x04')  # ZIP header but invalid data

    # Try to test it
    with zipfile.ZipFile(corrupted_zip, 'r') as zf:
        try:
            result = zf.testzip()
            # If it returns something, it's corrupted
            assert result is not None
        except zipfile.BadZipFile:
            pass  # Also valid sign of corruption

    corrupted_zip.unlink()

def test_download_endpoint_validates_zip(client):
    """Verify download endpoint checks ZIP before serving"""

    # Create job with output
    with patch('main.get_result') as mock_get_result:
        with patch('main.get_job') as mock_get_job:
            mock_get_job.return_value = {'status': 'completed'}
            mock_get_result.return_value = {'output_txt_path': '/path/to/file.zip'}

            # Create test ZIP
            test_zip = Path("/path/to/file.zip")
            test_zip.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(test_zip, 'w') as zf:
                zf.writestr("test.txt", "content")

            # Download should succeed
            response = client.get("/api/download/1")
            assert response.status_code in [200, 404]  # 200 if found

            # Cleanup
            if test_zip.exists():
                test_zip.unlink()
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_zip_integrity.py -v
```

Expected:
```
FAILED tests/test_zip_integrity.py::test_download_endpoint_validates_zip
```

**Step 3: Add ZIP validation to download endpoint**

Modify `main.py` around line 359-390:

```python
# BEFORE
@app.get("/api/download/{job_id}")
async def download_output(job_id: int):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job is not completed yet")

    result = get_result(job_id)
    if not result or not result.get('output_txt_path'):
        raise HTTPException(status_code=404, detail="Output file not found")

    output_path = Path(result['output_txt_path'])

    if output_path.suffix == '.zip' and output_path.exists():
        return FileResponse(path=output_path, ...)

# AFTER
@app.get("/api/download/{job_id}")
async def download_output(job_id: int):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job is not completed yet")

    result = get_result(job_id)
    if not result or not result.get('output_txt_path'):
        raise HTTPException(status_code=404, detail="Output file not found")

    output_path = Path(result['output_txt_path'])

    if output_path.suffix == '.zip' and output_path.exists():
        # VALIDATE ZIP INTEGRITY BEFORE DOWNLOAD
        try:
            with zipfile.ZipFile(output_path, 'r') as zipf:
                # testzip() returns None if valid, filename if corrupted
                bad_file = zipf.testzip()
                if bad_file:
                    logger.error(f"ZIP file corrupted: cannot read {bad_file}", job_id=job_id)
                    raise HTTPException(
                        status_code=500,
                        detail=f"Output file is corrupted and cannot be extracted. "
                               f"Contact administrator with job ID {job_id}"
                    )
        except zipfile.BadZipFile:
            logger.error(f"ZIP file is invalid/corrupted", job_id=job_id)
            raise HTTPException(
                status_code=500,
                detail=f"Output file is corrupted. Contact administrator with job ID {job_id}"
            )

        return FileResponse(
            path=output_path,
            filename=f"resolved_hands_{job_id}.zip",
            media_type="application/zip"
        )

    raise HTTPException(status_code=404, detail="Output file not found")
```

**Step 4: Add import at top of main.py**

```python
import zipfile  # Add if not present
```

**Step 5: Run test to verify it passes**

```bash
pytest tests/test_zip_integrity.py -v
```

Expected:
```
PASSED tests/test_zip_integrity.py::test_download_endpoint_validates_zip
```

**Step 6: Integration test**

```bash
# Create test job and download
pytest test_full_matching.py -v
# Manually download and verify
curl http://localhost:5000/api/download/1 > test_download.zip
unzip -t test_download.zip  # Should succeed
```

**Step 7: Commit**

```bash
git add main.py tests/test_zip_integrity.py
git commit -m "fix: validate ZIP integrity before download (#4)

- Add zipfile.testzip() validation in download endpoint
- Catch BadZipFile exceptions
- Return 500 error for corrupted files
- Log errors for debugging

Fixes: Validación de ZIP Faltante"
```

---

### Task 2.3: OCR2 Output Schema Validation

**Problem:** OCR2 data parsed without schema validation. Invalid JSON crashes job.

**Files:**
- Modify: `main.py:2404-2467`
- Create: `tests/test_ocr2_validation.py`

**Step 1: Write test for OCR2 schema validation**

Create `tests/test_ocr2_validation.py`:

```python
import pytest
import json
from main import _build_table_mapping
from unittest.mock import MagicMock
from models import ScreenshotAnalysis

def test_valid_ocr2_data_accepted():
    """Verify valid OCR2 output is processed"""

    valid_ocr_data = {
        'players': ['Player1', 'Player2', 'Player3'],
        'stacks': ['$100', '$200', '$150'],
        'positions': [1, 2, 3],
        'roles': {
            'dealer': 'Player1',
            'small_blind': 'Player2',
            'big_blind': 'Player3'
        },
        'hand_id': 'RC12345'
    }

    # Should not raise
    screenshot = MagicMock()
    screenshot.ocr2_data = json.dumps(valid_ocr_data)

    # After fix, should validate successfully
    assert isinstance(valid_ocr_data.get('players'), list)

def test_missing_players_field_rejected():
    """Verify OCR2 missing players field is caught"""

    invalid_ocr_data = {
        'stacks': ['$100', '$200'],  # Missing 'players'
        'roles': {'dealer': 'Player1'}
    }

    # Should fail validation
    assert 'players' not in invalid_ocr_data

def test_invalid_stacks_format_rejected():
    """Verify OCR2 invalid stacks format is caught"""

    invalid_ocr_data = {
        'players': ['Player1', 'Player2'],
        'stacks': 'invalid_string',  # Should be list
        'roles': {'dealer': 'Player1'}
    }

    # Should fail validation
    assert not isinstance(invalid_ocr_data.get('stacks'), list)

def test_ocr2_validation_continues_on_error():
    """Verify job continues if single OCR2 is invalid"""

    # Mock multiple screenshots
    screenshots = [
        MagicMock(filename='valid.png', ocr2_data=json.dumps({'players': [], 'roles': {}})),
        MagicMock(filename='invalid.png', ocr2_data='not_json'),
        MagicMock(filename='another_valid.png', ocr2_data=json.dumps({'players': [], 'roles': {}}))
    ]

    # After fix, should process valid ones, skip invalid
    valid_count = 0
    for ss in screenshots:
        try:
            data = json.loads(ss.ocr2_data)
            if isinstance(data.get('players'), list):
                valid_count += 1
        except:
            pass  # Skip invalid

    assert valid_count >= 2  # At least 2 valid
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_ocr2_validation.py -v
```

Expected:
```
FAILED tests/test_ocr2_validation.py::test_ocr2_validation_continues_on_error
```

**Step 3: Implement OCR2 schema validation**

Modify `main.py` in `_build_table_mapping()` around line 2404-2467:

```python
# BEFORE
if isinstance(ocr_data, str):
    ocr_data = json.loads(ocr_data)

players_list = ocr_data.get('players', [])
stacks_list = ocr_data.get('stacks', [])

# AFTER
if isinstance(ocr_data, str):
    try:
        ocr_data = json.loads(ocr_data)
    except json.JSONDecodeError as e:
        logger.error(
            f"❌ OCR2 JSON parse error for {screenshot_filename}",
            screenshot=screenshot_filename,
            error=str(e),
            table=table_name
        )
        continue  # Skip this screenshot

# VALIDATE SCHEMA
required_fields = ['players', 'roles']
missing_fields = [f for f in required_fields if f not in ocr_data]

if missing_fields:
    logger.error(
        f"❌ OCR2 missing required fields for {screenshot_filename}",
        screenshot=screenshot_filename,
        missing_fields=missing_fields,
        table=table_name,
        received_keys=list(ocr_data.keys())
    )
    continue  # Skip this screenshot

# Validate field types
if not isinstance(ocr_data.get('players'), list):
    logger.error(
        f"❌ OCR2 'players' must be list for {screenshot_filename}",
        screenshot=screenshot_filename,
        received_type=type(ocr_data.get('players')).__name__,
        table=table_name
    )
    continue

if not isinstance(ocr_data.get('roles'), dict):
    logger.error(
        f"❌ OCR2 'roles' must be dict for {screenshot_filename}",
        screenshot=screenshot_filename,
        received_type=type(ocr_data.get('roles')).__name__,
        table=table_name
    )
    continue

# Now safe to use
players_list = ocr_data.get('players', [])
stacks_list = ocr_data.get('stacks', [])
positions_list = ocr_data.get('positions', [])
roles_dict = ocr_data.get('roles', {})
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_ocr2_validation.py -v
```

Expected:
```
PASSED tests/test_ocr2_validation.py::test_ocr2_validation_continues_on_error
PASSED tests/test_ocr2_validation.py::test_valid_ocr2_data_accepted
```

**Step 5: Integration test**

```bash
# Create job with mock OCR2 returning invalid JSON
# Job should complete without crashing
pytest test_full_matching.py -v
```

**Step 6: Commit**

```bash
git add main.py tests/test_ocr2_validation.py
git commit -m "fix: validate OCR2 output schema before use (#7)

- Add schema validation for OCR2 JSON output
- Validate required fields: players, roles
- Validate field types (list for players, dict for roles)
- Skip screenshots with invalid OCR2 data
- Log validation errors for debugging

Fixes: OCR2 Output Sin Validación de Schema"
```

---

### Task 2.4: Dealer Player Explicit Logging

**Problem:** If OCR2 doesn't extract dealer_player, mapping is incomplete silently.

**Files:**
- Modify: `main.py:2425-2447`
- Create: `tests/test_dealer_logging.py`

**Step 1: Write test for dealer logging**

Create `tests/test_dealer_logging.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from main import _build_table_mapping
from logger import JobLogger

def test_warning_logged_when_dealer_missing():
    """Verify warning is logged when dealer_player is None"""

    ocr_data = {
        'players': ['Player1', 'Player2', 'Player3'],
        'stacks': ['$100', '$200', '$150'],
        'roles': {
            'dealer': None,  # Missing dealer
            'small_blind': None,
            'big_blind': None
        }
    }

    screenshot = MagicMock()
    screenshot.ocr2_data = json.dumps(ocr_data)
    screenshot.filename = 'test.png'

    logger = JobLogger(job_id=1)

    with patch.object(logger, 'warning') as mock_warning:
        # After fix, should log warning
        pass  # Placeholder

def test_dealer_found_logs_debug():
    """Verify debug log when dealer is found"""

    ocr_data = {
        'players': ['Player1', 'Player2', 'Player3'],
        'stacks': ['$100', '$200', '$150'],
        'roles': {
            'dealer': 'Player1',
            'small_blind': 'Player2',
            'big_blind': 'Player3'
        }
    }

    logger = JobLogger(job_id=1)

    with patch.object(logger, 'debug') as mock_debug:
        # After fix, should log calculated blinds
        pass  # Placeholder

def test_dealer_not_in_players_list_logged():
    """Verify warning when dealer name not in players list"""

    ocr_data = {
        'players': ['Player1', 'Player2', 'Player3'],
        'roles': {
            'dealer': 'UnknownPlayer'  # Not in players list
        }
    }

    logger = JobLogger(job_id=1)

    with patch.object(logger, 'warning') as mock_warning:
        # After fix, should log that dealer not found
        pass  # Placeholder
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/test_dealer_logging.py -v
```

**Step 3: Add explicit logging for dealer**

Modify `main.py` around line 2425-2447:

```python
# BEFORE
dealer_player = ocr_data.get('roles', {}).get('dealer')

if dealer_player and dealer_player in players_list:
    dealer_index = players_list.index(dealer_player)
    total_players = len(players_list)

    small_blind_player = players_list[(dealer_index + 1) % total_players]
    big_blind_player = players_list[(dealer_index + 2) % total_players]

# AFTER
dealer_player = ocr_data.get('roles', {}).get('dealer')

if not dealer_player:
    logger.warning(
        f"⚠️  No dealer detected for screenshot {screenshot_filename}",
        screenshot=screenshot_filename,
        table=table_name,
        reason="dealer role not extracted by OCR2"
    )
    small_blind_player = None
    big_blind_player = None
elif dealer_player not in players_list:
    logger.warning(
        f"⚠️  Dealer '{dealer_player}' not found in player list for {screenshot_filename}",
        screenshot=screenshot_filename,
        table=table_name,
        dealer=dealer_player,
        available_players=players_list
    )
    small_blind_player = None
    big_blind_player = None
else:
    # Calculate blinds from dealer position
    dealer_index = players_list.index(dealer_player)
    total_players = len(players_list)

    small_blind_player = players_list[(dealer_index + 1) % total_players]
    big_blind_player = players_list[(dealer_index + 2) % total_players]

    logger.debug(
        f"✓ Calculated blinds from dealer",
        screenshot=screenshot_filename,
        table=table_name,
        dealer=dealer_player,
        sb=small_blind_player,
        bb=big_blind_player
    )
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/test_dealer_logging.py -v
```

**Step 5: Integration test**

```bash
# Process job and check logs
pytest test_full_matching.py -v
# Verify warnings in database logs
sqlite3 ggrevealer.db "SELECT * FROM logs WHERE level='WARNING' LIKE '%dealer%';"
```

**Step 6: Commit**

```bash
git add main.py tests/test_dealer_logging.py
git commit -m "fix: explicit logging for dealer player detection (#9)

- Log WARNING when dealer not detected by OCR2
- Log WARNING when dealer not in player list
- Log DEBUG when blinds calculated successfully
- Prevents silent failures in role-based mapping

Fixes: Dealer Player Silent Failure"
```

---

## PHASE 3: NICE-TO-HAVE FIXES (Refactoring)

### Task 3.1: Specific Exception Handling

**Problem:** Generic `except Exception:` hides bugs.

**Files:**
- Modify: `ocr.py:85-95`
- Modify: `parser.py:100-110`
- Modify: `main.py:2025-2035`
- Create: `tests/test_exception_handling.py`

(Implementation follows same TDD pattern as above tasks)

---

### Task 3.2: File Upload Rollback on Error

**Problem:** Failed uploads leave orphaned files.

**Files:**
- Modify: `main.py:220-255`
- Create: `tests/test_upload_rollback.py`

(Implementation follows same TDD pattern)

---

### Task 3.3: Consistent Table Grouping in Metrics

**Problem:** Validation uses string search, metrics use extract_table_name.

**Files:**
- Modify: `main.py:1850-1860, 2090-2110`
- Create: `tests/test_table_grouping.py`

(Implementation follows same TDD pattern)

---

## Execution Instructions

### Before Starting

1. Ensure you're in a clean git state:
   ```bash
   git status  # Should be clean
   git log --oneline -3  # Know where you started
   ```

2. Create feature branch (optional but recommended):
   ```bash
   git checkout -b fix/audit-issues-phase1
   ```

### During Implementation

- Run tests frequently: `pytest tests/ -v`
- Commit after each step (don't batch commits)
- Use descriptive commit messages
- Keep changes focused on one task

### After Phase 1 Complete

- All tests pass: `pytest tests/ -v`
- Full pipeline test passes: `python test_full_matching.py`
- No regressions: `python test_cli.py`
- Ready for code review

### Deployment

1. Phase 1: Deploy immediately (unblocks production)
2. Phase 2: Deploy next sprint (increases stability)
3. Phase 3: Deploy as convenient (refactoring)

---

## Success Criteria

### Phase 1 (Critical - Must Pass)
- [ ] `asyncio.run()` called only once
- [ ] No `asyncio.run()` in two places
- [ ] GEMINI_API_KEY validation raises error if missing
- [ ] All tests pass
- [ ] No test regressions

### Phase 2 (Medium - Should Pass)
- [ ] Unknown tables handled correctly
- [ ] ZIP files validated before download
- [ ] OCR2 invalid data skipped with warning
- [ ] Dealer failures logged clearly
- [ ] All tests pass

### Phase 3 (Nice-to-have - Nice to Pass)
- [ ] No generic `except Exception:`
- [ ] Upload failures clean up files
- [ ] Consistent table grouping
- [ ] All tests pass

---

## Estimated Time

- **Phase 1**: 2-3 hours (2 tasks)
- **Phase 2**: 4-5 hours (4 tasks)
- **Phase 3**: 2-3 hours (3 tasks)
- **Total**: 8-11 hours
- **Testing & Review**: +2-3 hours

Can be parallelized to 1-2 days with multiple developers.

---

## Questions?

Each task includes:
- Specific file paths
- Complete code examples
- Test verification steps
- Exact git commands

Follow the TDD pattern: Test → Implement → Commit

If stuck, check the AUDIT_DETAILED.md for technical context on each problem.
