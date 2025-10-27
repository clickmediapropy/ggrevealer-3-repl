const API_BASE = window.location.origin;

let txtFiles = [];
let screenshotFiles = [];
let currentJobId = null;
let statusCheckInterval = null;

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
        startStatusPolling();

    } catch (error) {
        console.error('Error:', error);
        showError('Error al subir archivos: ' + error.message);
        uploadBtn.disabled = false;
        uploadBtn.innerHTML = '<i class="bi bi-upload"></i> Subir y Procesar';
    }
});

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
        statusText.textContent = getStatusMessage(job.status);

        if (job.status === 'completed') {
            stopStatusPolling();
            showResults(job);
        } else if (job.status === 'failed') {
            stopStatusPolling();
            showError(job.error_message || 'Processing failed');
        }
    } catch (error) {
        console.error('Error checking status:', error);
    }
}

function getStatusMessage(status) {
    const messages = {
        'pending': 'En cola...',
        'processing': 'Procesando archivos...',
        'completed': 'Completado',
        'failed': 'Error en procesamiento'
    };
    return messages[status] || 'Desconocido';
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

    const stats = job.result?.stats || {};
    resultsStats.innerHTML = `
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">${stats.matched_hands || 0}</div>
                <div class="stat-label">Manos Matched</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.mappings_count || 0}</div>
                <div class="stat-label">Nombres Resueltos</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${stats.high_confidence_matches || 0}</div>
                <div class="stat-label">Alta Confianza (≥80%)</div>
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
        div.className = 'job-item';

        const statusClass = `badge-${job.status}`;
        const createdDate = new Date(job.created_at).toLocaleString('es-ES');

        div.innerHTML = `
            <div class="job-header">
                <div class="job-id">Job #${job.id}</div>
                <span class="badge-status ${statusClass}">${job.status}</span>
            </div>
            <div class="job-details">
                <p class="mb-1"><small><i class="bi bi-calendar"></i> ${createdDate}</small></p>
                <p class="mb-2"><small><i class="bi bi-file-text"></i> ${job.txt_files_count} TXT | <i class="bi bi-image"></i> ${job.screenshot_files_count} Screenshots</small></p>
                ${job.status === 'completed' ? `
                    <button class="btn btn-sm btn-success" onclick="downloadResult(${job.id})">
                        <i class="bi bi-download"></i> Descargar
                    </button>
                ` : ''}
            </div>
        `;

        jobsList.appendChild(div);
    });
}

document.addEventListener('DOMContentLoaded', () => {
    loadJobs();
});
