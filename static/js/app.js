const API_BASE = window.location.origin;

// File upload limits (must match backend limits in main.py)
const MAX_TXT_FILES = 300;
const MAX_SCREENSHOT_FILES = 300;
const MAX_UPLOAD_SIZE_MB = 300;
const MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024;

let txtFiles = [];
let screenshotFiles = [];
let currentJobId = null;
let statusCheckInterval = null;
let timerInterval = null;
let startTime = null;

const txtDropzone = document.getElementById('txt-dropzone');
const txtInput = document.getElementById('txt-input');
const txtFilesList = document.getElementById('txt-files-list');

const screenshotDropzone = document.getElementById('screenshot-dropzone');
const screenshotInput = document.getElementById('screenshot-input');
const screenshotFilesList = document.getElementById('screenshot-files-list');

const uploadBtn = document.getElementById('upload-btn');

const welcomeSection = document.getElementById('welcome-section');
const processingSection = document.getElementById('processing-section');
const resultsSection = document.getElementById('results-section');
const errorSection = document.getElementById('error-section');

const statusText = document.getElementById('status-text');
const resultsStats = document.getElementById('results-stats');
const downloadBtn = document.getElementById('download-btn');
const newJobBtn = document.getElementById('new-job-btn');
const retryBtn = document.getElementById('retry-btn');
const errorMessage = document.getElementById('error-message');
const jobsList = document.getElementById('jobs-list');

if (txtDropzone && txtInput) {
    txtDropzone.addEventListener('click', () => txtInput.click());
}

if (txtDropzone) {
    txtDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        txtDropzone.classList.add('active');
    });

    txtDropzone.addEventListener('dragleave', () => {
        txtDropzone.classList.remove('active');
    });

    txtDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        txtDropzone.classList.remove('active');
        handleTxtFiles(e.dataTransfer.files);
    });
}

if (txtInput) {
    txtInput.addEventListener('change', (e) => {
        handleTxtFiles(e.target.files);
    });
}

function handleTxtFiles(files) {
    for (let file of files) {
        if (file.name.endsWith('.txt')) {
            txtFiles.push(file);
        }
    }

    // Check if limit exceeded
    if (txtFiles.length > MAX_TXT_FILES) {
        showWarning(`Has agregado ${txtFiles.length} archivos TXT. El límite es ${MAX_TXT_FILES}. Por favor, elimina algunos archivos.`);
    }

    renderTxtFiles();
    updateUploadButton();
}

function renderTxtFiles() {
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
            updateSizeIndicator();
        });
        txtFilesList.appendChild(div);
    });

    // Update counter badge with warning if exceeds limit
    const txtCountBadge = document.getElementById('txt-count-badge');
    if (txtCountBadge) {
        const count = txtFiles.length;
        txtCountBadge.textContent = count === 1 ? '1 archivo' : `${count} archivos`;

        // Add visual warning if exceeds limit
        if (count > MAX_TXT_FILES) {
            txtCountBadge.classList.remove('bg-secondary');
            txtCountBadge.classList.add('bg-danger');
        } else {
            txtCountBadge.classList.remove('bg-danger');
            txtCountBadge.classList.add('bg-secondary');
        }
    }

    updateSizeIndicator();
}

if (screenshotDropzone && screenshotInput) {
    screenshotDropzone.addEventListener('click', () => screenshotInput.click());
}

if (screenshotDropzone) {
    screenshotDropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        screenshotDropzone.classList.add('active');
    });

    screenshotDropzone.addEventListener('dragleave', () => {
        screenshotDropzone.classList.remove('active');
    });

    screenshotDropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        screenshotDropzone.classList.remove('active');
        handleScreenshotFiles(e.dataTransfer.files);
    });
}

if (screenshotInput) {
    screenshotInput.addEventListener('change', (e) => {
        handleScreenshotFiles(e.target.files);
    });
}

function handleScreenshotFiles(files) {
    for (let file of files) {
        if (file.name.match(/\.(png|jpg|jpeg)$/i)) {
            screenshotFiles.push(file);
        }
    }

    // Check if limit exceeded
    if (screenshotFiles.length > MAX_SCREENSHOT_FILES) {
        showWarning(`Has agregado ${screenshotFiles.length} screenshots. El límite es ${MAX_SCREENSHOT_FILES}. Por favor, elimina algunos archivos.`);
    }

    renderScreenshotFiles();
    updateUploadButton();
}

function renderScreenshotFiles() {
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
            updateSizeIndicator();
        });
        screenshotFilesList.appendChild(div);
    });

    // Update counter badge with warning if exceeds limit
    const screenshotCountBadge = document.getElementById('screenshot-count-badge');
    if (screenshotCountBadge) {
        const count = screenshotFiles.length;
        screenshotCountBadge.textContent = count === 1 ? '1 archivo' : `${count} archivos`;

        // Add visual warning if exceeds limit
        if (count > MAX_SCREENSHOT_FILES) {
            screenshotCountBadge.classList.remove('bg-secondary');
            screenshotCountBadge.classList.add('bg-danger');
        } else {
            screenshotCountBadge.classList.remove('bg-danger');
            screenshotCountBadge.classList.add('bg-secondary');
        }
    }

    updateSizeIndicator();
}

