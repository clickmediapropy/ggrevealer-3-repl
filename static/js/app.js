const API_BASE = window.location.origin;

// File upload limits (must match backend limits in main.py)
const MAX_TXT_FILES = 300;
const MAX_SCREENSHOT_FILES = 300;
const MAX_UPLOAD_SIZE_MB = 300;
const MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024;

// Batch upload constants
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

let txtFiles = [];
let screenshotFiles = [];
let currentJobId = null;
let statusCheckInterval = null;
let timerInterval = null;
let startTime = null;
/**
 * Guard flag to prevent concurrent status checks from running simultaneously.
 * Prevents race condition where multiple setInterval callbacks could execute
 * showResults() twice, causing duplicate UI renders.
 *
 * @type {boolean}
 */
let isCheckingStatus = false;

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
            <i class="bi bi-x-circle remove-btn"></i>
        `;

        // Use closure with current file reference, not index
        const removeBtn = div.querySelector('.remove-btn');
        removeBtn.addEventListener('click', () => {
            // Find current index dynamically to avoid stale closure
            const currentIndex = txtFiles.indexOf(file);
            if (currentIndex !== -1) {
                txtFiles.splice(currentIndex, 1);
                renderTxtFiles();
                updateUploadButton();
                updateSizeIndicator();
            }
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
            txtCountBadge.className = 'badge bg-danger text-white';
        } else {
            txtCountBadge.className = 'badge bg-light text-brand';
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
            <i class="bi bi-x-circle remove-btn"></i>
        `;

        // Use closure with current file reference, not index
        const removeBtn = div.querySelector('.remove-btn');
        removeBtn.addEventListener('click', () => {
            // Find current index dynamically to avoid stale closure
            const currentIndex = screenshotFiles.indexOf(file);
            if (currentIndex !== -1) {
                screenshotFiles.splice(currentIndex, 1);
                renderScreenshotFiles();
                updateUploadButton();
                updateSizeIndicator();
            }
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
            screenshotCountBadge.className = 'badge bg-danger text-white';
        } else {
            screenshotCountBadge.className = 'badge bg-light text-success';
        }
    }

    updateSizeIndicator();
}

function calculateTotalSizeGlobal() {
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
    const totalSize = calculateTotalSizeGlobal();

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
    if (calculateTotalSizeGlobal() > MAX_UPLOAD_SIZE_BYTES) {
        uploadBtn.disabled = true;
    }
}

