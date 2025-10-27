const API_BASE = window.location.origin;

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

txtDropzone.addEventListener('click', () => txtInput.click());

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

txtInput.addEventListener('change', (e) => {
    handleTxtFiles(e.target.files);
});

function handleTxtFiles(files) {
    for (let file of files) {
        if (file.name.endsWith('.txt')) {
            txtFiles.push(file);
        }
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
        });
        txtFilesList.appendChild(div);
    });
}

screenshotDropzone.addEventListener('click', () => screenshotInput.click());

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

screenshotInput.addEventListener('change', (e) => {
    handleScreenshotFiles(e.target.files);
});

function handleScreenshotFiles(files) {
    for (let file of files) {
        if (file.name.match(/\.(png|jpg|jpeg)$/i)) {
            screenshotFiles.push(file);
        }
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
        });
        screenshotFilesList.appendChild(div);
    });
}

function updateUploadButton() {
    uploadBtn.disabled = txtFiles.length === 0 || screenshotFiles.length === 0;
}

uploadBtn.addEventListener('click', async () => {
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
            throw new Error('Upload failed');
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
        
        updateProcessingUI(job);

        if (job.status === 'completed') {
            stopStatusPolling();
            stopTimer();
            showResults(job);
        } else if (job.status === 'failed') {
            stopStatusPolling();
            stopTimer();
            showError(job.error_message || 'Processing failed');
        }
    } catch (error) {
        console.error('Error checking status:', error);
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

function showProcessing() {
    welcomeSection.classList.add('d-none');
    processingSection.classList.remove('d-none');
    resultsSection.classList.add('d-none');
    errorSection.classList.add('d-none');
}

function showResults(job) {
    processingSection.classList.add('d-none');
    resultsSection.classList.remove('d-none');

    const stats = job.statistics || {};
    const detailedStats = job.detailed_stats || {};
    const processingTime = stats.processing_time ? formatDuration(stats.processing_time) : 'N/A';

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
                <div class="stat-value">${detailedStats.high_confidence_matches || 0}</div>
                <div class="stat-label">Alta Confianza (≥80%)</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${processingTime}</div>
                <div class="stat-label">Tiempo de Proceso</div>
            </div>
        </div>
    `;

    downloadBtn.onclick = () => downloadResult(currentJobId);
    loadJobs();
}

function showError(message) {
    processingSection.classList.add('d-none');
    errorSection.classList.remove('d-none');
    errorMessage.textContent = message;
}

function resetToWelcome() {
    welcomeSection.classList.remove('d-none');
    processingSection.classList.add('d-none');
    resultsSection.classList.add('d-none');
    errorSection.classList.add('d-none');

    txtFiles = [];
    screenshotFiles = [];
    currentJobId = null;
    startTime = null;
    renderTxtFiles();
    renderScreenshotFiles();
    updateUploadButton();
    uploadBtn.innerHTML = '<i class="bi bi-upload"></i> Subir y Procesar';

    loadJobs();
}

newJobBtn.addEventListener('click', resetToWelcome);
retryBtn.addEventListener('click', resetToWelcome);

async function downloadResult(jobId) {
    window.location.href = `${API_BASE}/api/download/${jobId}`;
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
            'processing': 'bi-arrow-repeat text-primary spinning',
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

document.addEventListener('DOMContentLoaded', () => {
    loadJobs();
});