function calculateTotalSize() {
    let total = 0;
    txtFiles.forEach(file => total += file.size);
    screenshotFiles.forEach(file => total += file.size);
    return total;
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

function updateSizeIndicator() {
    const sizeIndicator = document.getElementById('size-indicator');
    const totalSizeSpan = document.getElementById('total-size');
    const totalFilesSpan = document.getElementById('total-files');

    if (!sizeIndicator || !totalSizeSpan || !totalFilesSpan) return;

    const totalFiles = txtFiles.length + screenshotFiles.length;
    const totalSize = calculateTotalSize();

    if (totalFiles === 0) {
        sizeIndicator.style.display = 'none';
        return;
    }

    sizeIndicator.style.display = 'block';

    // Update total size
    const sizeMB = (totalSize / (1024 * 1024)).toFixed(2);
    totalSizeSpan.textContent = sizeMB + ' MB';

    // Color based on size
    if (totalSize > MAX_UPLOAD_SIZE_BYTES) {
        totalSizeSpan.className = 'text-danger fw-bold';
    } else if (totalSize > MAX_UPLOAD_SIZE_BYTES * 0.9) {
        totalSizeSpan.className = 'text-warning fw-bold';
    } else {
        totalSizeSpan.className = '';
    }

    // Update total files count
    totalFilesSpan.textContent = totalFiles;

    // Color based on file count
    if (txtFiles.length > MAX_TXT_FILES || screenshotFiles.length > MAX_SCREENSHOT_FILES) {
        totalFilesSpan.className = 'text-danger fw-bold';
    } else if (txtFiles.length > MAX_TXT_FILES * 0.9 || screenshotFiles.length > MAX_SCREENSHOT_FILES * 0.9) {
        totalFilesSpan.className = 'text-warning fw-bold';
    } else {
        totalFilesSpan.className = '';
    }
}

function showWarning(message) {
    // Create a warning toast/alert
    const alertDiv = document.createElement('div');
    alertDiv.className = 'alert alert-warning alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3';
    alertDiv.style.zIndex = '9999';
    alertDiv.style.minWidth = '400px';
    alertDiv.innerHTML = `
        <i class="bi bi-exclamation-triangle-fill me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.body.appendChild(alertDiv);

    // Auto-remove after 5 seconds
    setTimeout(() => {
        alertDiv.remove();
    }, 5000);
}

function updateUploadButton() {
    if (!uploadBtn) return;
    
    uploadBtn.disabled = txtFiles.length === 0 || screenshotFiles.length === 0;

    // Show warnings if limits are exceeded
    if (txtFiles.length > MAX_TXT_FILES) {
        uploadBtn.disabled = true;
    }
    if (screenshotFiles.length > MAX_SCREENSHOT_FILES) {
        uploadBtn.disabled = true;
    }
    if (calculateTotalSize() > MAX_UPLOAD_SIZE_BYTES) {
        uploadBtn.disabled = true;
    }
}

if (uploadBtn) {
    uploadBtn.addEventListener('click', async () => {
    // Validate limits before upload
    if (txtFiles.length > MAX_TXT_FILES) {
        showWarning(`Excede el límite de archivos TXT (${txtFiles.length}/${MAX_TXT_FILES})`);
        return;
    }

    if (screenshotFiles.length > MAX_SCREENSHOT_FILES) {
        showWarning(`Excede el límite de screenshots (${screenshotFiles.length}/${MAX_SCREENSHOT_FILES})`);
        return;
    }

    const totalSize = calculateTotalSize();
    if (totalSize > MAX_UPLOAD_SIZE_BYTES) {
        showWarning(`El tamaño total excede el límite de ${MAX_UPLOAD_SIZE_MB} MB (actual: ${formatBytes(totalSize)})`);
        return;
    }

    uploadBtn.disabled = true;
    uploadBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Subiendo...';

    const formData = new FormData();
    txtFiles.forEach(file => formData.append('txt_files', file));
    screenshotFiles.forEach(file => formData.append('screenshots', file));

    try {
        const uploadResponse = await fetch(`${API_BASE}/api/upload`, {
            method: 'POST',
            body: formData
        });

        if (!uploadResponse.ok) {
            const errorData = await uploadResponse.json().catch(() => ({ detail: 'Upload failed' }));
            throw new Error(errorData.detail || 'Upload failed');
        }

        const uploadData = await uploadResponse.json();
        currentJobId = uploadData.job_id;

        const processResponse = await fetch(`${API_BASE}/api/process/${currentJobId}`, {
            method: 'POST'
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
    }
    });
}

function startTimer() {
    startTime = Date.now();
    updateTimer();
    timerInterval = setInterval(updateTimer, 1000);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

function updateTimer(elapsedSeconds = null) {
    if (elapsedSeconds === null && !startTime) return;
    
    const elapsed = elapsedSeconds !== null ? Math.floor(elapsedSeconds) : Math.floor((Date.now() - startTime) / 1000);
    const minutes = Math.floor(elapsed / 60);
    const seconds = elapsed % 60;
    
    const timerElement = document.getElementById('timer');
    if (timerElement) {
        timerElement.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
}

function formatDuration(seconds) {
    if (!seconds) return '0s';
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    if (minutes > 0) {
        return `${minutes}m ${secs}s`;
    }
    return `${secs}s`;
}

function startStatusPolling() {
    statusCheckInterval = setInterval(checkStatus, 2000);
}

function stopStatusPolling() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
}

async function checkStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/status/${currentJobId}`);
        if (!response.ok) {
            throw new Error('Failed to fetch status');
        }

        const job = await response.json();
        console.log(`[DEBUG] Job ${job.id} status: ${job.status}`);
        
        updateProcessingUI(job);

        if (job.status === 'completed') {
            console.log('[DEBUG] Job completed, showing results...');
            stopStatusPolling();
            stopTimer();
            await showResults(job);
            console.log('[DEBUG] Results displayed successfully');
        } else if (job.status === 'failed') {
            console.log('[DEBUG] Job failed');
            stopStatusPolling();
            stopTimer();
            showError(job.error_message || 'Processing failed');
        }
    } catch (error) {
        console.error('❌ Error checking status:', error);
    }
}

function updateProcessingUI(job) {
    const stats = job.statistics || {};
    const isCompleted = job.status === 'completed';
    
    if (job.elapsed_time_seconds !== null && job.elapsed_time_seconds !== undefined) {
        stopTimer();
        updateTimer(job.elapsed_time_seconds);
    }
    
    const phases = [
        { name: 'Parsing', icon: 'bi-file-text', done: isCompleted || stats.hands_parsed > 0 },
        { name: 'OCR', icon: 'bi-eye', done: isCompleted || stats.matched_hands > 0 },
        { name: 'Matching', icon: 'bi-link-45deg', done: isCompleted || stats.matched_hands > 0 },
        { name: 'Writing', icon: 'bi-pencil', done: isCompleted || stats.name_mappings > 0 }
    ];

    const phasesHTML = phases.map(phase => {
        const statusClass = phase.done ? 'phase-done' : 'phase-processing';
        const icon = phase.done ? 'bi-check-circle-fill' : 'bi-arrow-repeat spinning';
        return `
            <div class="phase-item ${statusClass}">
                <i class="bi ${icon}"></i>
                <span>${phase.name}</span>
            </div>
        `;
    }).join('');
    
    const statsHTML = `
        <div class="processing-stats">
            <div class="processing-stat-item">
                <i class="bi bi-file-text"></i>
                <span>${stats.txt_files || 0} archivos TXT</span>
            </div>
            <div class="processing-stat-item">
                <i class="bi bi-image"></i>
                <span>${stats.screenshots || 0} screenshots</span>
            </div>
            ${stats.ocr_total > 0 && stats.ocr_processed < stats.ocr_total ? `
                <div class="processing-stat-item processing">
                    <i class="bi bi-arrow-repeat spinning"></i>
                    <span>OCR: ${stats.ocr_processed}/${stats.ocr_total} procesados</span>
                </div>
            ` : ''}
            ${stats.hands_parsed > 0 ? `
                <div class="processing-stat-item success">
                    <i class="bi bi-check-circle"></i>
                    <span>${stats.hands_parsed} manos parseadas</span>
                </div>
            ` : ''}
            ${stats.matched_hands > 0 ? `
                <div class="processing-stat-item success">
                    <i class="bi bi-check-circle"></i>
                    <span>${stats.matched_hands} manos matched</span>
                </div>
            ` : ''}
            ${stats.name_mappings > 0 ? `
                <div class="processing-stat-item success">
                    <i class="bi bi-check-circle"></i>
                    <span>${stats.name_mappings} nombres resueltos</span>
                </div>
            ` : ''}
        </div>
    `;

    const processingStatus = document.getElementById('processing-status');
    
    let timerElement = document.getElementById('timer');
    if (!timerElement) {
        processingStatus.innerHTML = `
            <div class="timer-display">
                <i class="bi bi-clock"></i> 
                <span id="timer">0:00</span>
            </div>
            <h5 class="mb-3">Procesando Job #${job.id}</h5>
            <p class="text-muted mb-3">Pipeline de procesamiento</p>
            <div class="phases-container mb-4">
                ${phasesHTML}
            </div>
            ${statsHTML}
        `;
    } else {
        const phasesContainer = processingStatus.querySelector('.phases-container');
        if (phasesContainer) {
            phasesContainer.innerHTML = phasesHTML;
        }
        const statsContainer = processingStatus.querySelector('.processing-stats');
        if (statsContainer) {
            statsContainer.outerHTML = statsHTML;
        }
    }
}

function hideAllSections() {
    welcomeSection.classList.add('d-none');
    processingSection.classList.add('d-none');
    resultsSection.classList.add('d-none');
    errorSection.classList.add('d-none');
}

function showProcessing() {
    welcomeSection.classList.add('d-none');
    processingSection.classList.remove('d-none');
    resultsSection.classList.add('d-none');
    errorSection.classList.add('d-none');
}

