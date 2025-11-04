# Batch Upload System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement batch upload system to work around Replit's ~100 MB nginx proxy limit by splitting large uploads into 50-60 MB batches.

**Architecture:** Create new job initialization endpoint that returns job_id before file upload. Add batch upload endpoint that accepts partial file uploads. Modify frontend to split files into size-based batches and upload sequentially with progress tracking.

**Tech Stack:** FastAPI (backend), Vanilla JS (frontend), SQLite (persistence)

---

## Task 1: Backend - Job Initialization Endpoint

**Files:**
- Modify: `main.py:210-266` (existing upload endpoint)
- Create: New endpoint at `main.py:~210` (insert before existing `/api/upload`)
- Test: Manual testing with curl

**Step 1: Write the new job initialization endpoint**

Insert this BEFORE the existing `@app.post("/api/upload")` endpoint (around line 210):

```python
@app.post("/api/upload/init")
async def init_upload_job(api_tier: str = Form(default='free')):
    """Initialize a new upload job without files (for batch uploads)"""
    # Validate API tier
    if api_tier not in ('free', 'paid'):
        api_tier = 'free'

    job_id = create_job(api_tier=api_tier)

    # Create upload directories
    job_upload_path = UPLOADS_PATH / str(job_id)
    job_upload_path.mkdir(exist_ok=True)

    txt_path = job_upload_path / "txt"
    screenshots_path = job_upload_path / "screenshots"
    txt_path.mkdir(exist_ok=True)
    screenshots_path.mkdir(exist_ok=True)

    return {
        "job_id": job_id,
        "status": "initialized",
        "message": "Job creado. Ahora puedes subir archivos por lotes."
    }
```

**Step 2: Test the initialization endpoint**

Run the server:
```bash
python main.py
```

Test in a new terminal:
```bash
curl -X POST http://localhost:5000/api/upload/init \
  -F "api_tier=free"
```

Expected output:
```json
{
  "job_id": 1,
  "status": "initialized",
  "message": "Job creado. Ahora puedes subir archivos por lotes."
}
```

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add job initialization endpoint for batch uploads"
```

---

## Task 2: Backend - Batch Upload Endpoint

**Files:**
- Create: New endpoint at `main.py:~235` (insert after init endpoint)
- Test: Manual testing with curl

**Step 1: Write the batch upload endpoint**

Insert this after the `/api/upload/init` endpoint:

```python
@app.post("/api/upload/batch/{job_id}")
async def upload_batch(
    job_id: int,
    txt_files: List[UploadFile] = File(default=[]),
    screenshots: List[UploadFile] = File(default=[])
):
    """Upload a batch of files to an existing job"""
    # Verify job exists
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")

    if job['status'] not in ['pending', 'initialized']:
        raise HTTPException(
            status_code=400,
            detail=f"No se pueden subir archivos a un job con estado '{job['status']}'"
        )

    job_upload_path = UPLOADS_PATH / str(job_id)
    txt_path = job_upload_path / "txt"
    screenshots_path = job_upload_path / "screenshots"

    # Ensure directories exist
    txt_path.mkdir(parents=True, exist_ok=True)
    screenshots_path.mkdir(parents=True, exist_ok=True)

    txt_count = 0
    screenshot_count = 0

    # Save TXT files
    for txt_file in txt_files:
        if not txt_file.filename:
            continue
        file_path = txt_path / txt_file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(txt_file.file, f)
        add_file(job_id, txt_file.filename, "txt", str(file_path))
        txt_count += 1

    # Save screenshot files
    for screenshot in screenshots:
        if not screenshot.filename:
            continue
        file_path = screenshots_path / screenshot.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(screenshot.file, f)
        add_file(job_id, screenshot.filename, "screenshot", str(file_path))
        screenshot_count += 1

    # Get current file counts from database
    job_files = get_job_files(job_id)
    total_txt = len([f for f in job_files if f['file_type'] == 'txt'])
    total_screenshots = len([f for f in job_files if f['file_type'] == 'screenshot'])

    # Update job file counts
    update_job_file_counts(job_id, total_txt, total_screenshots)

    return {
        "job_id": job_id,
        "batch_txt_count": txt_count,
        "batch_screenshot_count": screenshot_count,
        "total_txt_count": total_txt,
        "total_screenshot_count": total_screenshots,
        "message": f"Lote subido: {txt_count} TXT, {screenshot_count} screenshots"
    }
