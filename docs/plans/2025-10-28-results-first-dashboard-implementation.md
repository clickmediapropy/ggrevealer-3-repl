# Results-First Dashboard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform GGRevealer UI to show job results first with quality scores, hide dev tools, and enable multi-job workflows.

**Architecture:** 5-phase incremental implementation - layout reorder → job card enhancement → upload modal → settings panel → in-place processing. Each phase is non-breaking and independently testable.

**Tech Stack:** Bootstrap 5, Vanilla JS, Jinja2 templates, existing FastAPI backend (no API changes)

---

## Phase 1: Layout Restructure (Non-Breaking)

### Task 1: Reorder HTML sections for jobs-first layout

**Files:**
- Modify: `templates/index.html:23-307`

**Step 1: Move jobs section above welcome section**

In `templates/index.html`, cut lines 302-307 (jobs section) and paste after line 21 (after navbar).

**Step 2: Add persistent "New Job" button at top**

Add after navbar (line 22):
```html
<div class="container my-4">
    <button id="new-job-btn-top" class="btn btn-primary btn-lg w-100">
        <i class="bi bi-plus-circle"></i> New Job
    </button>
</div>
```

**Step 3: Hide dev mode section**

In `templates/index.html` line 24, change:
```html
<div id="dev-mode-section" class="row mb-4">
```
To:
```html
<div id="dev-mode-section" class="row mb-4 d-none">
```

**Step 4: Add settings icon to navbar**

In `templates/index.html` line 12-20, replace navbar content:
```html
<nav class="navbar navbar-dark bg-dark">
    <div class="container">
        <a class="navbar-brand" href="#">
            <i class="bi bi-puzzle"></i> GGRevealer
        </a>
        <div class="d-flex align-items-center">
            <span class="navbar-text me-3">
                Poker Hand De-anonymizer
            </span>
            <button id="settings-btn" class="btn btn-outline-light btn-sm">
                <i class="bi bi-gear"></i>
            </button>
        </div>
    </div>
</nav>
```

**Step 5: Verify layout**

Run: `python main.py`
Open: `http://localhost:5000/app`
Expected: Jobs section at top, "New Job" button visible, dev mode hidden, settings icon in navbar

**Step 6: Commit**

```bash
git add templates/index.html
git commit -m "feat: reorder UI for jobs-first dashboard

- Move jobs section above welcome section
- Add persistent New Job button
- Hide dev mode section (move to settings later)
- Add settings icon to navbar"
```

---

### Task 2: Wire up new job button

**Files:**
- Modify: `static/js/app.js:778-779`

**Step 1: Add click handler for top new job button**

In `app.js` after line 779:
```javascript
// Wire up top new job button
const newJobBtnTop = document.getElementById('new-job-btn-top');
if (newJobBtnTop) {
    newJobBtnTop.addEventListener('click', resetToWelcome);
}
```

**Step 2: Test button functionality**

Run: `python main.py`
Open: `http://localhost:5000/app`
Click: "New Job" button at top
Expected: Scrolls to welcome section, resets file lists

**Step 3: Commit**

```bash
git add static/js/app.js
git commit -m "feat: wire up persistent New Job button"
```

---

## Phase 2: Job Card Enhancement

### Task 3: Add quality score calculation

**Files:**
- Modify: `static/js/app.js:803-893`

**Step 1: Add quality score calculation to renderJobs**

In `app.js` line 811 (inside jobs.forEach loop), add after `const div = document.createElement('div');`:
```javascript
// Calculate quality score
const stats = job.detailed_stats || {};
const successfulCount = (stats.successful_files || []).length;
const failedCount = (stats.failed_files || []).length;
const totalTables = successfulCount + failedCount;
const qualityScore = totalTables > 0 ? Math.round((successfulCount / totalTables) * 100) : 0;
```

**Step 2: Add quality score to card HTML**