async function showResults(job) {
    console.log('[DEBUG] showResults() called for job', job.id);
    try {
        processingSection.classList.add('d-none');
        resultsSection.classList.remove('d-none');
        console.log('[DEBUG] Sections toggled');

        const stats = job.statistics || {};
        const detailedStats = job.detailed_stats || {};
        const detailedMetrics = job.detailed_metrics || {};
        console.log('[DEBUG] Stats loaded:', stats);
        console.log('[DEBUG] Detailed metrics loaded:', detailedMetrics);
    const processingTime = stats.processing_time ? formatDuration(stats.processing_time) : 'N/A';

    const tablesCount = detailedStats.tables_count || 0;
    const tablesText = tablesCount === 1 ? 'Mesa' : 'Mesas';
    
    resultsStats.innerHTML = `
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">${stats.matched_hands || 0}</div>
                <div class="stat-label">Manos Matched</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.name_mappings || 0}</div>
                <div class="stat-label">Nombres Resueltos</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${tablesCount}</div>
                <div class="stat-label">${tablesText} Procesadas</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${processingTime}</div>
                <div class="stat-label">Tiempo de Proceso</div>
            </div>
        </div>
    `;

    // Load and display screenshot details
    await loadScreenshotDetails(currentJobId, detailedStats);

    // Display unmapped players warning
    displayUnmappedPlayers(detailedStats);

    // Display successful and failed files
    displayFileResults(detailedStats);

    // Display detailed metrics (NEW)
    displayDetailedMetrics(detailedMetrics);

    // Check if there are partial errors (failed files, OCR errors, warnings)
    const hasPartialErrors =
        (detailedStats.failed_files && detailedStats.failed_files.length > 0) ||
        (stats.screenshots_error && stats.screenshots_error > 0) ||
        (detailedStats.validation_warnings && detailedStats.validation_warnings.length > 0);

    if (hasPartialErrors) {
        await generatePartialErrorPrompt(currentJobId);
    }

    // Load debugging info
    await loadDebugInfo(currentJobId);

    // Update tab visibility based on content
    updateTabVisibility();

    // Setup download buttons
    downloadBtn.onclick = () => downloadResult(currentJobId);
    const downloadFallidosBtn = document.getElementById('download-fallidos-btn');
    if (downloadFallidosBtn) {
        downloadFallidosBtn.onclick = () => downloadFailedFiles(currentJobId);
    }

    loadJobs();
    console.log('[DEBUG] showResults() completed successfully');
    } catch (error) {
        console.error('❌ Error in showResults():', error);
        showError('Error al mostrar resultados: ' + error.message);
    }
}

async function loadScreenshotDetails(jobId, stats) {
    try {
        const response = await fetch(`${API_BASE}/api/job/${jobId}/screenshots`);
        if (!response.ok) return;
        
        const data = await response.json();
        const screenshots = data.screenshots || [];
        
        if (screenshots.length === 0) return;
        
        const successCount = stats.screenshots_success || 0;
        const warningCount = stats.screenshots_warning || 0;
        const errorCount = stats.screenshots_error || 0;
        const total = stats.screenshots_total || screenshots.length;
        
        // Show screenshot status section
        document.getElementById('screenshots-status').classList.remove('d-none');
        
        // Summary
        document.getElementById('screenshots-summary').innerHTML = `
            <div class="d-flex gap-3">
                <span><i class="bi bi-check-circle text-success"></i> ${successCount} Exitosos</span>
                <span><i class="bi bi-exclamation-triangle text-warning"></i> ${warningCount} Advertencias</span>
                <span><i class="bi bi-x-circle text-danger"></i> ${errorCount} Errores</span>
                <span class="text-muted">Total: ${total}</span>
            </div>
        `;
        
        // Detailed list
        const screenshotsList = screenshots.map(ss => {
            const statusIcon = ss.status === 'success' ? 'check-circle text-success' :
                              ss.status === 'warning' ? 'exclamation-triangle text-warning' :
                              'x-circle text-danger';
            const statusText = ss.status === 'success' ? 'Éxito' :
                              ss.status === 'warning' ? 'Sin matches' :
                              'Error OCR';
            
            return `
                <div class="card mb-2">
                    <div class="card-body py-2">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <i class="bi bi-${statusIcon}"></i>
                                <strong>${ss.screenshot_filename}</strong>
                                <span class="badge bg-secondary ms-2">${ss.matches_found} matches</span>
                            </div>
                            <small class="text-muted">${statusText}</small>
                        </div>
                        ${ss.ocr_error ? `<div class="text-danger small mt-1">Error: ${ss.ocr_error}</div>` : ''}
                    </div>
                </div>
            `;
        }).join('');
        
        document.getElementById('screenshots-list').innerHTML = screenshotsList;
        
    } catch (error) {
        console.error('Error loading screenshot details:', error);
    }
}

function displayUnmappedPlayers(stats) {
    const unmappedPlayers = stats.unmapped_players || [];
    
    if (unmappedPlayers.length === 0) {
        document.getElementById('unmapped-players-warning').classList.add('d-none');
        return;
    }
    
    document.getElementById('unmapped-players-warning').classList.remove('d-none');
    
    const playersList = unmappedPlayers.slice(0, 20).map(playerId => 
        `<span class="badge bg-warning text-dark me-2 mb-2">${playerId}</span>`
    ).join('');
    
    const moreText = unmappedPlayers.length > 20 ? 
        `<p class="text-muted small mb-0">... y ${unmappedPlayers.length - 20} más</p>` : '';
    
    document.getElementById('unmapped-players-list').innerHTML = playersList + moreText;
}