if (uploadBtn) {
    uploadBtn.addEventListener('click', async () => {
    // Check if API key is configured
    if (!hasApiKey()) {
        showWarning('Primero debes configurar tu API Key');
        const apiKeyModal = new bootstrap.Modal(document.getElementById('apiKeyModal'));
        apiKeyModal.show();
        return;
    }

    // Get API tier for time estimation (default to 'free' if not set)
    const apiTier = localStorage.getItem('api_tier') || 'free';

    // Validate limits before upload
    if (txtFiles.length > MAX_TXT_FILES) {
        showWarning(`Excede el límite de archivos TXT (${txtFiles.length}/${MAX_TXT_FILES})`);
        return;
    }

    if (screenshotFiles.length > MAX_SCREENSHOT_FILES) {
        showWarning(`Excede el límite de screenshots (${screenshotFiles.length}/${MAX_SCREENSHOT_FILES})`);
        return;
    }

    const totalSize = calculateTotalSizeGlobal();
    if (totalSize > MAX_UPLOAD_SIZE_BYTES) {
        showWarning(`El tamaño total excede el límite de ${MAX_UPLOAD_SIZE_MB} MB (actual: ${formatBytes(totalSize)})`);
        return;
    }

    // Calculate estimated time and show warning if needed
    const timeEstimate = calculateEstimatedTime(screenshotFiles.length, apiTier);
    if (timeEstimate.minutes > 10 && apiTier === 'free') {
        const confirmed = await showProcessingTimeWarning(timeEstimate.minutes, apiTier);
        if (!confirmed) {
            return;
        }
    }

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

        // Step 3: Show batch progress UI
        showBatchProgress();
        updateBatchProgress(0, totalBatches, `Preparando ${totalBatches} lotes...`);

        // Step 4: Upload batches sequentially
        let currentBatchIndex = 0; // Track for error reporting
        for (let i = 0; i < fileBatches.length; i++) {
            currentBatchIndex = i; // Update before processing each batch
            const batch = fileBatches[i];
            const batchNum = i + 1;
            const batchSize = calculateTotalSize(batch);

            updateBatchProgress(
                batchNum,
                totalBatches,
                `Subiendo lote ${batchNum}/${totalBatches} (${formatBytes(batchSize)})`
            );

            const batchFormData = new FormData();

            // Separate files by type with validation
            batch.forEach(file => {
                const fileName = file.name.toLowerCase();
                if (fileName.endsWith('.txt')) {
                    batchFormData.append('txt_files', file);
                } else if (fileName.endsWith('.png') || fileName.endsWith('.jpg') || fileName.endsWith('.jpeg')) {
                    batchFormData.append('screenshots', file);
                } else {
                    console.warn(`Skipping unsupported file type: ${file.name}`);
                }
            });

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

            const batchData = await batchResponse.json();
            console.log(`✓ Batch ${batchNum} uploaded successfully:`, batchData);
        }

        // Step 5: Hide batch progress
        hideBatchProgress();

        // Step 6: Start processing
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

        // Construct detailed error message with batch context
        let errorMessage = 'Error al subir archivos: ' + error.message;

        // Add batch context if we know which batch failed
        if (typeof currentBatchIndex !== 'undefined' && typeof fileBatches !== 'undefined' && fileBatches.length > 1) {
            const completedBatches = currentBatchIndex; // Loop index before error
            errorMessage = `Error al subir lote ${currentBatchIndex + 1}/${fileBatches.length}\n\n` +
                          `Lotes completados exitosamente: ${completedBatches}/${fileBatches.length}\n` +
                          `Archivos subidos: ~${Math.round((completedBatches / fileBatches.length) * 100)}%\n\n` +
                          `Detalles: ${error.message}`;
        }

        showError(errorMessage, true);

        // Cleanup: Delete the job if it was created
        if (currentJobId) {
            try {
                await fetch(`${API_BASE}/api/job/${currentJobId}`, { method: 'DELETE' });
                console.log(`Cleaned up failed job ${currentJobId}`);
            } catch (cleanupError) {
                console.error('Failed to cleanup job:', cleanupError);
            }
            currentJobId = null;
        }

        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<i class="bi bi-upload"></i> Subir y Procesar';
        hideBatchProgress();
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
    // Reset guard flag to prevent stuck state on job cancellation
    isCheckingStatus = false;
    console.log('[POLLING] Status polling stopped, guard flag reset');
}

async function checkStatus() {
    // Guard against concurrent status checks
    if (isCheckingStatus) {
        console.log('[GUARD] Skipping duplicate status check');
        return;
    }

    isCheckingStatus = true;

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
            showError(job.error_message || 'Processing failed', true);
        }
    } catch (error) {
        console.error('❌ Error checking status:', error);
    } finally {
        isCheckingStatus = false;
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
        showError('Error al mostrar resultados: ' + error.message, false); // Keep job for debugging
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
                              ss.status === 'warning' ? 'Sin coincidencias' :
                              'Error OCR';
            
            return `
                <div class="card mb-2">
                    <div class="card-body py-2">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <i class="bi bi-${statusIcon}"></i>
                                <strong>${ss.screenshot_filename}</strong>
                                <span class="badge bg-secondary ms-2">${ss.matches_found} coincidencias</span>
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
                        <i class="bi bi-check-circle-fill"></i> Completamente Mapeado
                    </small>
                    <small><strong>${hands.fully_mapped || 0}</strong> (${hands.coverage_percentage || 0}%)</small>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-warning">
                        <i class="bi bi-exclamation-circle-fill"></i> Parcialmente Mapeado
                    </small>
                    <small>${hands.partially_mapped || 0}</small>
                </div>
                <div class="d-flex justify-content-between align-items-center">
                    <small class="text-danger">
                        <i class="bi bi-x-circle-fill"></i> Sin Mapeos
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
                <div class="metric-label">Total Únicos</div>
                <div class="metric-value">${players.total_unique || 0}</div>
            </div>
            <div class="progress mb-2" style="height: 8px;">
                <div class="progress-bar bg-info" style="width: ${players.mapping_rate || 0}%"></div>
            </div>
            <div class="metric-breakdown">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-success">
                        <i class="bi bi-check-circle-fill"></i> Mapeados
                    </small>
                    <small><strong>${players.mapped || 0}</strong> (${players.mapping_rate || 0}%)</small>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-danger">
                        <i class="bi bi-x-circle-fill"></i> Sin Mapear
                    </small>
                    <small>${players.unmapped || 0}</small>
                </div>
                <div class="d-flex justify-content-between align-items-center">
                    <small class="text-muted">
                        <i class="bi bi-graph-up"></i> Promedio por Mesa
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
                <div class="metric-label">Total de Mesas</div>
                <div class="metric-value">${tables.total || 0}</div>
            </div>
            <div class="progress mb-2" style="height: 8px;">
                <div class="progress-bar bg-success" style="width: ${tables.resolution_rate || 0}%"></div>
            </div>
            <div class="metric-breakdown">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-success">
                        <i class="bi bi-check-circle-fill"></i> Completamente Resuelto
                    </small>
                    <small><strong>${tables.fully_resolved || 0}</strong> (${tables.resolution_rate || 0}%)</small>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-warning">
                        <i class="bi bi-exclamation-circle-fill"></i> Parcialmente Resuelto
                    </small>
                    <small>${tables.partially_resolved || 0}</small>
                </div>
                <div class="d-flex justify-content-between align-items-center">
                    <small class="text-danger">
                        <i class="bi bi-x-circle-fill"></i> Fallidos
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
                <div class="metric-label">Total de Screenshots</div>
                <div class="metric-value">${screenshots.total || 0}</div>
            </div>
            <div class="metric-breakdown">
                <div class="mb-2">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <small class="text-primary">Éxito OCR1</small>
                        <small><strong>${screenshots.ocr1_success || 0}/${screenshots.total || 0}</strong></small>
                    </div>
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar bg-primary" style="width: ${screenshots.ocr1_success_rate || 0}%"></div>
                    </div>
                    <small class="text-muted">${screenshots.ocr1_success_rate || 0}% tasa de éxito</small>
                </div>
                <div class="mb-2">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <small class="text-info">Éxito OCR2</small>
                        <small><strong>${screenshots.ocr2_success || 0}/${screenshots.ocr1_success || 0}</strong></small>
                    </div>
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar bg-info" style="width: ${screenshots.ocr2_success_rate || 0}%"></div>
                    </div>
                    <small class="text-muted">${screenshots.ocr2_success_rate || 0}% tasa de éxito</small>
                </div>
                <div>
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <small class="text-success">Coincidencias</small>
                        <small><strong>${screenshots.matched || 0}/${screenshots.total || 0}</strong></small>
                    </div>
                    <div class="progress" style="height: 6px;">
                        <div class="progress-bar bg-success" style="width: ${screenshots.match_rate || 0}%"></div>
                    </div>
                    <small class="text-muted">${screenshots.match_rate || 0}% tasa de coincidencias</small>
                </div>
                ${screenshots.discarded > 0 ? `
                    <div class="mt-2">
                        <small class="text-warning">
                            <i class="bi bi-exclamation-triangle-fill"></i> ${screenshots.discarded} descartados
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
        const visualPositionPct = totalMappings > 0 ? Math.round((mappings.visual_position / totalMappings) * 100) : 0;

        const mappingMetricsHTML = `
            <div class="metric-item">
                <div class="metric-label">Total de Mapeos</div>
                <div class="metric-value">${totalMappings}</div>
            </div>
            <div class="metric-breakdown">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <small class="text-success">
                        <i class="bi bi-bookmark-check-fill"></i> Basado en Roles
                    </small>
                    <small><strong>${mappings.role_based || 0}</strong> (${roleBasedPct}%)</small>
                </div>
                <div class="progress mb-2" style="height: 6px;">
                    <div class="progress-bar bg-success" style="width: ${roleBasedPct}%"></div>
                </div>
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <small class="text-info">
                        <i class="bi bi-eye"></i> Posición Visual
                    </small>
                    <small><strong>${mappings.visual_position || 0}</strong> (${visualPositionPct}%)</small>
                </div>
                <div class="progress mb-2" style="height: 6px;">
                    <div class="progress-bar bg-info" style="width: ${visualPositionPct}%"></div>
                </div>
                ${mappings.conflicts_detected > 0 ? `
                    <div class="alert alert-warning p-2 mb-0 mt-2">
                        <small>
                            <i class="bi bi-exclamation-triangle-fill"></i>
                            ${mappings.conflicts_detected} conflictos detectados
                        </small>
                    </div>
                ` : ''}
            </div>
        `;
        document.getElementById('mapping-metrics').innerHTML = mappingMetricsHTML;
    }
}