Replace existing card innerHTML (lines 827-889) with:
```javascript
div.innerHTML = `
    <div class="job-card-header" onclick="toggleJobCard(${job.id})">
        <div class="job-card-left">
            <span class="job-id">Job #${job.id}</span>
            <span class="${statusClass}">
                <i class="bi ${statusIcon}"></i> ${job.status}
            </span>
            ${job.status === 'completed' && totalTables > 0 ? `
                <span class="quality-score ms-3">
                    📊 ${qualityScore}% (${successfulCount}/${totalTables} tables)
                </span>
            ` : ''}
        </div>
        <div class="job-card-right">
            ${job.status === 'completed' ? `
                <button class="btn btn-sm btn-success me-2" onclick="event.stopPropagation(); downloadResult(${job.id})">
                    <i class="bi bi-download"></i> Download
                </button>
            ` : ''}
            <i class="bi bi-chevron-down toggle-icon"></i>
        </div>
    </div>
    <div class="job-card-body" id="job-body-${job.id}" style="display: none;">
        <div class="job-details-grid">
            <div class="detail-item">
                <i class="bi bi-calendar"></i>
                <span>${createdDate}</span>
            </div>
            <div class="detail-item">
                <i class="bi bi-clock"></i>
                <span>${processingTime}</span>
            </div>
            <div class="detail-item">
                <i class="bi bi-file-text"></i>
                <span>${job.txt_files_count} archivos TXT</span>
            </div>
            <div class="detail-item">
                <i class="bi bi-image"></i>
                <span>${job.screenshot_files_count} screenshots</span>
            </div>
        </div>

        ${job.status === 'completed' && totalTables > 0 ? `
            <div class="quality-bar mt-3 mb-3">
                <div class="progress" style="height: 20px;">
                    <div class="progress-bar bg-success" style="width: ${qualityScore}%">${qualityScore}%</div>
                    ${failedCount > 0 ? `<div class="progress-bar bg-warning" style="width: ${100 - qualityScore}%">${100 - qualityScore}%</div>` : ''}
                </div>
                <div class="mt-2 small">
                    ${successfulCount > 0 ? `<span class="text-success me-3">✅ ${successfulCount} tables ready</span>` : ''}
                    ${failedCount > 0 ? `<span class="text-warning">⚠️ ${failedCount} tables need attention</span>` : ''}
                </div>
            </div>
        ` : ''}

        ${job.status === 'completed' ? `
            <div class="job-stats-grid mt-3">
                <div class="job-stat">
                    <div class="job-stat-value">${job.hands_parsed || 0}</div>
                    <div class="job-stat-label">Manos Parseadas</div>
                </div>
                <div class="job-stat">
                    <div class="job-stat-value">${job.matched_hands || 0}</div>
                    <div class="job-stat-label">Manos Matched</div>
                </div>
                <div class="job-stat">
                    <div class="job-stat-value">${job.name_mappings_count || 0}</div>
                    <div class="job-stat-label">Nombres Resueltos</div>
                </div>
                <div class="job-stat">
                    <div class="job-stat-value">${job.screenshot_files_count > 0 ? Math.round((job.matched_hands / job.screenshot_files_count) * 100) : 0}%</div>
                    <div class="job-stat-label">Tasa de Éxito OCR</div>
                </div>
            </div>
        ` : ''}
        ${job.error_message ? `
            <div class="alert alert-danger mt-3 mb-0">
                <i class="bi bi-exclamation-triangle"></i> ${job.error_message}
            </div>
        ` : ''}
    </div>
`;
```

**Step 3: Add CSS for quality score**

In `static/css/styles.css` after line 256 (after `.status-badge-pending`):
```css
.quality-score {
    font-size: 0.9rem;
    color: #0d6efd;
    font-weight: 500;
}

.quality-bar {
    border-left: 4px solid #0d6efd;
    padding-left: 15px;
}
```

**Step 4: Test quality score display**

Run: `python main.py`
Open: `http://localhost:5000/app`
Expected: Completed jobs show "📊 83% (5/6 tables)" inline with job ID

**Step 5: Commit**

```bash
git add static/js/app.js static/css/styles.css
git commit -m "feat: add quality score to job cards

- Calculate quality score from successful/failed tables
- Display inline with job ID
- Add progress bar with green/yellow split
- Show table counts in expanded state"
```

---

## Phase 3: Settings Panel

### Task 4: Create settings panel HTML

**Files:**
- Modify: `templates/index.html:307` (before closing container)

**Step 1: Add settings panel HTML**

Add before line 307 (`</div>` before scripts):
```html
<!-- Settings Panel -->
<div id="settings-panel" class="settings-panel">
    <div class="settings-panel-header">
        <h5><i class="bi bi-gear"></i> Settings</h5>
        <button id="close-settings-btn" class="btn-close"></button>
    </div>
    <div class="settings-panel-body">
        <h6>🔧 Developer Tools</h6>
        <div class="form-check form-switch mb-3">
            <input class="form-check-input" type="checkbox" id="dev-mode-toggle">
            <label class="form-check-label" for="dev-mode-toggle">
                Enable Developer Mode
            </label>
        </div>

        <hr>

        <h6>🔄 Reprocess Job</h6>
        <div class="mb-3">
            <label for="settings-job-id" class="form-label">Job ID</label>
            <input type="number" class="form-control" id="settings-job-id" value="3" min="1">
        </div>
        <div id="settings-job-info" class="small text-muted mb-3">
            Loading job info...
        </div>
        <button id="settings-reprocess-btn" class="btn btn-warning w-100">
            <i class="bi bi-arrow-clockwise"></i> Reprocess Job
        </button>

        <hr>

        <h6>ℹ️ About</h6>
        <p class="small text-muted mb-0">
            <strong>Version:</strong> 3.0<br>
            <strong>API:</strong> <span id="api-status">Connected</span>
        </p>
    </div>
</div>
<div id="settings-backdrop" class="settings-backdrop"></div>
```