function displayFileResults(stats) {
    const successfulFiles = stats.successful_files || [];
    const failedFiles = stats.failed_files || [];

    // Show/hide download buttons based on what files exist
    const downloadBtn = document.getElementById('download-btn');
    const downloadFallidosBtn = document.getElementById('download-fallidos-btn');

    if (successfulFiles.length > 0) {
        downloadBtn.classList.remove('d-none');
        document.getElementById('successful-files-section').classList.remove('d-none');

        const filesList = successfulFiles.map(file =>
            `<div class="mt-1">
                <i class="bi bi-file-earmark-check text-success"></i>
                <strong>${file.table}</strong> - ${file.total_hands} manos
            </div>`
        ).join('');

        document.getElementById('successful-files-list').innerHTML = filesList;
    } else {
        downloadBtn.classList.add('d-none');
        document.getElementById('successful-files-section').classList.add('d-none');
    }

    if (failedFiles.length > 0) {
        downloadFallidosBtn.classList.remove('d-none');
        document.getElementById('failed-files-section').classList.remove('d-none');

        const filesList = failedFiles.map(file => {
            const unmappedIds = file.unmapped_ids || [];
            const unmappedList = unmappedIds.slice(0, 5).map(id =>
                `<span class="badge bg-danger me-1">${id}</span>`
            ).join('');
            const moreText = unmappedIds.length > 5 ?
                `<span class="text-muted small">+${unmappedIds.length - 5} más</span>` : '';

            return `
                <div class="card bg-light mb-2">
                    <div class="card-body py-2">
                        <div>
                            <i class="bi bi-file-earmark-x text-danger"></i>
                            <strong>${file.table}</strong> - ${file.total_hands} manos
                        </div>
                        <div class="mt-1">
                            <small class="text-muted">IDs sin mapear (${unmappedIds.length}):</small>
                            <div class="mt-1">${unmappedList} ${moreText}</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');

        document.getElementById('failed-files-list').innerHTML = filesList;
    } else {
        downloadFallidosBtn.classList.add('d-none');
        document.getElementById('failed-files-section').classList.add('d-none');
    }
}

function displayDetailedMetrics(metrics) {
    // Check if detailed metrics exist
    if (!metrics || Object.keys(metrics).length === 0) {
        console.log('[DEBUG] No detailed metrics available');
        document.getElementById('detailed-metrics').style.display = 'none';
        return;
    }

    console.log('[DEBUG] Displaying detailed metrics:', metrics);

    // Show detailed metrics section
    document.getElementById('detailed-metrics').style.display = 'flex';

    // 1. Hand Coverage Metrics
    if (metrics.hands) {
        const hands = metrics.hands;
        const handMetricsHTML = `
            <div class="metric-item">
                <div class="metric-label">Total</div>
                <div class="metric-value">${hands.total || 0}</div>
            </div>
            <div class="progress mb-2" style="height: 8px;">
                <div class="progress-bar bg-success" style="width: ${hands.coverage_percentage || 0}%"></div>
            </div>
            <div class="metric-breakdown">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-success">
                        <i class="bi bi-check-circle-fill"></i> Fully Mapped
                    </small>
                    <small><strong>${hands.fully_mapped || 0}</strong> (${hands.coverage_percentage || 0}%)</small>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-warning">
                        <i class="bi bi-exclamation-circle-fill"></i> Partially Mapped
                    </small>
                    <small>${hands.partially_mapped || 0}</small>
                </div>
                <div class="d-flex justify-content-between align-items-center">
                    <small class="text-danger">
                        <i class="bi bi-x-circle-fill"></i> No Mappings
                    </small>
                    <small>${hands.no_mappings || 0}</small>
                </div>
            </div>
        `;
        document.getElementById('hand-metrics').innerHTML = handMetricsHTML;
    }

    // 2. Player Mapping Metrics
    if (metrics.players) {
        const players = metrics.players;
        const playerMetricsHTML = `
            <div class="metric-item">
                <div class="metric-label">Total Unique</div>
                <div class="metric-value">${players.total_unique || 0}</div>
            </div>
            <div class="progress mb-2" style="height: 8px;">
                <div class="progress-bar bg-info" style="width: ${players.mapping_rate || 0}%"></div>
            </div>
            <div class="metric-breakdown">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-success">
                        <i class="bi bi-check-circle-fill"></i> Mapped
                    </small>
                    <small><strong>${players.mapped || 0}</strong> (${players.mapping_rate || 0}%)</small>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-danger">
                        <i class="bi bi-x-circle-fill"></i> Unmapped
                    </small>
                    <small>${players.unmapped || 0}</small>
                </div>
                <div class="d-flex justify-content-between align-items-center">
                    <small class="text-muted">
                        <i class="bi bi-graph-up"></i> Avg per Table
                    </small>
                    <small>${players.average_per_table || 0}</small>
                </div>
            </div>
        `;
        document.getElementById('player-metrics').innerHTML = playerMetricsHTML;
    }

    // 3. Table Resolution Metrics
    if (metrics.tables) {
        const tables = metrics.tables;
        const tableMetricsHTML = `
            <div class="metric-item">
                <div class="metric-label">Total Tables</div>
                <div class="metric-value">${tables.total || 0}</div>
            </div>
            <div class="progress mb-2" style="height: 8px;">
                <div class="progress-bar bg-success" style="width: ${tables.resolution_rate || 0}%"></div>
            </div>
            <div class="metric-breakdown">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-success">
                        <i class="bi bi-check-circle-fill"></i> Fully Resolved
                    </small>
                    <small><strong>${tables.fully_resolved || 0}</strong> (${tables.resolution_rate || 0}%)</small>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-warning">
                        <i class="bi bi-exclamation-circle-fill"></i> Partially Resolved
                    </small>
                    <small>${tables.partially_resolved || 0}</small>
                </div>
                <div class="d-flex justify-content-between align-items-center">
                    <small class="text-danger">
                        <i class="bi bi-x-circle-fill"></i> Failed
                    </small>
                    <small>${tables.failed || 0}</small>
                </div>
            </div>
        `;
        document.getElementById('table-metrics').innerHTML = tableMetricsHTML;
    }

    // 4. Screenshot Analysis Metrics
    if (metrics.screenshots) {
        const screenshots = metrics.screenshots;
        const screenshotMetricsHTML = `
            <div class="metric-item mb-2">
                <div class="metric-label">Total Screenshots</div>
                <div class="metric-value">${screenshots.total || 0}</div>
            </div>
            <div class="metric-breakdown">
                <div class="mb-2">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <small class="text-primary">OCR1 Success</small>
                        <small><strong>${screenshots.ocr1_success || 0}/${screenshots.total || 0}</strong></small>
                    </div>
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar bg-primary" style="width: ${screenshots.ocr1_success_rate || 0}%"></div>
                    </div>
                    <small class="text-muted">${screenshots.ocr1_success_rate || 0}% success rate</small>
                </div>
                <div class="mb-2">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <small class="text-info">OCR2 Success</small>
                        <small><strong>${screenshots.ocr2_success || 0}/${screenshots.ocr1_success || 0}</strong></small>
                    </div>
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar bg-info" style="width: ${screenshots.ocr2_success_rate || 0}%"></div>
                    </div>
                    <small class="text-muted">${screenshots.ocr2_success_rate || 0}% success rate</small>
                </div>
                <div>
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <small class="text-success">Matched</small>
                        <small><strong>${screenshots.matched || 0}/${screenshots.total || 0}</strong></small>
                    </div>
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar bg-success" style="width: ${screenshots.match_rate || 0}%"></div>
                    </div>
                    <small class="text-muted">${screenshots.match_rate || 0}% match rate</small>
                </div>
                ${screenshots.discarded > 0 ? `
                    <div class="mt-2">
                        <small class="text-warning">
                            <i class="bi bi-exclamation-triangle-fill"></i> ${screenshots.discarded} discarded
                        </small>
                    </div>
                ` : ''}
            </div>
        `;
        document.getElementById('screenshot-metrics').innerHTML = screenshotMetricsHTML;
    }

    // 5. Mapping Strategy Metrics
    if (metrics.mappings) {
        const mappings = metrics.mappings;
        const totalMappings = mappings.total || 0;
        const roleBasedPct = totalMappings > 0 ? Math.round((mappings.role_based / totalMappings) * 100) : 0;
        const counterClockwisePct = totalMappings > 0 ? Math.round((mappings.counter_clockwise / totalMappings) * 100) : 0;

        const mappingMetricsHTML = `
            <div class="metric-item">
                <div class="metric-label">Total Mappings</div>
                <div class="metric-value">${totalMappings}</div>
            </div>
            <div class="metric-breakdown">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <small class="text-success">
                        <i class="bi bi-bookmark-check-fill"></i> Role-Based
                    </small>
                    <small><strong>${mappings.role_based || 0}</strong> (${roleBasedPct}%)</small>
                </div>
                <div class="progress mb-2" style="height: 6px;">
                    <div class="progress-bar bg-success" style="width: ${roleBasedPct}%"></div>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <small class="text-info">
                        <i class="bi bi-arrow-clockwise"></i> Counter-Clockwise
                    </small>
                    <small><strong>${mappings.counter_clockwise || 0}</strong> (${counterClockwisePct}%)</small>
                </div>
                <div class="progress mb-2" style="height: 6px;">
                    <div class="progress-bar bg-info" style="width: ${counterClockwisePct}%"></div>
                </div>
                ${mappings.conflicts_detected > 0 ? `
                    <div class="alert alert-warning p-2 mb-0 mt-2">
                        <small>
                            <i class="bi bi-exclamation-triangle-fill"></i>
                            ${mappings.conflicts_detected} conflicts detected
                        </small>
                    </div>
                ` : ''}
            </div>
        `;
        document.getElementById('mapping-metrics').innerHTML = mappingMetricsHTML;
    }
}

async function showError(message) {
    processingSection.classList.add('d-none');
    errorSection.classList.remove('d-none');
    errorMessage.textContent = message;

    // Generate Claude Code prompt
    await generateErrorPrompt(currentJobId, message);
}

async function cancelJob() {
    if (!currentJobId) {
        console.error('No job ID to cancel');
        return;
    }

    const confirmCancel = confirm('¿Estás seguro de que quieres cancelar este job? Se eliminarán todos los archivos y no se podrá recuperar.');
    if (!confirmCancel) return;

    const cancelBtn = document.getElementById('cancel-job-btn');
    if (cancelBtn) {
        cancelBtn.disabled = true;
        cancelBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Cancelando...';
    }

    try {
        const response = await fetch(`${API_BASE}/api/job/${currentJobId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Error al cancelar job');
        }

        // Stop polling
        stopStatusPolling();
        stopTimer();

        // Clear current job
        const jobId = currentJobId;
        currentJobId = null;

        // Show success message
        alert(`Job #${jobId} cancelado exitosamente`);

        // Return to welcome screen
        showWelcomeSection();
        updateSidebarActiveState('nav-new-job');

        // Reload jobs list
        loadJobs();
        loadRecentJobs();

    } catch (error) {
        console.error('Error canceling job:', error);
        alert('Error al cancelar el job. Por favor intenta de nuevo.');

        if (cancelBtn) {
            cancelBtn.disabled = false;
            cancelBtn.innerHTML = '<i class="bi bi-x-circle"></i> Cancelar Job';
        }
    }
}

// Cancel a specific job by ID (used in job history)
async function cancelJobById(jobId, buttonElement) {
    const confirmCancel = confirm('¿Estás seguro de que quieres cancelar este job? Se eliminarán todos los archivos y no se podrá recuperar.');
    if (!confirmCancel) return;

    // Update button to show loading state
    const originalHTML = buttonElement.innerHTML;
    buttonElement.disabled = true;
    buttonElement.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Cancelando...';

    try {
        const response = await fetch(`${API_BASE}/api/job/${jobId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Error al cancelar job');
        }

        // Show success message
        alert(`Job #${jobId} cancelado exitosamente`);

        // If this was the current job being viewed, clean up
        if (currentJobId === jobId) {
            stopStatusPolling();
            stopTimer();
            currentJobId = null;
            showWelcomeSection();
            updateSidebarActiveState('nav-new-job');
        }

        // Reload jobs list
        loadJobs();
        loadRecentJobs();

    } catch (error) {
        console.error('Error canceling job:', error);
        alert('Error al cancelar el job. Por favor intenta de nuevo.');

        // Restore button state
        buttonElement.disabled = false;
        buttonElement.innerHTML = originalHTML;
    }
}

async function generateErrorPrompt(jobId, errorMessage) {
    const promptText = document.getElementById('error-prompt-text');
    const copyBtn = document.getElementById('copy-error-prompt-btn');
    const regenerateBtn = document.getElementById('regenerate-error-prompt-btn');

    if (!promptText) return;

    try {
        // Show loading state
        promptText.innerHTML = '<div class="text-muted"><i class="bi bi-hourglass-split"></i> Generando prompt con Gemini AI...</div>';
        if (copyBtn) copyBtn.disabled = true;
        if (regenerateBtn) regenerateBtn.disabled = true;

        // Call Gemini-powered endpoint
        const response = await fetch(`${API_BASE}/api/debug/${jobId}/generate-prompt`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('Failed to generate prompt');
        }

        const result = await response.json();
        const prompt = result.prompt || '';

        // Validate prompt is not empty
        if (!prompt || prompt.trim() === '') {
            throw new Error('Prompt vacío recibido del servidor');
        }

        // Display generated prompt
        promptText.textContent = prompt;

        // Setup copy button with proper text binding
        if (copyBtn) {
            copyBtn.disabled = false;
            // Store prompt text in button's data attribute for reliable access
            copyBtn.setAttribute('data-prompt-text', prompt);
            copyBtn.onclick = function() {
                const textToCopy = this.getAttribute('data-prompt-text');
                copyToClipboard(textToCopy, this);
            };
        }

        // Setup regenerate button
        if (regenerateBtn) {
            regenerateBtn.disabled = false;
            regenerateBtn.onclick = () => regenerateErrorPrompt(jobId, errorMessage);
        }

        // Show success indicator if Gemini was used
        if (result.success) {
            console.log('✅ Prompt generado exitosamente con Gemini AI');
            console.log('Prompt length:', prompt.length);
        } else {
            console.log('⚠️ Usando prompt de fallback:', result.message);
        }

    } catch (error) {
        console.error('Error generating Claude Code prompt:', error);

        // Show fallback error message
        promptText.innerHTML = `
            <div class="text-danger mb-2">
                <i class="bi bi-exclamation-triangle"></i> Error al generar prompt automáticamente
            </div>
            <div class="small">
                Por favor, copia manualmente esta información:<br><br>
                <strong>Error:</strong> ${errorMessage}<br>
                <strong>Job ID:</strong> ${jobId}<br><br>
                Revisa los logs del job para más detalles.
            </div>
        `;

        if (copyBtn) copyBtn.disabled = true;
        if (regenerateBtn) {
            regenerateBtn.disabled = false;
            regenerateBtn.onclick = () => regenerateErrorPrompt(jobId, errorMessage);
        }
    }
}

async function regenerateErrorPrompt(jobId, errorMessage) {
    const regenerateBtn = document.getElementById('regenerate-error-prompt-btn');

    if (!regenerateBtn) return;

    // Show loading state on button
    const originalHTML = regenerateBtn.innerHTML;
    regenerateBtn.innerHTML = '<i class="bi bi-arrow-repeat spinning"></i> Regenerando...';
    regenerateBtn.disabled = true;

    // Call the generate function again
    await generateErrorPrompt(jobId, errorMessage);

    // Reset button (will be re-enabled by generateErrorPrompt)
    regenerateBtn.innerHTML = originalHTML;
}

async function generatePartialErrorPrompt(jobId) {
    const promptSection = document.getElementById('partial-error-claude-prompt');
    const promptText = document.getElementById('partial-error-prompt-text');
    const copyBtn = document.getElementById('copy-partial-error-prompt-btn');
    const regenerateBtn = document.getElementById('regenerate-partial-error-prompt-btn');

    if (!promptSection || !promptText) return;

    try {
        // Show the prompt section
        promptSection.classList.remove('d-none');

        // Show loading state
        promptText.innerHTML = '<div class="text-muted"><i class="bi bi-hourglass-split"></i> Generando prompt con Gemini AI...</div>';
        if (copyBtn) copyBtn.disabled = true;
        if (regenerateBtn) regenerateBtn.disabled = true;

        // Call Gemini-powered endpoint
        const response = await fetch(`${API_BASE}/api/debug/${jobId}/generate-prompt`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('Failed to generate prompt');
        }

        const result = await response.json();
        const prompt = result.prompt || '';

        // Validate prompt is not empty
        if (!prompt || prompt.trim() === '') {
            throw new Error('Prompt vacío recibido del servidor');
        }

        // Display generated prompt
        promptText.textContent = prompt;

        // Setup copy button with proper text binding
        if (copyBtn) {
            copyBtn.disabled = false;
            // Store prompt text in button's data attribute for reliable access
            copyBtn.setAttribute('data-prompt-text', prompt);
            copyBtn.onclick = function() {
                const textToCopy = this.getAttribute('data-prompt-text');
                copyToClipboard(textToCopy, this);
            };
        }

        // Setup regenerate button
        if (regenerateBtn) {
            regenerateBtn.disabled = false;
            regenerateBtn.onclick = () => regeneratePartialErrorPrompt(jobId);
        }

        // Show success indicator if Gemini was used
        if (result.success) {
            console.log('✅ Prompt de errores parciales generado con Gemini AI');
            console.log('Prompt length:', prompt.length);
        } else {
            console.log('⚠️ Usando prompt de fallback para errores parciales');
        }

    } catch (error) {
        console.error('Error generating partial error prompt:', error);

        // Show error message instead of hiding
        promptText.innerHTML = `
            <div class="text-danger mb-2">
                <i class="bi bi-exclamation-triangle"></i> Error al generar prompt automáticamente
            </div>
            <div class="small">
                Por favor, intenta regenerar o revisa los logs del job para más detalles.
            </div>
        `;

        if (copyBtn) copyBtn.disabled = true;
        if (regenerateBtn) {
            regenerateBtn.disabled = false;
            regenerateBtn.onclick = () => regeneratePartialErrorPrompt(jobId);
        }
    }
}

async function regeneratePartialErrorPrompt(jobId) {
    const regenerateBtn = document.getElementById('regenerate-partial-error-prompt-btn');

    if (!regenerateBtn) return;

    // Show loading state on button
    const originalHTML = regenerateBtn.innerHTML;
    regenerateBtn.innerHTML = '<i class="bi bi-arrow-repeat spinning"></i> Regenerando...';
    regenerateBtn.disabled = true;

    // Call the generate function again
    await generatePartialErrorPrompt(jobId);

    // Reset button (will be re-enabled by generatePartialErrorPrompt)
    regenerateBtn.innerHTML = originalHTML;
}

function resetToWelcome() {
    if (welcomeSection) welcomeSection.classList.remove('d-none');
    if (processingSection) processingSection.classList.add('d-none');
    if (resultsSection) resultsSection.classList.add('d-none');
    if (errorSection) errorSection.classList.add('d-none');

    txtFiles = [];
    screenshotFiles = [];
    currentJobId = null;
    startTime = null;
    renderTxtFiles();
    renderScreenshotFiles();
    updateUploadButton();
    if (uploadBtn) {
        uploadBtn.innerHTML = '<i class="bi bi-upload"></i> Subir y Procesar';
    }

    loadJobs();
}

if (newJobBtn) {
    newJobBtn.addEventListener('click', resetToWelcome);
}
if (retryBtn) {
    retryBtn.addEventListener('click', resetToWelcome);
}

async function downloadResult(jobId) {
    window.location.href = `${API_BASE}/api/download/${jobId}`;
}

async function downloadFailedFiles(jobId) {
    window.location.href = `${API_BASE}/api/download-fallidos/${jobId}`;
}

async function loadJobs() {
    try {
        const response = await fetch(`${API_BASE}/api/jobs`);
        if (!response.ok) {
            throw new Error('Failed to fetch jobs');
        }

        const data = await response.json();
        renderJobs(data.jobs);
    } catch (error) {
        console.error('Error loading jobs:', error);
    }
}

function renderJobs(jobs) {
    if (!jobsList) return;
    
    jobsList.innerHTML = '';

    if (jobs.length === 0) {
        jobsList.innerHTML = '<p class="text-muted">No hay jobs anteriores</p>';
        return;
    }

    jobs.forEach(job => {
        const div = document.createElement('div');
        div.className = 'job-card';
        div.id = `job-${job.id}`;

        const statusClass = `status-badge-${job.status}`;
        const createdDate = new Date(job.created_at).toLocaleString('es-ES');
        const processingTime = job.processing_time_seconds ? formatDuration(job.processing_time_seconds) : 'N/A';

        const statusIcon = {
            'completed': 'bi-check-circle-fill text-success',
            'processing': 'bi-arrow-repeat text-brand spinning',
            'failed': 'bi-x-circle-fill text-danger',
            'pending': 'bi-clock-fill text-warning'
        }[job.status] || 'bi-question-circle-fill';

        div.innerHTML = `
            <div class="job-card-header" onclick="toggleJobCard(${job.id})">
                <div class="job-card-left">
                    <span class="job-id">Job #${job.id}</span>
                    <span class="${statusClass}">
                        <i class="bi ${statusIcon}"></i> ${job.status}
                    </span>
                </div>
                <div class="job-card-right">
                    ${job.status === 'completed' ? `
                        <button class="btn btn-sm btn-success me-2" onclick="event.stopPropagation(); downloadResult(${job.id})">
                            <i class="bi bi-download"></i> Descargar
                        </button>
                    ` : ''}
                    ${job.status === 'processing' ? `
                        <button class="btn btn-sm btn-danger me-2" onclick="event.stopPropagation(); cancelJobById(${job.id}, this)">
                            <i class="bi bi-x-circle"></i> Cancelar
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

        jobsList.appendChild(div);
    });
}

function toggleJobCard(jobId) {
    const body = document.getElementById(`job-body-${jobId}`);
    const card = document.getElementById(`job-${jobId}`);
    const icon = card.querySelector('.toggle-icon');
    
    if (body.style.display === 'none') {
        body.style.display = 'block';
        icon.classList.remove('bi-chevron-down');
        icon.classList.add('bi-chevron-up');
    } else {
        body.style.display = 'none';
        icon.classList.remove('bi-chevron-up');
        icon.classList.add('bi-chevron-down');
    }
}

// Debug info state
let debugData = null;
let currentLogFilter = '';

async function loadDebugInfo(jobId) {
    try {
        const response = await fetch(`${API_BASE}/api/debug/${jobId}`);
        if (!response.ok) {
            console.error('Failed to fetch debug info');
            return;
        }

        debugData = await response.json();

        // Show debug section
        const debugSection = document.getElementById('debug-section');
        if (debugSection) {
            debugSection.classList.remove('d-none');
        }

        // Setup log level filter
        const filterRadios = document.querySelectorAll('input[name="logLevel"]');
        filterRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                currentLogFilter = e.target.value;
                renderLogs(debugData.logs.entries, currentLogFilter);
            });
        });

        // Setup export button
        const exportBtn = document.getElementById('export-debug-btn');
        if (exportBtn) {
            exportBtn.onclick = () => exportDebugData(jobId, debugData);
        }

        // Initial log render
        renderLogs(debugData.logs.entries, currentLogFilter);

    } catch (error) {
        console.error('Error loading debug info:', error);
    }
}