async function showError(message, shouldCleanup = false) {
    // Clear job ID if requested
    if (shouldCleanup && currentJobId) {
        console.log(`[CLEANUP] Clearing failed job ID: ${currentJobId}`);
        const failedJobId = currentJobId;
        currentJobId = null;

        // Reset guard flag to prevent stuck state
        if (typeof isCheckingStatus !== 'undefined') {
            isCheckingStatus = false;
        }

        // Optional: Try to delete failed job from server
        try {
            await fetch(`${API_BASE}/api/job/${failedJobId}`, { method: 'DELETE' });
            console.log(`[CLEANUP] Deleted failed job ${failedJobId} from server`);
        } catch (cleanupError) {
            console.warn(`[CLEANUP] Could not delete job ${failedJobId}:`, cleanupError);
        }
    }

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
            // Remove any existing event listeners to avoid duplicates
            copyBtn.onclick = null;
            copyBtn.onclick = function() {
                const textToCopy = this.getAttribute('data-prompt-text');
                console.log('Copy button clicked, text length:', textToCopy ? textToCopy.length : 0);
                copyToClipboard(textToCopy, this);
            };
            console.log('Copy button configured for error prompt');
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
            // Remove any existing event listeners to avoid duplicates
            copyBtn.onclick = null;
            copyBtn.onclick = function() {
                const textToCopy = this.getAttribute('data-prompt-text');
                console.log('Copy button clicked, text length:', textToCopy ? textToCopy.length : 0);
                copyToClipboard(textToCopy, this);
            };
            console.log('Copy button configured for partial error prompt');
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

const cancelErrorJobBtn = document.getElementById('cancel-error-job-btn');
if (cancelErrorJobBtn) {
    cancelErrorJobBtn.addEventListener('click', async () => {
        if (!currentJobId) {
            console.warn('[CANCEL] No job ID to cancel');
            showWelcomeSection();
            updateSidebarActiveState('nav-new-job');
            return;
        }

        const confirmCancel = confirm('¿Eliminar este job y volver al inicio?');
        if (!confirmCancel) return;

        const jobIdToDelete = currentJobId;
        currentJobId = null;

        cancelErrorJobBtn.disabled = true;
        cancelErrorJobBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Eliminando...';

        try {
            await fetch(`${API_BASE}/api/job/${jobIdToDelete}`, { method: 'DELETE' });
            console.log(`[CANCEL] Deleted failed job ${jobIdToDelete}`);

            showWelcomeSection();
            updateSidebarActiveState('nav-new-job');
            loadJobs();
            loadRecentJobs();
        } catch (error) {
            console.error('[CANCEL] Error deleting job:', error);
            alert('Error al eliminar el job. Volviendo al inicio de todos modos.');
            showWelcomeSection();
            updateSidebarActiveState('nav-new-job');
        }
    });
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
                    <div class="text-center mt-3">
                        <button class="btn btn-outline-primary btn-sm" onclick="event.stopPropagation(); toggleJobMetrics(${job.id})">
                            <i class="bi bi-bar-chart-line"></i>
                            <span id="metrics-btn-text-${job.id}">Ver Estadísticas Detalladas</span>
                            <span id="metrics-spinner-${job.id}" class="spinner-border spinner-border-sm ms-2" style="display: none;"></span>
                        </button>
                    </div>
                    <div id="detailed-metrics-${job.id}" class="mt-3" style="display: none;"></div>
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

// Toggle job detailed metrics
async function toggleJobMetrics(jobId) {
    const container = document.getElementById(`detailed-metrics-${jobId}`);
    const btnText = document.getElementById(`metrics-btn-text-${jobId}`);
    const spinner = document.getElementById(`metrics-spinner-${jobId}`);

    // If metrics are already loaded, just toggle visibility
    if (container.innerHTML.trim() !== '') {
        if (container.style.display === 'none') {
            container.style.display = 'block';
            btnText.textContent = 'Ocultar Estadísticas';
        } else {
            container.style.display = 'none';
            btnText.textContent = 'Ver Estadísticas Detalladas';
        }
        return;
    }

    // Load metrics for the first time
    try {
        // Show spinner
        spinner.style.display = 'inline-block';
        btnText.textContent = 'Cargando...';

        const response = await fetch(`${API_BASE}/api/status/${jobId}`);
        if (!response.ok) {
            throw new Error('Failed to fetch job metrics');
        }

        const data = await response.json();
        const metrics = data.detailed_metrics;

        if (!metrics || Object.keys(metrics).length === 0) {
            container.innerHTML = '<p class="text-muted text-center">No hay métricas detalladas disponibles</p>';
            container.style.display = 'block';
            btnText.textContent = 'Ocultar Estadísticas';
            spinner.style.display = 'none';
            return;
        }

        // Generate detailed metrics HTML
        const metricsHTML = generateDetailedMetricsHTML(metrics);
        container.innerHTML = metricsHTML;
        container.style.display = 'block';

        // Update button text
        btnText.textContent = 'Ocultar Estadísticas';
        spinner.style.display = 'none';

    } catch (error) {
        console.error('Error loading job metrics:', error);
        container.innerHTML = '<div class="alert alert-danger">Error al cargar las métricas</div>';
        container.style.display = 'block';
        btnText.textContent = 'Ocultar Estadísticas';
        spinner.style.display = 'none';
    }
}

// Generate detailed metrics HTML (similar to displayDetailedMetrics but returns HTML string)
function generateDetailedMetricsHTML(metrics) {
    let html = '<div class="row">';

    // 1. Hand Coverage Metrics
    if (metrics.hands) {
        const hands = metrics.hands;
        html += `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="metric-card">
                    <div class="metric-card-header">
                        <i class="bi bi-layers-fill"></i> COBERTURA DE MANOS
                    </div>
                    <div class="metric-card-body">
                        <div class="metric-item">
                            <div class="metric-label">TOTAL</div>
                            <div class="metric-value">${hands.total || 0}</div>
                        </div>
                        <div class="progress mb-2" style="height: 8px;">
                            <div class="progress-bar bg-success" style="width: ${hands.coverage_percentage || 0}%"></div>
                        </div>
                        <div class="metric-breakdown">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <small class="text-success">
                                    <i class="bi bi-check-circle-fill"></i> Completamente Mapeado
                                </small>
                                <small><strong>${hands.fully_mapped || 0}</strong> (${hands.coverage_percentage || 0}%)</small>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <small class="text-warning">
                                    <i class="bi bi-exclamation-circle-fill"></i> Parcialmente Mapeado
                                </small>
                                <small>${hands.partially_mapped || 0}</small>
                            </div>
                            <div class="d-flex justify-content-between align-items-center">
                                <small class="text-danger">
                                    <i class="bi bi-x-circle-fill"></i> Sin Mapeos
                                </small>
                                <small>${hands.no_mappings || 0}</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // 2. Player Mapping Metrics
    if (metrics.players) {
        const players = metrics.players;
        html += `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="metric-card">
                    <div class="metric-card-header">
                        <i class="bi bi-people-fill"></i> MAPEO DE JUGADORES
                    </div>
                    <div class="metric-card-body">
                        <div class="metric-item">
                            <div class="metric-label">TOTAL ÚNICOS</div>
                            <div class="metric-value">${players.total_unique || 0}</div>
                        </div>
                        <div class="progress mb-2" style="height: 8px;">
                            <div class="progress-bar bg-info" style="width: ${players.mapping_rate || 0}%"></div>
                        </div>
                        <div class="metric-breakdown">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <small class="text-success">
                                    <i class="bi bi-check-circle-fill"></i> Mapeados
                                </small>
                                <small><strong>${players.mapped || 0}</strong> (${players.mapping_rate || 0}%)</small>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <small class="text-danger">
                                    <i class="bi bi-x-circle-fill"></i> Sin Mapear
                                </small>
                                <small>${players.unmapped || 0}</small>
                            </div>
                            <div class="d-flex justify-content-between align-items-center">
                                <small class="text-muted">
                                    <i class="bi bi-graph-up"></i> Promedio por Mesa
                                </small>
                                <small>${players.average_per_table || 0}</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // 3. Table Resolution Metrics
    if (metrics.tables) {
        const tables = metrics.tables;
        html += `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="metric-card">
                    <div class="metric-card-header">
                        <i class="bi bi-table"></i> RESOLUCIÓN DE MESAS
                    </div>
                    <div class="metric-card-body">
                        <div class="metric-item">
                            <div class="metric-label">TOTAL DE MESAS</div>
                            <div class="metric-value">${tables.total || 0}</div>
                        </div>
                        <div class="progress mb-2" style="height: 8px;">
                            <div class="progress-bar bg-success" style="width: ${tables.resolution_rate || 0}%"></div>
                        </div>
                        <div class="metric-breakdown">
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <small class="text-success">
                                    <i class="bi bi-check-circle-fill"></i> Completamente Resuelto
                                </small>
                                <small><strong>${tables.fully_resolved || 0}</strong> (${tables.resolution_rate || 0}%)</small>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mb-1">
                                <small class="text-warning">
                                    <i class="bi bi-exclamation-circle-fill"></i> Parcialmente Resuelto
                                </small>
                                <small>${tables.partially_resolved || 0}</small>
                            </div>
                            <div class="d-flex justify-content-between align-items-center">
                                <small class="text-danger">
                                    <i class="bi bi-x-circle-fill"></i> Fallidos
                                </small>
                                <small>${tables.failed || 0}</small>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // 4. Screenshot Analysis Metrics
    if (metrics.screenshots) {
        const screenshots = metrics.screenshots;
        html += `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="metric-card">
                    <div class="metric-card-header">
                        <i class="bi bi-camera-fill"></i> ANÁLISIS DE SCREENSHOTS
                    </div>
                    <div class="metric-card-body">
                        <div class="metric-item mb-2">
                            <div class="metric-label">TOTAL DE SCREENSHOTS</div>
                            <div class="metric-value">${screenshots.total || 0}</div>
                        </div>
                        <div class="metric-breakdown">
                            <div class="mb-2">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <small class="text-primary">Éxito OCR1</small>
                                    <small><strong>${screenshots.ocr1_success || 0}/${screenshots.total || 0}</strong></small>
                                </div>
                                <div class="progress" style="height: 6px;">
                                    <div class="progress-bar bg-primary" style="width: ${screenshots.ocr1_success_rate || 0}%"></div>
                                </div>
                                <small class="text-muted">${screenshots.ocr1_success_rate || 0}% tasa de éxito</small>
                            </div>
                            <div class="mb-2">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <small class="text-info">Éxito OCR2</small>
                                    <small><strong>${screenshots.ocr2_success || 0}/${screenshots.ocr1_success || 0}</strong></small>
                                </div>
                                <div class="progress" style="height: 6px;">
                                    <div class="progress-bar bg-info" style="width: ${screenshots.ocr2_success_rate || 0}%"></div>
                                </div>
                                <small class="text-muted">${screenshots.ocr2_success_rate || 0}% tasa de éxito</small>
                            </div>
                            <div>
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <small class="text-success">Coincidencias</small>
                                    <small><strong>${screenshots.matched || 0}/${screenshots.total || 0}</strong></small>
                                </div>
                                <div class="progress" style="height: 6px;">
                                    <div class="progress-bar bg-success" style="width: ${screenshots.match_rate || 0}%"></div>
                                </div>
                                <small class="text-muted">${screenshots.match_rate || 0}% tasa de coincidencias</small>
                            </div>
                            ${screenshots.discarded > 0 ? `
                                <div class="mt-2">
                                    <small class="text-warning">
                                        <i class="bi bi-exclamation-triangle-fill"></i> ${screenshots.discarded} descartados
                                    </small>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    // 5. Mapping Strategy Metrics
    if (metrics.mappings) {
        const mappings = metrics.mappings;
        const totalMappings = mappings.total || 0;
        const roleBasedPct = totalMappings > 0 ? Math.round((mappings.role_based / totalMappings) * 100) : 0;
        const visualPositionPct = totalMappings > 0 ? Math.round((mappings.visual_position / totalMappings) * 100) : 0;

        html += `
            <div class="col-md-6 col-lg-4 mb-3">
                <div class="metric-card">
                    <div class="metric-card-header">
                        <i class="bi bi-shuffle"></i> ESTRATEGIA DE MAPEO
                    </div>
                    <div class="metric-card-body">
                        <div class="metric-item">
                            <div class="metric-label">TOTAL DE MAPEOS</div>
                            <div class="metric-value">${totalMappings}</div>
                        </div>
                        <div class="metric-breakdown">
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <small class="text-success">
                                    <i class="bi bi-bookmark-check-fill"></i> Basado en Roles
                                </small>
                                <small><strong>${mappings.role_based || 0}</strong> (${roleBasedPct}%)</small>
                            </div>
                            <div class="progress mb-2" style="height: 6px;">
                                <div class="progress-bar bg-success" style="width: ${roleBasedPct}%"></div>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mb-2">
                                <small class="text-info">
                                    <i class="bi bi-eye"></i> Posición Visual
                                </small>
                                <small><strong>${mappings.visual_position || 0}</strong> (${visualPositionPct}%)</small>
                            </div>
                            <div class="progress mb-2" style="height: 6px;">
                                <div class="progress-bar bg-info" style="width: ${visualPositionPct}%"></div>
                            </div>
                            ${mappings.conflicts_detected > 0 ? `
                                <div class="alert alert-warning p-2 mb-0 mt-2">
                                    <small>
                                        <i class="bi bi-exclamation-triangle-fill"></i>
                                        ${mappings.conflicts_detected} conflictos detectados
                                    </small>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    html += '</div>';
    return html;
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

async function copyToClipboard(text, button) {
    // Validate inputs
    if (!text || text.trim() === '') {
        console.error('No text to copy');
        showCopyError(button, 'No hay texto para copiar');
        return;
    }

    if (!button) {
        console.error('No button element provided');
        return;
    }

    try {
        // Try modern clipboard API first
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
        } else {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            textArea.style.position = 'fixed';
            textArea.style.left = '-9999px';
            textArea.style.top = '-9999px';
            document.body.appendChild(textArea);
            textArea.focus();
            textArea.select();

            const successful = document.execCommand('copy');
            document.body.removeChild(textArea);

            if (!successful) {
                throw new Error('Fallback copy method failed');
            }
        }

        // Show success feedback
        showCopySuccess(button);

    } catch (err) {
        console.error('Error copying to clipboard:', err);
        showCopyError(button, 'Error al copiar');
    }
}

function showCopySuccess(button) {
    const originalHTML = button.innerHTML;
    const originalClasses = button.className;

    // Change to success state
    button.innerHTML = '<i class="bi bi-check-circle"></i> ¡Copiado!';
    button.className = button.className.replace('btn-outline-dark', 'btn-success').replace('btn-outline-primary', 'btn-success');

    // Reset after 2 seconds
    setTimeout(() => {
        button.innerHTML = originalHTML;
        button.className = originalClasses;
    }, 2000);
}

function showCopyError(button, message) {
    const originalHTML = button.innerHTML;
    const originalClasses = button.className;

    // Change to error state
    button.innerHTML = '<i class="bi bi-x-circle"></i> Error';
    button.className = button.className.replace('btn-outline-dark', 'btn-danger').replace('btn-outline-primary', 'btn-danger');

    // Show alert with error message
    alert(message || 'Error al copiar al portapapeles');

    // Reset after 3 seconds
    setTimeout(() => {
        button.innerHTML = originalHTML;
        button.className = originalClasses;
    }, 3000);
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
            method: 'POST',
            headers: getHeadersWithApiKey()
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

function showFailedFilesView() {
    // Hide all views
    const welcomeSection = document.getElementById('welcome-section');
    const processingSection = document.getElementById('processing-section');
    const resultsSection = document.getElementById('results-section');
    const errorSection = document.getElementById('error-section');
    const historySection = document.getElementById('history-section');
    const failedFilesView = document.getElementById('failed-files-view');

    if (welcomeSection) welcomeSection.classList.add('d-none');
    if (processingSection) processingSection.classList.add('d-none');
    if (resultsSection) resultsSection.classList.add('d-none');
    if (errorSection) errorSection.classList.add('d-none');
    if (historySection) historySection.style.display = 'none';

    // Show failed files view
    if (failedFilesView) failedFilesView.style.display = 'block';
}

// ========================================
// PT4 LOG SUBMISSION HANDLER
// ========================================

function displayFailedFilesResults(data) {
    const resultsDiv = document.getElementById('failed-files-results');
    const tbody = document.getElementById('failed-files-tbody');

    if (!resultsDiv || !tbody) {
        console.error('Failed files results elements not found');
        return;
    }

    // Clear previous results
    tbody.innerHTML = '';

    // Debug logging
    console.log('Displaying failed files results:', data);

    if (!data.failed_files || data.failed_files.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="text-center">No se detectaron archivos fallidos</td></tr>';
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
                <button class="btn btn-sm btn-link" onclick='showScreenshots(${JSON.stringify(file.screenshot_paths)})'>
                    Ver
                </button>`;
        } else {
            screenshotsCell.innerHTML = '<span class="text-muted">No encontrados</span>';
        }
        row.appendChild(screenshotsCell);

        // Reprocesar button
        const reprocessCell = document.createElement('td');
        if (file.screenshot_paths && file.screenshot_paths.length > 0) {
            if (file.corrected_file_path) {
                // Already corrected - show download button
                reprocessCell.innerHTML = `
                    <span class="badge bg-success">✓ Corregido</span>
                    <button class="btn btn-sm btn-success mt-2" onclick="downloadFile('${file.corrected_file_path}')">
                        <i class="bi bi-download"></i> Descargar
                    </button>
                `;
            } else {
                // Not corrected - show Reprocesar button
                reprocessCell.innerHTML = `
                    <button class="btn btn-sm btn-warning reprocess-btn"
                            data-file-id="${file.id}"
                            data-table="${file.table_number}"
                            onclick="reprocessFailedFile(${file.id}, ${file.table_number})">
                        <i class="bi bi-arrow-clockwise"></i> Reprocesar
                    </button>
                    <div class="spinner-border spinner-border-sm d-none mt-2" role="status" id="spinner-${file.id}"></div>
                `;
            }
        } else {
            reprocessCell.innerHTML = '<span class="text-muted">Sin screenshots</span>';
        }
        row.appendChild(reprocessCell);

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

async function reprocessFailedFile(failedFileId, tableNumber) {
    console.log('[REPROCESS] ===== Starting Reprocess =====');
    console.log('[REPROCESS] Failed file ID:', failedFileId);
    console.log('[REPROCESS] Table number:', tableNumber);

    const button = document.querySelector(`button[data-file-id="${failedFileId}"]`);
    const spinner = document.getElementById(`spinner-${failedFileId}`);

    if (!button) {
        console.error('[REPROCESS] Button not found for failed file ID:', failedFileId);
        return;
    }

    // Show loading state
    button.disabled = true;
    button.classList.add('d-none');
    spinner.classList.remove('d-none');

    console.log('[REPROCESS] Sending request to server...');

    try {
        const formData = new FormData();
        formData.append('pt4_failed_file_id', failedFileId);

        // Check if API key is available and add it
        const apiKeyInput = document.getElementById('api-key-input');
        if (apiKeyInput && apiKeyInput.value) {
            formData.append('api_key', apiKeyInput.value);
            console.log('[REPROCESS] API Key included: Yes');
        } else {
            console.log('[REPROCESS] API Key included: No (using server environment key)');
        }

        const response = await fetch('/api/reprocess-failed-file', {
            method: 'POST',
            body: formData
        });

        console.log('[REPROCESS] Response status:', response.status);
        console.log('[REPROCESS] Response OK:', response.ok);

        const data = await response.json();
        console.log('[REPROCESS] Response data:', data);

        if (data.success) {
            console.log('[REPROCESS] ✅ Success!');
            console.log('[REPROCESS] Corrected file path:', data.corrected_file_path);
            console.log('[REPROCESS] Mappings count:', data.mappings_count);

            // Change row state to "Corregido"
            const cell = button.parentElement;
            cell.innerHTML = `
                <span class="badge bg-success">✓ Corregido</span>
                <button class="btn btn-sm btn-success mt-2" onclick="downloadFile('${data.corrected_file_path}')">
                    <i class="bi bi-download"></i> Descargar
                </button>
            `;

            // Show success notification
            alert(`✅ Mesa ${tableNumber} corregida exitosamente!\n\nMappings: ${data.mappings_count} jugadores`);
        } else {
            console.error('[REPROCESS] ❌ Failed!');
            console.error('[REPROCESS] Error:', data.error);

            if (data.unmapped_ids) {
                console.error('[REPROCESS] Unmapped IDs:', data.unmapped_ids);
                console.error('[REPROCESS] Unmapped count:', data.unmapped_ids.length);
            }

            if (data.details) {
                console.log('[REPROCESS] Details:', data.details);
            }

            // Show error with unmapped IDs
            spinner.classList.add('d-none');
            button.classList.remove('d-none');
            button.disabled = false;

            const errorMsg = data.unmapped_ids
                ? `❌ Error: IDs sin mapear (${data.unmapped_ids.join(', ')})\n\n${data.details}`
                : `❌ Error: ${data.error}`;

            alert(errorMsg);
        }
    } catch (error) {
        console.error('[REPROCESS] ❌ Network/Parse Error:', error);
        console.error('[REPROCESS] Error stack:', error.stack);

        spinner.classList.add('d-none');
        button.classList.remove('d-none');
        button.disabled = false;

        alert(`❌ Error de red: ${error.message}`);
    }

    console.log('[REPROCESS] ===== End Reprocess =====');
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
                    ${screenshotPaths.map(path => {
                        // Remove leading slash if present
                        const cleanPath = path.startsWith('/') ? path.substring(1) : path;
                        // Use query parameter to correctly handle special characters (# and spaces)
                        const encodedPath = encodeURIComponent(cleanPath);
                        return `
                        <div class="mb-3">
                            <p class="small text-muted">${path.split('/').pop()}</p>
                            <img src="/api/screenshot?path=${encodedPath}" class="img-fluid border" alt="Screenshot">
                        </div>
                    `}).join('')}
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
    // Create toast element
    const toastContainer = document.getElementById('toast-container') || createToastContainer();

    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${type === 'success' ? 'success' : 'danger'} border-0`;
    toast.setAttribute('role', 'alert');
    toast.setAttribute('aria-live', 'assertive');
    toast.setAttribute('aria-atomic', 'true');

    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
        </div>
    `;

    toastContainer.appendChild(toast);
    const bsToast = new bootstrap.Toast(toast);
    bsToast.show();

    // Remove toast element after it's hidden
    toast.addEventListener('hidden.bs.toast', () => {
        toast.remove();
    });
}

function createToastContainer() {
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '9999';
    document.body.appendChild(container);
    return container;
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

// ========================================
// FAILED FILES INTEGRATION
// ========================================

async function loadJobFailedFiles(jobId) {
    try {
        const response = await fetch(`${API_BASE}/api/pt4-log/failed-files/${jobId}`);
        if (!response.ok) return;

        const data = await response.json();

        const pt4Count = data.total_pt4_failures || 0;
        const appCount = data.total_app_failures || 0;

        if (pt4Count > 0 || appCount > 0) {
            const failedFilesSection = document.getElementById('modal-job-failed-files-section');
            const pt4CountSpan = document.getElementById('modal-job-pt4-failures-count');
            const appCountSpan = document.getElementById('modal-job-app-failures-count');

            if (failedFilesSection && pt4CountSpan && appCountSpan) {
                failedFilesSection.style.display = 'block';
                pt4CountSpan.textContent = pt4Count;
                appCountSpan.textContent = appCount;

                // Store for later viewing
                window.currentJobFailedFiles = data;
            }
        }
    } catch (error) {
        console.error('Error loading failed files:', error);
    }
}

function viewJobFailedFiles() {
    if (!window.currentJobFailedFiles) return;

    // Close the modal first
    if (reprocessModal) {
        reprocessModal.hide();
    }

    // Switch to failed files view and populate with this job's data
    showFailedFilesView();
    updateSidebarActiveState('nav-failed-files');

    // Display the failed files
    displayFailedFilesResults({
        failed_files_count: window.currentJobFailedFiles.total_pt4_failures,
        failed_files: window.currentJobFailedFiles.pt4_failures
    });
}

async function recalculateScreenshots() {
    // Get job ID from the input field
    const jobIdInput = document.getElementById('job-id-input');
    if (!jobIdInput || !jobIdInput.value) {
        alert('Por favor ingresa un Job ID primero');
        return;
    }

    const jobId = parseInt(jobIdInput.value);
    const btn = document.getElementById('recalculate-btn');

    // Disable button and show loading state
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Recalculando...';
    }

    try {
        const response = await fetch(`${API_BASE}/api/pt4-log/recalculate-screenshots/${jobId}`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`API error: ${response.status}`);
        }

        const data = await response.json();

        // Show success message
        alert(`✅ Recálculo completado!\n\nTotal de archivos: ${data.total_files}\nActualizados: ${data.updated_count}`);

        // Reload the failed files view to show updated screenshots
        if (window.currentJobFailedFiles) {
            const reloadResponse = await fetch(`${API_BASE}/api/pt4-log/failed-files/${jobId}`);
            if (reloadResponse.ok) {
                const reloadData = await reloadResponse.json();
                window.currentJobFailedFiles = reloadData;

                // Parse JSON fields
                if (reloadData.pt4_failures) {
                    reloadData.pt4_failures.forEach(failure => {
                        if (failure.associated_screenshot_paths) {
                            try {
                                failure.screenshot_paths = JSON.parse(failure.associated_screenshot_paths);
                            } catch (e) {
                                failure.screenshot_paths = [];
                            }
                        }
                    });
                }

                // Update the display
                displayFailedFilesResults({
                    failed_files_count: reloadData.total_pt4_failures,
                    failed_files: reloadData.pt4_failures
                });
            }
        }
    } catch (error) {
        console.error('Error recalculating screenshots:', error);
        alert(`❌ Error: ${error.message}`);
    } finally {
        // Re-enable button
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Recalcular Screenshots';
        }
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
            showError(data.error || 'Job falló', false); // Keep job - user is viewing historical failure
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
// API KEY MANAGEMENT
// ========================================

function getApiKey() {
    return localStorage.getItem('gemini_api_key');
}

function getHeadersWithApiKey() {
    const headers = {};
    const apiKey = getApiKey();
    if (apiKey) {
        headers['X-Gemini-API-Key'] = apiKey;
    }
    return headers;
}

function hasApiKey() {
    const key = getApiKey();
    return key && key.trim() !== '';
}

function updateApiKeyStatus() {
    const statusBadge = document.getElementById('api-key-status');
    if (!statusBadge) return;

    if (hasApiKey()) {
        const key = getApiKey();
        const maskedKey = '***' + key.slice(-4);
        statusBadge.innerHTML = `<i class="bi bi-check-circle"></i> ${maskedKey}`;
        statusBadge.className = 'badge bg-success';
    } else {
        statusBadge.innerHTML = '<i class="bi bi-x-circle"></i> Sin configurar';
        statusBadge.className = 'badge bg-danger';
    }
}

function checkApiKeyOnStartup() {
    if (!hasApiKey()) {
        // Open modal automatically if no API key is configured
        const apiKeyModal = new bootstrap.Modal(document.getElementById('apiKeyModal'));
        apiKeyModal.show();
    }
    updateApiKeyStatus();
}

async function validateAndSaveApiKey() {
    const apiKeyInput = document.getElementById('api-key-input');
    const apiKey = apiKeyInput.value.trim();

    // Get selected API tier (default to 'free' if somehow not selected)
    const apiTierElement = document.querySelector('input[name="apiTier"]:checked');
    const apiTier = apiTierElement ? apiTierElement.value : 'free';

    const errorDiv = document.getElementById('api-key-error');
    const successDiv = document.getElementById('api-key-success');
    const validatingDiv = document.getElementById('api-key-validating');
    const saveBtn = document.getElementById('save-api-key-btn');

    // Hide all messages
    errorDiv.classList.add('d-none');
    successDiv.classList.add('d-none');
    validatingDiv.classList.remove('d-none');
    saveBtn.disabled = true;

    // Validate input
    if (!apiKey || apiKey.length < 20) {
        errorDiv.textContent = 'Por favor ingresa una API key válida';
        errorDiv.classList.remove('d-none');
        validatingDiv.classList.add('d-none');
        saveBtn.disabled = false;
        return;
    }

    try {
        // Validate with server
        const response = await fetch(`${API_BASE}/api/validate-api-key`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ api_key: apiKey })
        });

        const data = await response.json();

        if (!response.ok || !data.valid) {
            throw new Error(data.error || 'API key inválida');
        }

        // Save to localStorage
        localStorage.setItem('gemini_api_key', apiKey);
        localStorage.setItem('api_tier', apiTier);

        // Show success
        validatingDiv.classList.add('d-none');
        successDiv.classList.remove('d-none');

        // Update status badge
        updateApiKeyStatus();

        // Close modal after 1.5 seconds
        setTimeout(() => {
            const modal = bootstrap.Modal.getInstance(document.getElementById('apiKeyModal'));
            modal.hide();
            successDiv.classList.add('d-none');
            apiKeyInput.value = '';
        }, 1500);

    } catch (error) {
        console.error('API key validation failed:', error);
        errorDiv.textContent = error.message || 'Error al validar la API key. Verifica que sea correcta.';
        errorDiv.classList.remove('d-none');
        validatingDiv.classList.add('d-none');
    } finally {
        saveBtn.disabled = false;
    }
}

function clearApiKey() {
    if (confirm('¿Estás seguro de que quieres eliminar tu API key? Necesitarás configurarla nuevamente para procesar jobs.')) {
        localStorage.removeItem('gemini_api_key');
        updateApiKeyStatus();
        document.getElementById('api-key-input').value = '';

        const modal = bootstrap.Modal.getInstance(document.getElementById('apiKeyModal'));
        modal.hide();
    }
}

function toggleApiKeyVisibility() {
    const input = document.getElementById('api-key-input');
    const toggleBtn = document.getElementById('toggle-api-key-visibility');
    const icon = toggleBtn.querySelector('i');

    if (input.type === 'password') {
        input.type = 'text';
        icon.className = 'bi bi-eye-slash';
    } else {
        input.type = 'password';
        icon.className = 'bi bi-eye';
    }
}

// ========================================
// RATE LIMITING & TIME ESTIMATION
// ========================================

function calculateEstimatedTime(screenshotCount, apiTier = null) {
    // Get tier from parameter or localStorage
    const tier = apiTier || localStorage.getItem('api_tier') || 'free';

    // Calculate requests per minute based on tier
    const requestsPerMin = tier === 'free' ? 14 : 300;

    // Estimate total minutes (ORC1 + OCR2 = 2x screenshots)
    const totalRequests = screenshotCount * 2;
    const estimatedMinutes = Math.ceil(totalRequests / requestsPerMin);

    return {
        minutes: estimatedMinutes,
        tier: tier,
        requestsPerMin: requestsPerMin
    };
}

function showProcessingTimeWarning(estimatedMinutes, apiTier) {
    return new Promise((resolve) => {
        // Create modal HTML
        const warningHtml = `
            <div class="modal fade" id="timeWarningModal" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header bg-warning">
                            <h5 class="modal-title">
                                <i class="bi bi-exclamation-triangle-fill"></i>
                                Procesamiento Lento
                            </h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <p><strong>Tu API Key es TIER GRATIS</strong></p>
                            <div class="alert alert-info">
                                <i class="bi bi-info-circle"></i>
                                <strong>Tiempo estimado: ~${estimatedMinutes} minutos</strong>
                                <br>
                                <small>Los screenshots se procesarán a 14 requests/minuto</small>
                            </div>
                            <p class="mb-2">El procesamiento será más lento, pero completará correctamente.</p>
                            <p class="text-muted small mb-0">
                                <i class="bi bi-lightning-fill"></i>
                                <strong>Quieres procesar más rápido?</strong>
                                <a href="https://console.cloud.google.com/billing" target="_blank" rel="noopener">
                                    Configura facturación en Google Cloud
                                </a>
                            </p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" id="cancel-warning">
                                Cancelar
                            </button>
                            <button type="button" class="btn btn-warning" id="continue-warning">
                                <i class="bi bi-play-fill"></i> Continuar
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Remove if exists
        const existing = document.getElementById('timeWarningModal');
        if (existing) existing.remove();

        // Add to body
        document.body.insertAdjacentHTML('beforeend', warningHtml);

        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('timeWarningModal'));

        // Handle buttons
        document.getElementById('cancel-warning').addEventListener('click', () => {
            modal.hide();
            resolve(false);
        });

        document.getElementById('continue-warning').addEventListener('click', () => {
            modal.hide();
            resolve(true);
        });

        // Resolve false if modal is dismissed
        document.getElementById('timeWarningModal').addEventListener('hidden.bs.modal', () => {
            resolve(false);
        }, { once: true });

        modal.show();
    });
}

// ========================================
// BUDGET MANAGEMENT
// ========================================

async function loadBudgetInfo() {
    try {
        const response = await fetch(`${API_BASE}/api/config/budget`);
        const data = await response.json();

        // Update display values
        document.getElementById('monthly-spending').textContent = `$${data.monthly_spending.toFixed(2)}`;
        document.getElementById('monthly-budget').textContent = `$${data.monthly_budget.toFixed(2)}`;

        // Update progress bar
        const progressBar = document.getElementById('budget-progress');
        const percentage = data.percentage_used;
        progressBar.style.width = `${percentage}%`;
        progressBar.textContent = `${percentage.toFixed(1)}%`;
        progressBar.setAttribute('aria-valuenow', percentage);

        // Update progress bar color based on percentage
        progressBar.classList.remove('bg-success', 'bg-warning', 'bg-danger');
        if (percentage >= 100) {
            progressBar.classList.add('bg-danger');
        } else if (percentage >= 80) {
            progressBar.classList.add('bg-warning');
        } else {
            progressBar.classList.add('bg-success');
        }

        // Update budget modal inputs
        document.getElementById('budget-input').value = data.monthly_budget.toFixed(2);
        document.getElementById('reset-day-input').value = data.budget_reset_day;

    } catch (error) {
        console.error('Failed to load budget info:', error);
    }
}

async function saveBudgetConfig() {
    const budget = parseFloat(document.getElementById('budget-input').value);
    const resetDay = parseInt(document.getElementById('reset-day-input').value);

    const errorDiv = document.getElementById('budget-error');
    const successDiv = document.getElementById('budget-success');

    // Hide previous messages
    errorDiv.classList.add('d-none');
    successDiv.classList.add('d-none');

    // Validate inputs
    if (isNaN(budget) || budget < 0) {
        errorDiv.textContent = 'El presupuesto debe ser un número positivo';
        errorDiv.classList.remove('d-none');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/config/budget`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                monthly_budget: budget,
                budget_reset_day: resetDay
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save budget');
        }

        // Show success message
        successDiv.classList.remove('d-none');

        // Reload budget info to update sidebar
        await loadBudgetInfo();

        // Close modal after 1.5 seconds
        setTimeout(() => {
            const modal = bootstrap.Modal.getInstance(document.getElementById('budgetModal'));
            modal.hide();
            // Reset messages on close
            successDiv.classList.add('d-none');
        }, 1500);

    } catch (error) {
        console.error('Failed to save budget:', error);
        errorDiv.textContent = error.message;
        errorDiv.classList.remove('d-none');
    }
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

                    // Hide failed files section initially
                    const failedFilesSection = document.getElementById('modal-job-failed-files-section');
                    if (failedFilesSection) {
                        failedFilesSection.style.display = 'none';
                    }

                    // Display job info
                    modalJobIdDisplay.textContent = jobId;
                    modalJobDetails.innerHTML = `
                        <div class="mb-2"><strong>Estado:</strong> ${formatStatus(data.status)}</div>
                        <div class="mb-2"><strong>Archivos TXT:</strong> ${data.txt_files_count || 0}</div>
                        <div class="mb-2"><strong>Screenshots:</strong> ${data.screenshot_files_count || 0}</div>
                        ${data.created_at ? `<div class="mb-2"><strong>Creado:</strong> ${new Date(data.created_at).toLocaleString('es-ES')}</div>` : ''}
                        ${data.match_rate !== null && data.match_rate !== undefined ? `<div class="mb-2"><strong>Tasa de Coincidencias:</strong> ${(data.match_rate * 100).toFixed(1)}%</div>` : ''}
                    `;

                    modalJobInfo.classList.remove('d-none');
                    modalJobError.classList.add('d-none');
                    modalReprocessBtn.disabled = false;
                    modalReprocessBtn.dataset.jobId = jobId;

                    // Load failed files for this job
                    await loadJobFailedFiles(jobId);

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
                        method: 'POST',
                        headers: getHeadersWithApiKey()
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

    const navFailedFiles = document.getElementById('nav-failed-files');
    if (navFailedFiles) {
        navFailedFiles.addEventListener('click', (e) => {
            e.preventDefault();
            showFailedFilesView();
            updateSidebarActiveState('nav-failed-files');
        });
    }

    // Initialize cancel job button
    const cancelJobBtn = document.getElementById('cancel-job-btn');
    if (cancelJobBtn) {
        cancelJobBtn.addEventListener('click', cancelJob);
    }

    // Initialize budget save button
    const saveBudgetBtn = document.getElementById('save-budget-btn');
    if (saveBudgetBtn) {
        saveBudgetBtn.addEventListener('click', saveBudgetConfig);
    }

    // Initialize API key buttons
    const saveApiKeyBtn = document.getElementById('save-api-key-btn');
    if (saveApiKeyBtn) {
        saveApiKeyBtn.addEventListener('click', validateAndSaveApiKey);
    }

    const clearApiKeyBtn = document.getElementById('clear-api-key-btn');
    if (clearApiKeyBtn) {
        clearApiKeyBtn.addEventListener('click', clearApiKey);
    }

    const toggleApiKeyBtn = document.getElementById('toggle-api-key-visibility');
    if (toggleApiKeyBtn) {
        toggleApiKeyBtn.addEventListener('click', toggleApiKeyVisibility);
    }

    // PT4 Log Form Submission
    const pt4LogForm = document.getElementById('pt4-log-form');
    if (pt4LogForm) {
        pt4LogForm.addEventListener('submit', async (e) => {
            e.preventDefault();

            const logText = document.getElementById('pt4-log-text').value.trim();
            const jobId = document.getElementById('pt4-job-id').value.trim();

            if (!logText) {
                showToast('error', 'Por favor ingresa el log de PokerTracker');
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

                // Debug: Log the response
                console.log('PT4 Log Upload Response:', data);
                console.log('Failed files count:', data.failed_files_count);
                console.log('Failed files array:', data.failed_files);

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
    }

    // Check API key status on startup
    checkApiKeyOnStartup();

    // Load initial data
    loadJobs();
    loadRecentJobs();
    loadBudgetInfo();

    // Refresh recent jobs every 30 seconds
    setInterval(loadRecentJobs, 30000);

    // Refresh budget info every minute
    setInterval(loadBudgetInfo, 60000);
});