**Step 2: Add settings panel CSS**

In `static/css/styles.css` after line 403:
```css
/* Settings Panel */
.settings-panel {
    position: fixed;
    top: 0;
    right: -350px;
    width: 320px;
    height: 100vh;
    background-color: #fff;
    box-shadow: -2px 0 8px rgba(0,0,0,0.15);
    z-index: 1050;
    transition: right 0.3s ease;
    overflow-y: auto;
}

.settings-panel.open {
    right: 0;
}

.settings-panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 20px;
    border-bottom: 1px solid #dee2e6;
    background-color: #f8f9fa;
}

.settings-panel-header h5 {
    margin: 0;
}

.settings-panel-body {
    padding: 20px;
}

.settings-panel-body h6 {
    margin-top: 15px;
    margin-bottom: 10px;
    font-weight: 600;
}

.settings-panel-body hr {
    margin: 20px 0;
}

.settings-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100vh;
    background-color: rgba(0,0,0,0.5);
    z-index: 1040;
    display: none;
}

.settings-backdrop.open {
    display: block;
}
```

**Step 3: Test panel structure**

Run: `python main.py`
Open: `http://localhost:5000/app`
Open DevTools Console, run: `document.getElementById('settings-panel').classList.add('open')`
Expected: Panel slides in from right

**Step 4: Commit**

```bash
git add templates/index.html static/css/styles.css
git commit -m "feat: add settings panel structure

- Create slide-in panel with dev tools section
- Add reprocess job functionality placeholder
- Add about section with version info
- Style panel and backdrop"
```

---

### Task 5: Wire up settings panel behavior

**Files:**
- Modify: `static/js/app.js:1233` (end of file)

**Step 1: Add settings panel controls**

Add at end of `app.js`:
```javascript
// ============================================================================
// SETTINGS PANEL
// ============================================================================

const settingsBtn = document.getElementById('settings-btn');
const settingsPanel = document.getElementById('settings-panel');
const settingsBackdrop = document.getElementById('settings-backdrop');
const closeSettingsBtn = document.getElementById('close-settings-btn');
const devModeToggle = document.getElementById('dev-mode-toggle');

function openSettings() {
    settingsPanel.classList.add('open');
    settingsBackdrop.classList.add('open');

    // Load dev mode state from localStorage
    const devMode = localStorage.getItem('devMode') === 'on';
    devModeToggle.checked = devMode;

    // Load job info
    const jobId = parseInt(document.getElementById('settings-job-id').value);
    if (jobId && jobId > 0) {
        loadSettingsJobInfo(jobId);
    }
}

function closeSettings() {
    settingsPanel.classList.remove('open');
    settingsBackdrop.classList.remove('open');
}

async function loadSettingsJobInfo(jobId) {
    const jobInfo = document.getElementById('settings-job-info');

    if (!jobId || jobId < 1) {
        jobInfo.innerHTML = '<span class="text-danger">Job ID inválido</span>';
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/status/${jobId}`);

        if (!response.ok) {
            jobInfo.innerHTML = '<span class="text-danger">Job no encontrado</span>';
            return;
        }

        const job = await response.json();
        const stats = job.statistics || {};

        jobInfo.innerHTML = `
            <strong>Status:</strong> <span class="badge bg-${getStatusBadgeColor(job.status)}">${job.status}</span><br>
            <strong>Archivos:</strong> ${stats.txt_files || 0} TXT, ${stats.screenshots || 0} screenshots<br>
            <strong>Hands:</strong> ${stats.hands_parsed || 0} parseadas, ${stats.matched_hands || 0} matched
        `;
    } catch (error) {
        console.error('Error loading settings job info:', error);
        jobInfo.innerHTML = '<span class="text-danger">Error al cargar info del job</span>';
    }
}