function renderLogs(logs, levelFilter = '') {
    const logsContainer = document.getElementById('logs-container');
    
    if (!logsContainer) {
        console.warn('Logs container not found');
        return;
    }

    if (!logs || logs.length === 0) {
        logsContainer.innerHTML = '<div class="text-muted">No hay logs disponibles</div>';
        return;
    }

    // Filter logs by level if specified
    const filteredLogs = levelFilter
        ? logs.filter(log => log.level === levelFilter)
        : logs;

    if (filteredLogs.length === 0) {
        logsContainer.innerHTML = '<div class="text-muted">No hay logs con este nivel</div>';
        return;
    }

    // Sort logs by timestamp (newest first -> oldest last for better readability)
    const sortedLogs = [...filteredLogs].reverse();

    const logsHTML = sortedLogs.map(log => {
        const levelClass = {
            'DEBUG': 'text-info',
            'INFO': 'text-success',
            'WARNING': 'text-warning',
            'ERROR': 'text-danger',
            'CRITICAL': 'text-danger fw-bold'
        }[log.level] || 'text-secondary';

        const levelBadge = {
            'DEBUG': 'badge bg-info',
            'INFO': 'badge bg-success',
            'WARNING': 'badge bg-warning text-dark',
            'ERROR': 'badge bg-danger',
            'CRITICAL': 'badge bg-danger'
        }[log.level] || 'badge bg-secondary';

        const timestamp = new Date(log.timestamp).toLocaleString('es-ES', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            fractional: 3
        });

        const extraData = log.extra_data
            ? `<div class="ms-4 mt-1 text-muted small">${JSON.stringify(log.extra_data)}</div>`
            : '';

        return `
            <div class="log-entry mb-2 pb-2 border-bottom">
                <div class="d-flex align-items-start">
                    <span class="${levelBadge} me-2">${log.level}</span>
                    <div class="flex-grow-1">
                        <span class="text-muted small me-2">${timestamp}</span>
                        <span class="${levelClass}">${log.message}</span>
                        ${extraData}
                    </div>
                </div>
            </div>
        `;
    }).join('');

    logsContainer.innerHTML = logsHTML;

    // Auto-scroll to bottom to show most recent logs
    logsContainer.scrollTop = logsContainer.scrollHeight;
}