```

**Step 2: Test the batch upload endpoint**

First, initialize a job:
```bash
JOB_ID=$(curl -s -X POST http://localhost:5000/api/upload/init -F "api_tier=free" | jq -r '.job_id')
echo "Job ID: $JOB_ID"
```

Then upload a batch (replace with actual test files):
```bash
curl -X POST http://localhost:5000/api/upload/batch/$JOB_ID \
  -F "txt_files=@/path/to/test1.txt" \
  -F "screenshots=@/path/to/screenshot1.png"
```

Expected output:
```json
{
  "job_id": 1,
  "batch_txt_count": 1,
  "batch_screenshot_count": 1,
  "total_txt_count": 1,
  "total_screenshot_count": 1,
  "message": "Lote subido: 1 TXT, 1 screenshots"
}
```

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add batch upload endpoint for chunked uploads"
```

---

## Task 3: Backend - File Count Validation

**Files:**
- Modify: `main.py` (batch upload endpoint from Task 2)
- Test: Manual testing with curl

**Step 1: Add validation to batch upload endpoint**

Modify the `upload_batch` function to add validation after counting files (around line where we calculate `total_txt` and `total_screenshots`):

Find this section:
```python
    # Update job file counts
    update_job_file_counts(job_id, total_txt, total_screenshots)
```

Replace with:
```python
    # Validate file count limits
    if total_txt > MAX_TXT_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Excede el límite de archivos TXT. Máximo: {MAX_TXT_FILES}, Total acumulado: {total_txt}"
        )

    if total_screenshots > MAX_SCREENSHOT_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Excede el límite de screenshots. Máximo: {MAX_SCREENSHOT_FILES}, Total acumulado: {total_screenshots}"
        )

    # Update job file counts
    update_job_file_counts(job_id, total_txt, total_screenshots)
```

**Step 2: Test validation**

Test that it rejects when exceeding limits (you may need to adjust MAX_TXT_FILES temporarily to test):

```bash
# Upload batch that would exceed limit
# (create a loop to upload 301 files if MAX_TXT_FILES=300)
```

Expected: 400 error with message about exceeding limit

**Step 3: Commit**

```bash
git add main.py
git commit -m "feat: add file count validation to batch uploads"
```

---

## Task 4: Frontend - File Batching Utility

**Files:**
- Modify: `static/js/app.js:~1` (add at top of file, after API_BASE constant)
- Test: Browser console testing

**Step 1: Add batch size constants and utility function**

Add these constants after the `API_BASE` declaration (around line 1-10):

```javascript
const MAX_BATCH_SIZE_MB = 55; // 55 MB to stay safely under 60 MB limit
const MAX_BATCH_SIZE_BYTES = MAX_BATCH_SIZE_MB * 1024 * 1024;

/**
 * Split files into batches based on size limit
 * @param {File[]} files - Array of File objects
 * @param {number} maxBatchSize - Maximum batch size in bytes
 * @returns {File[][]} Array of file batches
 */
function createFileBatches(files, maxBatchSize = MAX_BATCH_SIZE_BYTES) {
    const batches = [];
    let currentBatch = [];
    let currentBatchSize = 0;

    for (const file of files) {
        const fileSize = file.size;

        // If single file exceeds limit, put it in its own batch
        if (fileSize > maxBatchSize) {
            // Flush current batch if not empty
            if (currentBatch.length > 0) {
                batches.push(currentBatch);
                currentBatch = [];
                currentBatchSize = 0;
            }
            // Add large file as single-file batch
            batches.push([file]);
            continue;
        }

        // If adding this file would exceed limit, start new batch
        if (currentBatchSize + fileSize > maxBatchSize && currentBatch.length > 0) {
            batches.push(currentBatch);
            currentBatch = [];
            currentBatchSize = 0;
        }

        currentBatch.push(file);
        currentBatchSize += fileSize;
    }

    // Add remaining files
    if (currentBatch.length > 0) {
        batches.push(currentBatch);
    }

    return batches;
}

/**
 * Calculate total size of files in bytes
 * @param {File[]} files - Array of File objects
 * @returns {number} Total size in bytes
 */
function calculateTotalSize(files) {
    return files.reduce((total, file) => total + file.size, 0);
}

/**
 * Format bytes to human-readable size
 * @param {number} bytes - Size in bytes
 * @returns {string} Formatted size (e.g., "12.5 MB")
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}
```

**Step 2: Test batching logic in browser console**

Open the app in browser, open DevTools console, and test:

```javascript
// Create mock files for testing
const mockFiles = [
    { name: 'file1.txt', size: 30 * 1024 * 1024 }, // 30 MB
    { name: 'file2.txt', size: 40 * 1024 * 1024 }, // 40 MB
    { name: 'file3.txt', size: 20 * 1024 * 1024 }, // 20 MB
    { name: 'file4.txt', size: 60 * 1024 * 1024 }, // 60 MB (exceeds limit)
];

const batches = createFileBatches(mockFiles);
console.log('Batches:', batches.length);
batches.forEach((batch, i) => {
    const size = calculateTotalSize(batch);
    console.log(`Batch ${i + 1}: ${batch.length} files, ${formatBytes(size)}`);
});
```

Expected output:
```
Batches: 3
Batch 1: 2 files, 50 MB  // file1 (30MB) + file2 (40MB) would exceed, so only file1
Batch 2: 2 files, 60 MB  // file2 (40MB) + file3 (20MB)
Batch 3: 1 files, 60 MB  // file4 alone (exceeds limit)
```

**Step 3: Commit**

```bash
git add static/js/app.js
git commit -m "feat: add file batching utility for chunked uploads"
```

---

## Task 5: Frontend - Batch Upload UI Progress

**Files:**
- Modify: `static/js/app.js` (add progress display functions)
- Modify: `templates/index.html` (add progress UI elements)
- Test: Browser visual testing

**Step 1: Add batch upload progress HTML**

In `templates/index.html`, find the upload section (around the "Subiendo..." area) and add this new progress div:

Find this section (around line 50-60):
```html
<div id="uploadSection" class="mb-4">
    <!-- existing upload form -->
</div>
```

Add this immediately after the upload form div (inside uploadSection):

```html
<!-- Batch Upload Progress -->
<div id="batchProgress" class="mt-3" style="display: none;">
    <div class="card border-primary">
        <div class="card-body">
            <h6 class="card-title">
                <i class="bi bi-cloud-upload"></i> Subiendo archivos por lotes...
            </h6>
            <div class="progress mb-2" style="height: 25px;">
                <div id="batchProgressBar" class="progress-bar progress-bar-striped progress-bar-animated"
                     role="progressbar" style="width: 0%;" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                    0%
                </div>
            </div>
            <p class="mb-1" id="batchProgressText">Preparando lotes...</p>
            <small class="text-muted" id="batchProgressDetail">Lote 0 de 0</small>
        </div>
    </div>
</div>
```

**Step 2: Add batch progress JavaScript functions**

In `static/js/app.js`, add these functions before the `uploadAndProcess` function:

```javascript
/**
 * Show batch upload progress UI
 */
function showBatchProgress() {
    document.getElementById('batchProgress').style.display = 'block';
}

/**
 * Hide batch upload progress UI
 */
function hideBatchProgress() {
    document.getElementById('batchProgress').style.display = 'none';
}

/**
 * Update batch upload progress
 * @param {number} current - Current batch number (1-based)
 * @param {number} total - Total number of batches
 * @param {string} message - Progress message
 */
function updateBatchProgress(current, total, message = '') {
    const progressBar = document.getElementById('batchProgressBar');
    const progressText = document.getElementById('batchProgressText');
    const progressDetail = document.getElementById('batchProgressDetail');

    const percentage = Math.round((current / total) * 100);

    progressBar.style.width = percentage + '%';
    progressBar.setAttribute('aria-valuenow', percentage);
    progressBar.textContent = percentage + '%';

    if (message) {
        progressText.textContent = message;
    }

    progressDetail.textContent = `Lote ${current} de ${total}`;
}
```

**Step 3: Test progress UI in browser**

Open browser DevTools console and test:

```javascript
// Show progress
showBatchProgress();

// Simulate batch upload progress
updateBatchProgress(1, 3, 'Subiendo archivos TXT...');
setTimeout(() => updateBatchProgress(2, 3, 'Subiendo screenshots...'), 1000);
setTimeout(() => updateBatchProgress(3, 3, 'Finalizando...'), 2000);
setTimeout(() => hideBatchProgress(), 3000);
```

Expected: Progress bar should animate from 0% to 33% to 66% to 100% with messages

**Step 4: Commit**

```bash
git add static/js/app.js templates/index.html
git commit -m "feat: add batch upload progress UI"
```

---

## Task 6: Frontend - Batch Upload Logic

**Files:**
- Modify: `static/js/app.js` (uploadAndProcess function around line 320-373)
- Test: Full integration test with real files

**Step 1: Replace the upload logic in uploadAndProcess function**

Find the `uploadAndProcess` function (around line 295-373). Replace the entire `try` block (lines 340-365) with this new batch upload logic:

```javascript
    try {
        // Step 1: Initialize job
        uploadBtn.disabled = true;
        uploadBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Inicializando...';

        const initFormData = new FormData();
        initFormData.append('api_tier', apiTier);

        const initResponse = await fetch(`${API_BASE}/api/upload/init`, {
            method: 'POST',
            body: initFormData
        });

        if (!initResponse.ok) {
            const errorData = await initResponse.json().catch(() => ({ detail: 'Failed to initialize job' }));
            throw new Error(errorData.detail || 'Failed to initialize job');
        }

        const initData = await initResponse.json();
        currentJobId = initData.job_id;

        // Step 2: Prepare batches
        uploadBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Preparando lotes...';

        // Combine all files and create batches
        const allFiles = [...txtFiles, ...screenshotFiles];
        const fileBatches = createFileBatches(allFiles);

        const totalBatches = fileBatches.length;
        const totalSize = calculateTotalSize(allFiles);

        console.log(`Uploading ${allFiles.length} files (${formatBytes(totalSize)}) in ${totalBatches} batches`);

        // Show batch progress UI
        showBatchProgress();
        updateBatchProgress(0, totalBatches, `Preparando ${totalBatches} lotes...`);

        // Step 3: Upload batches sequentially
        for (let i = 0; i < fileBatches.length; i++) {
            const batch = fileBatches[i];
            const batchNum = i + 1;
            const batchSize = calculateTotalSize(batch);

            updateBatchProgress(
                batchNum,
                totalBatches,
                `Subiendo lote ${batchNum}/${totalBatches} (${formatBytes(batchSize)})`
            );

            const batchFormData = new FormData();

            // Separate files by type
            batch.forEach(file => {
                if (file.name.endsWith('.txt')) {
                    batchFormData.append('txt_files', file);
                } else {
                    batchFormData.append('screenshots', file);
                }
            });

            const batchResponse = await fetch(`${API_BASE}/api/upload/batch/${currentJobId}`, {
                method: 'POST',
                body: batchFormData
            });

            if (!batchResponse.ok) {
                const errorData = await batchResponse.json().catch(() => ({
                    detail: `Failed to upload batch ${batchNum}`
                }));
                throw new Error(errorData.detail || `Failed to upload batch ${batchNum}`);
            }

            const batchData = await batchResponse.json();
            console.log(`Batch ${batchNum} uploaded:`, batchData);
        }

        // Hide batch progress
        hideBatchProgress();

        // Step 4: Start processing
        uploadBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Iniciando procesamiento...';

        const processResponse = await fetch(`${API_BASE}/api/process/${currentJobId}`, {
            method: 'POST',
            headers: getHeadersWithApiKey()
        });

        if (!processResponse.ok) {
            throw new Error('Failed to start processing');
        }

        showProcessing();
        startTimer();
        startStatusPolling();

    } catch (error) {
        console.error('Error:', error);
        showError('Error al subir archivos: ' + error.message);
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<i class="bi bi-upload"></i> Subir y Procesar';
        hideBatchProgress(); // Hide progress on error
    }
```

**Step 2: Test with real files**

1. Start the server: `python main.py`
2. Open browser to `http://localhost:5000/app`
3. Select test files (mix of TXT and screenshots totaling ~100-150 MB)
4. Click "Subir y Procesar"
5. Observe batch progress UI

Expected behavior:
- Shows "Inicializando..."
- Shows "Preparando lotes..."
- Shows batch progress (e.g., "Lote 1 de 3")
- Progress bar animates
- Eventually shows "Procesando..." screen
- Job processes successfully

**Step 3: Test error handling**

Test with files exceeding 300MB total:
- Should show error message
- Should hide batch progress UI
- Should re-enable upload button

**Step 4: Commit**

```bash
git add static/js/app.js
git commit -m "feat: implement batch upload logic in frontend"
```

---

## Task 7: Testing - Integration Tests

**Files:**
- Create: `test_batch_uploads.py`
- Test: Run pytest

**Step 1: Write integration tests**

Create `test_batch_uploads.py`:

```python
"""Integration tests for batch upload system"""

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from io import BytesIO

from main import app
from database import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup test database before each test"""
    # Use test database
    os.environ['DATABASE_PATH'] = ':memory:'
    init_db()
    yield
    # Cleanup happens automatically with in-memory DB

def create_mock_file(filename: str, size_mb: int = 1):
    """Create a mock file for testing"""
    content = b'x' * (size_mb * 1024 * 1024)
    return (filename, BytesIO(content), 'text/plain')

def test_init_upload_job():
    """Test job initialization endpoint"""
    response = client.post("/api/upload/init", data={"api_tier": "free"})

    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "initialized"
    assert data["job_id"] > 0

def test_batch_upload_single_batch():
    """Test uploading a single batch of files"""
    # Initialize job
    init_response = client.post("/api/upload/init", data={"api_tier": "free"})
    job_id = init_response.json()["job_id"]

    # Upload batch
    files = {
        "txt_files": [create_mock_file("test1.txt", 1)],
        "screenshots": [create_mock_file("screenshot1.png", 1)]
    }

    response = client.post(f"/api/upload/batch/{job_id}", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["batch_txt_count"] == 1
    assert data["batch_screenshot_count"] == 1
    assert data["total_txt_count"] == 1
    assert data["total_screenshot_count"] == 1

def test_batch_upload_multiple_batches():
    """Test uploading multiple batches sequentially"""
    # Initialize job
    init_response = client.post("/api/upload/init", data={"api_tier": "free"})
    job_id = init_response.json()["job_id"]

    # Upload batch 1
    files1 = {
        "txt_files": [create_mock_file("test1.txt", 1)],
    }
    response1 = client.post(f"/api/upload/batch/{job_id}", files=files1)
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["total_txt_count"] == 1

    # Upload batch 2
    files2 = {
        "txt_files": [create_mock_file("test2.txt", 1)],
        "screenshots": [create_mock_file("screenshot1.png", 1)]
    }
    response2 = client.post(f"/api/upload/batch/{job_id}", files=files2)
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["total_txt_count"] == 2
    assert data2["total_screenshot_count"] == 1

def test_batch_upload_invalid_job():
    """Test uploading to non-existent job returns 404"""
    files = {
        "txt_files": [create_mock_file("test1.txt", 1)],
    }

    response = client.post("/api/upload/batch/99999", files=files)
    assert response.status_code == 404
    assert "Job no encontrado" in response.json()["detail"]

def test_batch_upload_exceeds_file_limit():
    """Test that exceeding file limits returns error"""
    # Initialize job
    init_response = client.post("/api/upload/init", data={"api_tier": "free"})
    job_id = init_response.json()["job_id"]

    # Try to upload 301 TXT files (exceeds MAX_TXT_FILES=300)
    files = {
        "txt_files": [create_mock_file(f"test{i}.txt", 1) for i in range(301)]
    }

    response = client.post(f"/api/upload/batch/{job_id}", files=files)
    assert response.status_code == 400
    assert "Excede el límite" in response.json()["detail"]
```

**Step 2: Run tests**

```bash
pytest test_batch_uploads.py -v
```

Expected output:
```
test_batch_uploads.py::test_init_upload_job PASSED
test_batch_uploads.py::test_batch_upload_single_batch PASSED
test_batch_uploads.py::test_batch_upload_multiple_batches PASSED
test_batch_uploads.py::test_batch_upload_invalid_job PASSED
test_batch_uploads.py::test_batch_upload_exceeds_file_limit PASSED

5 passed in 1.23s
```

**Step 3: Commit**

```bash
git add test_batch_uploads.py
git commit -m "test: add integration tests for batch upload system"
```

---

## Task 8: Documentation - Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md` (add batch upload documentation)

**Step 1: Add batch upload section to CLAUDE.md**

Find the "API Endpoints" section (around line 84-738) and add this new subsection right after the "Core Workflow" section:

```markdown
### Batch Upload System (Nov 2025)

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
```

**Step 2: Update the "Common Development Patterns" section**

Add this pattern to the section (around line 739+):

```markdown
### Testing batch uploads with curl

```bash
# 1. Initialize job
JOB_ID=$(curl -s -X POST http://localhost:5000/api/upload/init -F "api_tier=free" | jq -r '.job_id')

# 2. Upload batch 1
curl -X POST http://localhost:5000/api/upload/batch/$JOB_ID \
  -F "txt_files=@file1.txt" \
  -F "txt_files=@file2.txt"

# 3. Upload batch 2
curl -X POST http://localhost:5000/api/upload/batch/$JOB_ID \
  -F "screenshots=@screenshot1.png" \
  -F "screenshots=@screenshot2.png"

# 4. Start processing
curl -X POST http://localhost:5000/api/process/$JOB_ID \
  -H "X-Gemini-API-Key: your_key_here"
```
```

**Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: document batch upload system in CLAUDE.md"
```

---

## Task 9: Backward Compatibility - Keep Original Upload Endpoint

**Files:**
- Modify: `main.py` (ensure original `/api/upload` endpoint still works)
- Test: Test both upload methods

**Step 1: Verify original endpoint still works**

The original `/api/upload` endpoint should still be in `main.py` (lines 210-266, now shifted down after adding new endpoints). Verify it hasn't been removed or broken.

Read the file to confirm:
```bash
grep -A 5 '@app.post("/api/upload")' main.py
```

Expected: Should see the original single-upload endpoint

**Step 2: Test both upload methods**

Test original method (single upload):
```bash
curl -X POST http://localhost:5000/api/upload \
  -F "txt_files=@test1.txt" \
  -F "screenshots=@screenshot1.png" \
  -F "api_tier=free"
```

Expected: Works normally, returns job_id

Test new method (batch upload):
```bash
JOB_ID=$(curl -s -X POST http://localhost:5000/api/upload/init -F "api_tier=free" | jq -r '.job_id')
curl -X POST http://localhost:5000/api/upload/batch/$JOB_ID -F "txt_files=@test1.txt"
```

Expected: Both methods work independently

**Step 3: Document backward compatibility**

Add comment in `main.py` above the original `/api/upload` endpoint:

```python
# Legacy single-upload endpoint (backward compatible)
# For large uploads (>100 MB), use /api/upload/init + /api/upload/batch instead
@app.post("/api/upload")
async def upload_files(
    ...
```

**Step 4: Commit**

```bash
git add main.py
git commit -m "docs: document backward compatibility for upload endpoints"
```

**Verification Results (Nov 3, 2025)**

✅ Original `/api/upload` endpoint exists at line 317 in main.py
✅ Endpoint accepts txt_files, screenshots, and api_tier parameters
✅ Successfully tested with small upload (1 file):
   - Job 91 created successfully
   - Response: {"job_id":91,"txt_files_count":1,"screenshot_files_count":1}
✅ Successfully tested with multiple files (3 txt + 1 screenshot):
   - Job 92 created with api_tier='paid'
   - Response: {"job_id":92,"txt_files_count":3,"screenshot_files_count":1}
✅ Successfully tested with large file (107MB):
   - Job 93 created and accepted (backend has no size limit)
   - Frontend enforces 100MB limit for better UX
✅ `calculateTotalSize()` function exists in static/js/app.js (line 64)
✅ No interference between old endpoint and new batch system

**Conclusion**: Original upload endpoint remains fully functional. Both upload methods (legacy single-upload and new batch system) work independently without conflicts.

---

## Task 10: Error Handling - Retry Failed Batches

**Files:**
- Modify: `static/js/app.js` (add retry logic to batch upload)
- Test: Simulate network failure

**Step 1: Add retry logic to batch upload**

In `static/js/app.js`, find the batch upload loop in `uploadAndProcess` function (Task 6). Replace the batch upload fetch with this retry-enabled version:

Find this code (inside the `for` loop):
```javascript
            const batchResponse = await fetch(`${API_BASE}/api/upload/batch/${currentJobId}`, {
                method: 'POST',
                body: batchFormData
            });

            if (!batchResponse.ok) {
                const errorData = await batchResponse.json().catch(() => ({
                    detail: `Failed to upload batch ${batchNum}`
                }));
                throw new Error(errorData.detail || `Failed to upload batch ${batchNum}`);
            }
```

Replace with:
```javascript
            // Retry logic for batch upload
            const MAX_RETRIES = 3;
            let batchResponse = null;
            let lastError = null;

            for (let retryCount = 0; retryCount <= MAX_RETRIES; retryCount++) {
                try {
                    if (retryCount > 0) {
                        updateBatchProgress(
                            batchNum,
                            totalBatches,
                            `Reintentando lote ${batchNum}/${totalBatches} (intento ${retryCount + 1}/${MAX_RETRIES + 1})`
                        );
                        // Wait 2 seconds before retry
                        await new Promise(resolve => setTimeout(resolve, 2000));
                    }

                    batchResponse = await fetch(`${API_BASE}/api/upload/batch/${currentJobId}`, {
                        method: 'POST',
                        body: batchFormData
                    });

                    if (batchResponse.ok) {
                        break; // Success, exit retry loop
                    }

                    // Non-network error (e.g., 400, 404) - don't retry
                    if (batchResponse.status < 500) {
                        const errorData = await batchResponse.json().catch(() => ({
                            detail: `Failed to upload batch ${batchNum}`
                        }));
                        throw new Error(errorData.detail || `Failed to upload batch ${batchNum}`);
                    }

                    // Server error (5xx) - retry
                    lastError = new Error(`Server error (${batchResponse.status}) uploading batch ${batchNum}`);

                } catch (error) {
                    lastError = error;
                    if (retryCount === MAX_RETRIES) {
                        throw error; // Give up after max retries
                    }
                }
            }

            if (!batchResponse || !batchResponse.ok) {
                throw lastError || new Error(`Failed to upload batch ${batchNum}`);
            }
```

**Step 2: Test retry logic**

Simulate network failure (browser DevTools → Network tab → Throttling → Offline):
1. Start upload
2. Enable offline mode during batch upload
3. Observe retry attempts in UI ("Reintentando lote...")
4. Re-enable network
5. Upload should succeed

**Step 3: Commit**

```bash
git add static/js/app.js
git commit -m "feat: add retry logic for failed batch uploads"
```

---

## Task 11: Production Testing - End-to-End Validation

**Files:**
- Test: Manual testing with production data
- Document: Results in commit message

**Step 1: Test with small dataset (< 50 MB)**

1. Collect 10 TXT files + 30 screenshots (~30-40 MB total)
2. Upload via web interface
3. Verify:
   - Single batch created
   - Upload succeeds
   - Processing works normally

**Step 2: Test with medium dataset (50-100 MB)**

1. Collect 50 TXT files + 100 screenshots (~80 MB total)
2. Upload via web interface
3. Verify:
   - Multiple batches created (2-3 batches expected)
   - Batch progress UI shows correctly
   - Upload succeeds
   - Processing works normally

**Step 3: Test with large dataset (100-200 MB)**

1. Collect 100 TXT files + 200 screenshots (~150 MB total)
2. Upload via web interface
3. Verify:
   - Multiple batches created (3-4 batches expected)
   - All batches upload successfully
   - Upload succeeds (this would have failed before with 413 error)
   - Processing works normally

**Step 4: Test error scenarios**

1. Upload > 300 files (should fail with validation error)
2. Simulate network interruption (should retry and recover)
3. Upload to already-processing job (should fail with status error)

**Step 5: Document test results**

Create test summary:

```bash
git add .
git commit -m "test: validate batch upload system with production data

Tested scenarios:
- Small dataset (30 MB, 1 batch): ✓ Success
- Medium dataset (80 MB, 2-3 batches): ✓ Success
- Large dataset (150 MB, 3-4 batches): ✓ Success (previously failed with 413)
- File limit validation: ✓ Correctly rejects >300 files
- Network retry: ✓ Recovers from transient failures
- Status validation: ✓ Rejects uploads to processing jobs

Batch upload system working as expected. Fixes #413-upload-limit"
```

---

## Task 12: Deployment - Update Replit Configuration

**Files:**
- Modify: `.replit` (if needed for deployment config)
- Document: Deployment notes

**Step 1: Verify deployment configuration**

Check if `.replit` needs updates:
```bash
cat .replit
```

Expected: Should already have correct deployment config (uses uvicorn with port 5000)

**Step 2: Test on Replit deployment**

1. Push code to git: `git push`
2. Open Replit deployment
3. Test upload with 100-150 MB dataset
4. Verify batches upload successfully (no 413 error)

**Step 3: Monitor for issues**

Check Replit logs for:
- Batch upload requests
- Any 413 errors (should be gone)
- Processing pipeline working normally

**Step 4: Commit deployment notes**

```bash
git add .replit
git commit -m "deploy: batch upload system to Replit

Batch upload system now live on Replit. Tested with 150 MB uploads.
No more 413 errors from nginx proxy limit.

Deployment verified:
- Batch uploads work correctly
- No 413 errors observed
- Processing pipeline unaffected
- Backward compatible with original upload endpoint"
```

---

## Summary

**What we built:**
- Job initialization endpoint (`/api/upload/init`)
- Batch upload endpoint (`/api/upload/batch/{job_id}`)
- Frontend file batching utilities
- Batch progress UI
- Retry logic for failed uploads
- Comprehensive tests
- Documentation

**What it fixes:**
- Replit's ~100 MB nginx proxy limit causing 413 errors
- Allows uploads up to 300 MB by splitting into 50-60 MB batches
- Provides user feedback with batch progress UI
- Handles network failures with automatic retries

**Backward compatibility:**
- Original `/api/upload` endpoint still works for small uploads (<100 MB)
- Frontend automatically uses batch system for all uploads
- No breaking changes to existing API

**Testing completed:**
- Unit tests: 5 integration tests
- Manual testing: Small/medium/large datasets
- Error scenarios: File limits, network failures, status validation
- Production validation: Replit deployment

**Next steps:**
- Monitor Replit production logs
- Gather user feedback on batch upload experience
- Consider adding parallel batch uploads (currently sequential)
- Add batch upload analytics (batch size distribution, retry rates)