// Event listeners
if (settingsBtn) settingsBtn.addEventListener('click', openSettings);
if (closeSettingsBtn) closeSettingsBtn.addEventListener('click', closeSettings);
if (settingsBackdrop) settingsBackdrop.addEventListener('click', closeSettings);

if (devModeToggle) {
    devModeToggle.addEventListener('change', (e) => {
        localStorage.setItem('devMode', e.target.checked ? 'on' : 'off');

        // Toggle dev mode section visibility
        const devModeSection = document.getElementById('dev-mode-section');
        if (devModeSection) {
            if (e.target.checked) {
                devModeSection.classList.remove('d-none');
            } else {
                devModeSection.classList.add('d-none');
            }
        }
    });
}

const settingsJobIdInput = document.getElementById('settings-job-id');
if (settingsJobIdInput) {
    settingsJobIdInput.addEventListener('input', (e) => {
        const jobId = parseInt(e.target.value);
        if (jobId && jobId > 0) {
            loadSettingsJobInfo(jobId);
        }
    });
}

const settingsReprocessBtn = document.getElementById('settings-reprocess-btn');
if (settingsReprocessBtn) {
    settingsReprocessBtn.addEventListener('click', async () => {
        const jobId = parseInt(document.getElementById('settings-job-id').value);

        if (!jobId || jobId < 1) {
            alert('Por favor ingresa un Job ID válido');
            return;
        }

        settingsReprocessBtn.disabled = true;
        settingsReprocessBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Iniciando...';

        try {
            const response = await fetch(`${API_BASE}/api/process/${jobId}`, {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to start processing');
            }

            const data = await response.json();
            currentJobId = jobId;

            // Close settings and show processing
            closeSettings();
            showProcessing();
            startTimer();
            startStatusPolling();

            console.log(`✅ ${data.is_reprocess ? 'Reprocesando' : 'Procesando'} job ${jobId}`);

        } catch (error) {
            console.error('Error reprocessing job:', error);
            alert('Error al reprocesar job: ' + error.message);

            settingsReprocessBtn.disabled = false;
            settingsReprocessBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Reprocesar Job';
        }
    });
}
```

**Step 2: Test settings panel**

Run: `python main.py`
Open: `http://localhost:5000/app`
Click: Settings icon in navbar
Expected: Panel slides in, backdrop appears, close button works
Toggle: Dev mode switch
Expected: Original dev mode section appears/disappears

**Step 3: Commit**

```bash
git add static/js/app.js
git commit -m "feat: wire up settings panel interactions

- Open/close panel with settings icon and backdrop
- Persist dev mode toggle to localStorage
- Show/hide original dev mode section based on toggle
- Load job info for reprocessing
- Wire up reprocess button"
```

---

## Phase 4: Upload Modal (Simplified - Keep Existing for Now)

### Task 6: Add file count summary to existing upload section

**Files:**
- Modify: `templates/index.html:89` and `templates/index.html:106`
- Modify: `static/js/app.js:64-80,113-129`

**Step 1: Add file summary display**

In `templates/index.html` after line 87 (after dropzone close):
```html
<div id="txt-summary" class="mt-2 text-center d-none">
    <span class="badge bg-primary">
        <i class="bi bi-check-circle"></i> <span id="txt-count">0</span> files (<span id="txt-size">0</span> MB)
    </span>
</div>
```

In `templates/index.html` after line 104 (after screenshot dropzone close):
```html
<div id="screenshot-summary" class="mt-2 text-center d-none">
    <span class="badge bg-success">
        <i class="bi bi-check-circle"></i> <span id="screenshot-count">0</span> files (<span id="screenshot-size">0</span> MB)
    </span>
</div>
```

**Step 2: Update renderTxtFiles to show summary**

In `app.js` replace `renderTxtFiles()` function (lines 64-80):
```javascript
function renderTxtFiles() {
    const summary = document.getElementById('txt-summary');
    const countSpan = document.getElementById('txt-count');
    const sizeSpan = document.getElementById('txt-size');

    if (txtFiles.length > 0) {
        const totalSize = txtFiles.reduce((sum, file) => sum + file.size, 0);
        const sizeMB = (totalSize / (1024 * 1024)).toFixed(2);

        countSpan.textContent = txtFiles.length;
        sizeSpan.textContent = sizeMB;
        summary.classList.remove('d-none');
    } else {
        summary.classList.add('d-none');
    }

    txtFilesList.innerHTML = '';
    txtFiles.forEach((file, index) => {
        const div = document.createElement('div');
        div.className = 'file-item';
        div.innerHTML = `
            <span><i class="bi bi-file-text"></i> ${file.name}</span>
            <i class="bi bi-x-circle remove-btn" data-index="${index}"></i>
        `;
        div.querySelector('.remove-btn').addEventListener('click', () => {
            txtFiles.splice(index, 1);
            renderTxtFiles();
            updateUploadButton();
        });
        txtFilesList.appendChild(div);
    });
}
```

**Step 3: Update renderScreenshotFiles to show summary**

In `app.js` replace `renderScreenshotFiles()` function (lines 113-129):
```javascript
function renderScreenshotFiles() {
    const summary = document.getElementById('screenshot-summary');
    const countSpan = document.getElementById('screenshot-count');
    const sizeSpan = document.getElementById('screenshot-size');

    if (screenshotFiles.length > 0) {
        const totalSize = screenshotFiles.reduce((sum, file) => sum + file.size, 0);
        const sizeMB = (totalSize / (1024 * 1024)).toFixed(2);

        countSpan.textContent = screenshotFiles.length;
        sizeSpan.textContent = sizeMB;
        summary.classList.remove('d-none');
    } else {
        summary.classList.add('d-none');
    }

    screenshotFilesList.innerHTML = '';
    screenshotFiles.forEach((file, index) => {
        const div = document.createElement('div');
        div.className = 'file-item';
        div.innerHTML = `
            <span><i class="bi bi-image"></i> ${file.name}</span>
            <i class="bi bi-x-circle remove-btn" data-index="${index}"></i>
        `;
        div.querySelector('.remove-btn').addEventListener('click', () => {
            screenshotFiles.splice(index, 1);
            renderScreenshotFiles();
            updateUploadButton();
        });
        screenshotFilesList.appendChild(div);
    });
}
```

**Step 4: Make file lists scrollable with max height**

In `static/css/styles.css` after line 56:
```css
.file-item-container {
    max-height: 200px;
    overflow-y: auto;
}
```

Update `templates/index.html` lines 89 and 106 to wrap file lists:
```html
<div id="txt-files-list" class="mt-3 file-item-container"></div>
```
```html
<div id="screenshot-files-list" class="mt-3 file-item-container"></div>
```

**Step 5: Test file summaries**

Run: `python main.py`
Open: `http://localhost:5000/app`
Add: 10 TXT files and 10 screenshots
Expected: Summary badges show "10 files (X MB)", file list scrolls after 200px

**Step 6: Commit**

```bash
git add templates/index.html static/js/app.js static/css/styles.css
git commit -m "feat: add file count summaries to upload section

- Show total count and size for TXT and screenshots
- Make file lists scrollable (max 200px height)
- Update summaries when files added/removed"
```

---

## Validation & Final Steps

### Task 7: Verify all phases work together

**Step 1: Test complete workflow**

Run: `python main.py`
Open: `http://localhost:5000/app`

**Checklist:**
- [ ] Jobs section displays at top (Phase 1)
- [ ] "New Job" button visible and works (Phase 1)
- [ ] Dev mode section hidden by default (Phase 1)
- [ ] Settings icon in navbar (Phase 1)
- [ ] Completed jobs show quality score (Phase 2)
- [ ] Quality progress bar displays correctly (Phase 2)
- [ ] Settings panel opens/closes smoothly (Phase 3)
- [ ] Dev mode toggle works (Phase 3)
- [ ] Reprocess functionality accessible in settings (Phase 3)
- [ ] File upload summaries display (Phase 4)
- [ ] File lists scroll when > 200px (Phase 4)

**Step 2: Test with real job**

Upload: 5 TXT files + 5 screenshots
Process: New job
Expected: Quality score appears in job card after completion

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: complete Results-First Dashboard Phase 1-4

All non-breaking changes implemented:
- Jobs-first layout
- Quality scores on job cards
- Settings panel with dev tools
- File upload improvements

Phase 5 (in-place processing) deferred to avoid breaking existing workflow."
```

---

## Notes on Phase 5 (Deferred)

**Phase 5: Processing In-Place** is intentionally deferred because it changes core workflow:
- Requires refactoring `showProcessing()` to work inside job cards
- Needs careful state management for multiple simultaneous jobs
- Risk of breaking existing polling/status updates

**Recommendation:** Deploy Phases 1-4, gather user feedback, then tackle Phase 5 separately with dedicated testing.

---

## Success Criteria Met

✅ Jobs displayed first (most common action)
✅ Quality scores visible without expanding cards
✅ Dev mode hidden from production users
✅ File upload handles 200+ files without scrolling issues
✅ Settings panel accessible but non-intrusive
✅ Zero breaking changes to existing functionality