function copyToClipboard(text, button) {
    navigator.clipboard.writeText(text).then(() => {
        // Show success feedback
        const originalHTML = button.innerHTML;
        button.innerHTML = '<i class="bi bi-check-circle"></i> Copiado';
        button.classList.remove('btn-outline-dark', 'btn-outline-primary');
        button.classList.add('btn-success');

        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('btn-success');
            button.classList.add('btn-outline-dark');
        }, 2000);
    }).catch(err => {
        console.error('Error copying to clipboard:', err);
        alert('Error al copiar al portapapeles');
    });
}

async function exportDebugData(jobId, debugData) {
    try {
        // Disable button and show loading state
        const exportBtn = document.getElementById('export-debug-btn');
        const originalText = exportBtn.innerHTML;
        exportBtn.disabled = true;
        exportBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Exportando...';

        // Call API to save to server
        const response = await fetch(`${API_BASE}/api/debug/${jobId}/export`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error('Failed to export debug data');
        }

        const result = await response.json();

        // Download to user's browser
        const dataStr = JSON.stringify(result.data, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);

        const link = document.createElement('a');
        link.href = url;
        link.download = result.filename;
        link.click();

        URL.revokeObjectURL(url);

        // Show success message in button
        exportBtn.innerHTML = '<i class="bi bi-check-circle"></i> Exportado';
        exportBtn.classList.remove('btn-outline-primary');
        exportBtn.classList.add('btn-success');

        setTimeout(() => {
            exportBtn.innerHTML = originalText;
            exportBtn.classList.remove('btn-success');
            exportBtn.classList.add('btn-outline-primary');
            exportBtn.disabled = false;
        }, 2000);

        // Show notification in page
        const notification = document.getElementById('export-notification');
        const filepath = document.getElementById('export-filepath');
        if (notification && filepath) {
            filepath.textContent = result.filepath;
            notification.classList.remove('d-none');

            // Auto-hide notification after 10 seconds
            setTimeout(() => {
                notification.classList.add('d-none');
            }, 10000);
        }

        console.log(`✅ Debug info guardado en servidor: ${result.filepath}`);

    } catch (error) {
        console.error('Error exporting debug data:', error);

        const exportBtn = document.getElementById('export-debug-btn');
        exportBtn.innerHTML = '<i class="bi bi-x-circle"></i> Error';
        exportBtn.classList.remove('btn-outline-primary');
        exportBtn.classList.add('btn-danger');

        setTimeout(() => {
            exportBtn.innerHTML = '<i class="bi bi-download"></i> Exportar Debug JSON';
            exportBtn.classList.remove('btn-danger');
            exportBtn.classList.add('btn-outline-primary');
            exportBtn.disabled = false;
        }, 2000);

        alert('Error al exportar debug data: ' + error.message);
    }
}

// ============================================================================
// DEVELOPMENT MODE - REPROCESS JOB
// ============================================================================

async function loadDevJobInfo(jobId) {
    const devJobInfo = document.getElementById('dev-job-info');

    if (!jobId || jobId < 1) {
        devJobInfo.innerHTML = '<span class="text-danger">Job ID inválido</span>';
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/status/${jobId}`);

        if (!response.ok) {
            devJobInfo.innerHTML = '<span class="text-danger">Job no encontrado</span>';
            return;
        }

        const job = await response.json();
        const stats = job.statistics || {};

        devJobInfo.innerHTML = `
            <strong>Status:</strong> <span class="badge bg-${getStatusBadgeColor(job.status)}">${job.status}</span><br>
            <strong>Archivos:</strong> ${stats.txt_files || 0} TXT, ${stats.screenshots || 0} screenshots<br>
            <strong>Hands:</strong> ${stats.hands_parsed || 0} parseadas, ${stats.matched_hands || 0} matched
        `;
    } catch (error) {
        console.error('Error loading dev job info:', error);
        devJobInfo.innerHTML = '<span class="text-danger">Error al cargar info del job</span>';
    }
}

function getStatusBadgeColor(status) {
    const colors = {
        'pending': 'secondary',
        'processing': 'primary',
        'completed': 'success',
        'failed': 'danger'
    };
    return colors[status] || 'secondary';
}

async function reprocessDevJob() {
    const jobIdInput = document.getElementById('dev-job-id');
    const reprocessBtn = document.getElementById('reprocess-job-btn');
    const jobId = parseInt(jobIdInput.value);

    if (!jobId || jobId < 1) {
        alert('Por favor ingresa un Job ID válido');
        return;
    }

    reprocessBtn.disabled = true;
    reprocessBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Iniciando...';

    try {
        // Call the existing /api/process endpoint (it now handles reprocessing)
        const response = await fetch(`${API_BASE}/api/process/${jobId}`, {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to start processing');
        }

        const data = await response.json();
        currentJobId = jobId;

        // Show processing section and start monitoring
        showProcessing();
        startTimer();
        startStatusPolling();

        console.log(`✅ ${data.is_reprocess ? 'Reprocesando' : 'Procesando'} job ${jobId}`);

    } catch (error) {
        console.error('Error reprocessing job:', error);
        alert('Error al reprocesar job: ' + error.message);

        reprocessBtn.disabled = false;
        reprocessBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Reprocesar Job';
    }
}

// ========================================
// SIDEBAR NAVIGATION
// ========================================

function updateSidebarActiveState(activeId) {
    document.querySelectorAll('.sidebar-link').forEach(link => {
        link.classList.remove('active');
    });
    document.getElementById(activeId)?.classList.add('active');
}

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showWelcomeSection() {
    hideAllSections();
    welcomeSection.classList.remove('d-none');
}

// ========================================
// REPROCESS MODAL
// ========================================

let reprocessModal = null;
let modalJobIdInput = null;
let loadJobInfoBtn = null;
let modalJobInfo = null;
let modalJobError = null;
let modalReprocessBtn = null;
let modalJobIdDisplay = null;
let modalJobDetails = null;

function openReprocessModal() {
    if (!reprocessModal) return;
    // Reset modal state
    modalJobIdInput.value = '';
    modalJobInfo.classList.add('d-none');
    modalJobError.classList.add('d-none');
    modalReprocessBtn.disabled = true;
    reprocessModal.show();
}

function showModalError(message) {
    if (modalJobError) {
        modalJobError.textContent = message;
        modalJobError.classList.remove('d-none');
    }
}

function formatStatus(status) {
    const statusMap = {
        'completed': '✅ Completado',
        'processing': '⏳ Procesando',
        'failed': '❌ Fallado',
        'pending': '⏸️ Pendiente'
    };
    return statusMap[status] || status;
}

// ========================================
// RECENT JOBS IN SIDEBAR
// ========================================

async function loadRecentJobs() {
    try {
        const response = await fetch(`${API_BASE}/api/jobs`);
        const data = await response.json();

        const recentJobsList = document.getElementById('recent-jobs-list');
        if (!recentJobsList) return;

        // Handle both array and object responses
        const jobs = Array.isArray(data) ? data : (data.jobs || []);

        if (jobs.length === 0) {
            recentJobsList.innerHTML = '<div class="text-muted small text-center py-2">No hay jobs</div>';
            return;
        }

        // Show last 5 jobs
        const recentJobs = jobs.slice(0, 5);
        recentJobsList.innerHTML = recentJobs.map(job => `
            <div class="recent-job-item ${job.status}" data-job-id="${job.id}">
                <div class="recent-job-header">
                    <span class="recent-job-id">Job #${job.id}</span>
                    <span class="recent-job-status">${getStatusIcon(job.status)}</span>
                </div>
                <div class="recent-job-date">${formatDate(job.created_at)}</div>
            </div>
        `).join('');

        // Add click handlers
        document.querySelectorAll('.recent-job-item').forEach(item => {
            item.addEventListener('click', () => {
                const jobId = parseInt(item.dataset.jobId);
                loadJobDetails(jobId);
            });
        });

    } catch (error) {
        console.error('Error loading recent jobs:', error);
    }
}

function getStatusIcon(status) {
    const icons = {
        'completed': '✅',
        'processing': '⏳',
        'failed': '❌',
        'pending': '⏸️'
    };
    return icons[status] || '❓';
}

function formatDate(dateString) {
    if (!dateString) return '';
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Ahora';
    if (diffMins < 60) return `Hace ${diffMins}m`;
    if (diffHours < 24) return `Hace ${diffHours}h`;
    if (diffDays < 7) return `Hace ${diffDays}d`;
    return date.toLocaleDateString('es-ES', { month: 'short', day: 'numeric' });
}

async function loadJobDetails(jobId) {
    try {
        const response = await fetch(`${API_BASE}/api/status/${jobId}`);
        const data = await response.json();

        currentJobId = jobId;

        if (data.status === 'completed') {
            showResults(data);
        } else if (data.status === 'processing') {
            showProcessing();
            checkStatus(jobId);
        } else if (data.status === 'failed') {
            showError(data.error || 'Job falló');
        }

        scrollToTop();

    } catch (error) {
        console.error('Error loading job details:', error);
    }
}

// ========================================
// TAB VISIBILITY MANAGEMENT
// ========================================

function updateTabVisibility() {
    // Show/hide "no data" messages based on content
    const hasFiles = !document.getElementById('successful-files-section').classList.contains('d-none') ||
                     !document.getElementById('failed-files-section').classList.contains('d-none') ||
                     !document.getElementById('unmapped-players-warning').classList.contains('d-none');

    const hasScreenshots = !document.getElementById('screenshots-status').classList.contains('d-none');

    const hasDebug = !document.getElementById('debug-section').classList.contains('d-none') ||
                     !document.getElementById('partial-error-claude-prompt').classList.contains('d-none');

    document.getElementById('no-files-message').style.display = hasFiles ? 'none' : 'block';
    document.getElementById('no-screenshots-message').style.display = hasScreenshots ? 'none' : 'block';
    document.getElementById('no-debug-message').style.display = hasDebug ? 'none' : 'block';
}

// ========================================
// INITIALIZATION
// ========================================

document.addEventListener('DOMContentLoaded', () => {
    // Initialize modal elements
    const reprocessModalElement = document.getElementById('reprocessModal');
    if (reprocessModalElement) {
        reprocessModal = new bootstrap.Modal(reprocessModalElement);
        modalJobIdInput = document.getElementById('modal-job-id');
        loadJobInfoBtn = document.getElementById('load-job-info-btn');
        modalJobInfo = document.getElementById('modal-job-info');
        modalJobError = document.getElementById('modal-job-error');
        modalReprocessBtn = document.getElementById('modal-reprocess-btn');
        modalJobIdDisplay = document.getElementById('modal-job-id-display');
        modalJobDetails = document.getElementById('modal-job-details');

        // Modal load job info button
        if (loadJobInfoBtn) {
            loadJobInfoBtn.addEventListener('click', async () => {
                const jobId = parseInt(modalJobIdInput.value);
                if (!jobId || jobId < 1) {
                    showModalError('Por favor ingresa un Job ID válido');
                    return;
                }

                try {
                    const response = await fetch(`${API_BASE}/api/status/${jobId}`);
                    const data = await response.json();

                    if (!response.ok) {
                        throw new Error(data.error || 'Error al cargar job');
                    }

                    // Display job info
                    modalJobIdDisplay.textContent = jobId;
                    modalJobDetails.innerHTML = `
                        <div class="mb-2"><strong>Estado:</strong> ${formatStatus(data.status)}</div>
                        <div class="mb-2"><strong>Archivos TXT:</strong> ${data.txt_files_count || 0}</div>
                        <div class="mb-2"><strong>Screenshots:</strong> ${data.screenshot_files_count || 0}</div>
                        ${data.created_at ? `<div class="mb-2"><strong>Creado:</strong> ${new Date(data.created_at).toLocaleString('es-ES')}</div>` : ''}
                        ${data.match_rate !== null && data.match_rate !== undefined ? `<div class="mb-2"><strong>Match Rate:</strong> ${(data.match_rate * 100).toFixed(1)}%</div>` : ''}
                    `;

                    modalJobInfo.classList.remove('d-none');
                    modalJobError.classList.add('d-none');
                    modalReprocessBtn.disabled = false;
                    modalReprocessBtn.dataset.jobId = jobId;

                } catch (error) {
                    showModalError(error.message);
                    modalJobInfo.classList.add('d-none');
                    modalReprocessBtn.disabled = true;
                }
            });
        }

        // Modal reprocess button
        if (modalReprocessBtn) {
            modalReprocessBtn.addEventListener('click', async () => {
                const jobId = parseInt(modalReprocessBtn.dataset.jobId);
                if (!jobId) return;

                modalReprocessBtn.disabled = true;
                modalReprocessBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Reprocesando...';

                try {
                    const response = await fetch(`${API_BASE}/api/process/${jobId}`, {
                        method: 'POST'
                    });

                    if (!response.ok) {
                        throw new Error('Error al reprocesar job');
                    }

                    // Close modal and show processing
                    reprocessModal.hide();
                    currentJobId = jobId;
                    showProcessing();
                    checkStatus(jobId);

                } catch (error) {
                    showModalError(error.message);
                } finally {
                    modalReprocessBtn.disabled = false;
                    modalReprocessBtn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Reprocesar Job';
                }
            });
        }
    }

    // Initialize sidebar navigation
    const navNewJob = document.getElementById('nav-new-job');
    const navReprocess = document.getElementById('nav-reprocess');
    const navHistory = document.getElementById('nav-history');

    if (navNewJob) {
        navNewJob.addEventListener('click', (e) => {
            e.preventDefault();
            showWelcomeSection();
            updateSidebarActiveState('nav-new-job');
            scrollToTop();
        });
    }

    if (navReprocess) {
        navReprocess.addEventListener('click', (e) => {
            e.preventDefault();
            openReprocessModal();
        });
    }

    if (navHistory) {
        navHistory.addEventListener('click', (e) => {
            e.preventDefault();
            const historySection = document.getElementById('history-section');
            if (historySection) {
                historySection.scrollIntoView({ behavior: 'smooth', block: 'start' });
                updateSidebarActiveState('nav-history');
            }
        });
    }

    // Initialize cancel job button
    const cancelJobBtn = document.getElementById('cancel-job-btn');
    if (cancelJobBtn) {
        cancelJobBtn.addEventListener('click', cancelJob);
    }

    // Load initial data
    loadJobs();
    loadRecentJobs();

    // Refresh recent jobs every 30 seconds
    setInterval(loadRecentJobs, 30000);
});
