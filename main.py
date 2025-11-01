"""
FastAPI application entry point
"""

import os
import asyncio
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
import zipfile
from dataclasses import asdict
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request, Form
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import List, Optional
import shutil

from database import init_db, create_job, get_job, get_all_jobs, update_job_status, add_file, get_job_files, save_result, get_result, update_job_file_counts, delete_job, mark_job_started, update_job_stats, set_ocr_total_count, increment_ocr_processed_count, save_screenshot_result, get_screenshot_results, update_screenshot_result_matches, get_job_logs, clear_job_results, save_ocr1_result, save_ocr2_result, mark_screenshot_discarded, update_job_detailed_metrics, update_job_cost, get_budget_config, save_budget_config, get_budget_summary
from config import GEMINI_COST_PER_IMAGE
from parser import GGPokerParser
from ocr import ocr_hand_id, ocr_player_details
from matcher import find_best_matches, _build_seat_mapping_by_roles
from writer import generate_txt_files_by_table, generate_txt_files_with_validation, validate_output_format, extract_table_name
from models import NameMapping, ParsedHand
from logger import get_job_logger
from google import genai
from google.genai import types

# File upload limits
MAX_TXT_FILES = 300
MAX_SCREENSHOT_FILES = 300
MAX_UPLOAD_SIZE_MB = 300
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024  # 300 MB in bytes

app = FastAPI(
    title="GGRevealer API",
    description="De-anonymize GGPoker hand histories using screenshot OCR",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware to enforce upload size limit and disable caching
@app.middleware("http")
async def limit_upload_size(request: Request, call_next):
    """Enforce maximum upload size and disable caching for static files"""
    if request.method == "POST" and request.url.path == "/api/upload":
        content_length = request.headers.get("content-length")
        if content_length:
            content_length = int(content_length)
            if content_length > MAX_UPLOAD_SIZE_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"El tamaño total de los archivos excede el límite de {MAX_UPLOAD_SIZE_MB} MB. Tamaño recibido: {content_length / (1024 * 1024):.1f} MB"
                    }
                )
    response = await call_next(request)
    
    # Disable caching for static files to ensure fresh content
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    return response

STORAGE_PATH = Path("storage")
UPLOADS_PATH = STORAGE_PATH / "uploads"
OUTPUTS_PATH = STORAGE_PATH / "outputs"
DEBUG_PATH = STORAGE_PATH / "debug"

UPLOADS_PATH.mkdir(parents=True, exist_ok=True)
OUTPUTS_PATH.mkdir(parents=True, exist_ok=True)
DEBUG_PATH.mkdir(parents=True, exist_ok=True)

Path("static").mkdir(exist_ok=True)
Path("static/css").mkdir(exist_ok=True)
Path("static/js").mkdir(exist_ok=True)
Path("templates").mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()
    print("✅ FastAPI app started")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_api_key_from_request(request: Request) -> str:
    """
    Get API key from request header or fallback to environment variable

    Args:
        request: FastAPI Request object

    Returns:
        API key string (from header or env)
    """
    # Try to get API key from request header
    user_api_key = request.headers.get('X-Gemini-API-Key')
    if user_api_key and user_api_key.strip():
        return user_api_key.strip()

    # Fallback to environment variable
    return os.getenv('GEMINI_API_KEY', 'DUMMY_API_KEY_FOR_TESTING')


async def ocr_hand_id_with_retry(
    screenshot_path: str,
    screenshot_filename: str,
    job_id: int,
    api_key: str,
    logger,
    max_retries: int = 1
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    OCR1 with retry logic for transient failures

    Args:
        screenshot_path: Path to screenshot
        screenshot_filename: Filename for DB tracking
        job_id: Job ID for DB tracking
        api_key: Gemini API key
        logger: Job logger
        max_retries: Maximum retry attempts (default 1)

    Returns:
        Tuple of (success, hand_id, error)
    """
    retry_count = 0
    last_error = None

    # Initial attempt
    success, hand_id, error = await ocr_hand_id(screenshot_path, api_key)
    save_ocr1_result(job_id, screenshot_filename, success, hand_id, error, retry_count=0)

    if success:
        logger.info(f"OCR1 success (first attempt): {screenshot_filename} → {hand_id}")
        return (True, hand_id, None)

    logger.warning(f"OCR1 failed (attempt 1): {screenshot_filename} - {error}")
    last_error = error

    # Retry logic
    for retry_count in range(1, max_retries + 1):
        logger.info(f"Retrying OCR1 (attempt {retry_count + 1}): {screenshot_filename}")

        # Wait 1 second before retry (avoid rate limits)
        await asyncio.sleep(1)

        success, hand_id, error = await ocr_hand_id(screenshot_path, api_key)
        save_ocr1_result(job_id, screenshot_filename, success, hand_id, error, retry_count=retry_count)

        if success:
            logger.info(f"OCR1 success (retry {retry_count}): {screenshot_filename} → {hand_id}")
            return (True, hand_id, None)

        logger.warning(f"OCR1 failed (attempt {retry_count + 1}): {screenshot_filename} - {error}")
        last_error = error

    # All attempts failed
    logger.error(f"OCR1 failed after {max_retries + 1} attempts: {screenshot_filename}")
    return (False, None, last_error)


# ============================================================================
# API ROUTES
# ============================================================================

@app.get("/")
async def root():
    """Redirect to the app"""
    return RedirectResponse(url="/app")


@app.get("/app")
async def serve_app(request: Request):
    """Serve the main application page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/upload")
async def upload_files(
    txt_files: List[UploadFile] = File(...),
    screenshots: List[UploadFile] = File(...),
    api_tier: str = Form(default='free')
):
    """Upload TXT files and screenshots for a new job"""
    # Validate API tier
    if api_tier not in ('free', 'paid'):
        api_tier = 'free'

    # Validate file count limits
    if len(txt_files) > MAX_TXT_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Excede el límite de archivos TXT. Máximo: {MAX_TXT_FILES}, Recibidos: {len(txt_files)}"
        )

    if len(screenshots) > MAX_SCREENSHOT_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Excede el límite de screenshots. Máximo: {MAX_SCREENSHOT_FILES}, Recibidos: {len(screenshots)}"
        )

    job_id = create_job(api_tier=api_tier)

    job_upload_path = UPLOADS_PATH / str(job_id)
    job_upload_path.mkdir(exist_ok=True)
    
    txt_path = job_upload_path / "txt"
    screenshots_path = job_upload_path / "screenshots"
    txt_path.mkdir(exist_ok=True)
    screenshots_path.mkdir(exist_ok=True)
    
    for txt_file in txt_files:
        if not txt_file.filename:
            raise HTTPException(status_code=400, detail="File must have a filename")
        file_path = txt_path / txt_file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(txt_file.file, f)
        add_file(job_id, txt_file.filename, "txt", str(file_path))
    
    for screenshot in screenshots:
        if not screenshot.filename:
            raise HTTPException(status_code=400, detail="File must have a filename")
        file_path = screenshots_path / screenshot.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(screenshot.file, f)
        add_file(job_id, screenshot.filename, "screenshot", str(file_path))
    
    update_job_file_counts(job_id, len(txt_files), len(screenshots))
    
    return {
        "job_id": job_id,
        "txt_files_count": len(txt_files),
        "screenshot_files_count": len(screenshots)
    }


@app.post("/api/process/{job_id}")
async def process_job(job_id: int, request: Request, background_tasks: BackgroundTasks):
    """Start processing a job in the background (supports reprocessing)"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job['status'] == 'processing':
        raise HTTPException(status_code=400, detail="Job is already processing")

    # Check budget before processing
    budget_summary = get_budget_summary()
    if budget_summary['monthly_spending'] >= budget_summary['monthly_budget']:
        raise HTTPException(
            status_code=403,
            detail=f"Presupuesto mensual agotado (${budget_summary['monthly_spending']:.2f} / ${budget_summary['monthly_budget']:.2f}). No se pueden procesar más jobs hasta el próximo ciclo."
        )

    # Check if this is a reprocess (job already completed or failed)
    is_reprocess = job['status'] in ['completed', 'failed']

    if is_reprocess:
        # Clear previous results from database
        clear_job_results(job_id)

        # Clear output files from filesystem
        job_output_path = OUTPUTS_PATH / str(job_id)
        if job_output_path.exists():
            shutil.rmtree(job_output_path)

        print(f"[JOB {job_id}] Reprocessing: cleared previous results")

    # Get API key from request header or fallback to env
    api_key = get_api_key_from_request(request)

    # Start processing with user's API key
    background_tasks.add_task(run_processing_pipeline, job_id, api_key)
    update_job_status(job_id, 'processing')

    return {"job_id": job_id, "status": "processing", "is_reprocess": is_reprocess}


@app.get("/api/status/{job_id}")
async def get_job_status(job_id: int):
    """Get current status of a job with detailed statistics"""
    from datetime import datetime
    
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Calculate elapsed time if processing
    elapsed_time = None
    if job['status'] == 'processing' and job.get('started_at'):
        started = datetime.fromisoformat(job['started_at'])
        elapsed_time = (datetime.utcnow() - started).total_seconds()
    
    # Build enhanced response
    response = {
        **job,
        'elapsed_time_seconds': elapsed_time,
        'statistics': {
            'txt_files': job.get('txt_files_count', 0),
            'screenshots': job.get('screenshot_files_count', 0),
            'hands_parsed': job.get('hands_parsed', 0),
            'matched_hands': job.get('matched_hands', 0),
            'name_mappings': job.get('name_mappings_count', 0),
            'processing_time': job.get('processing_time_seconds'),
            'ocr_processed': job.get('ocr_processed_count', 0),
            'ocr_total': job.get('ocr_total_count', 0)
        },
        'costs': {
            'ocr1_images': job.get('ocr1_images_processed', 0),
            'ocr2_images': job.get('ocr2_images_processed', 0),
            'total_cost_usd': job.get('total_api_cost', 0.0),
            'cost_calculated_at': job.get('cost_calculated_at')
        }
    }
    
    # Add detailed result stats if completed
    if job['status'] == 'completed':
        result = get_result(job_id)
        if result and result.get('stats'):
            response['detailed_stats'] = result['stats']

            # EXPOSE DETAILED METRICS directly for frontend use
            if result['stats'].get('detailed_metrics'):
                response['detailed_metrics'] = result['stats']['detailed_metrics']

            # Calculate OCR success rate
            screenshots = job.get('screenshot_files_count', 0)
            matches = job.get('matched_hands', 0)
            if screenshots > 0:
                response['statistics']['ocr_success_rate'] = round((matches / screenshots) * 100, 1)
    
    return response


@app.get("/api/download/{job_id}")
async def download_output(job_id: int):
    """Download the processed ZIP file for successful files"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job is not completed yet")
    
    result = get_result(job_id)
    if not result or not result.get('output_txt_path'):
        raise HTTPException(status_code=404, detail="Output file not found")
    
    output_path = Path(result['output_txt_path'])

    # Check if it's a ZIP file (new format) or TXT file (old format)
    if output_path.suffix == '.zip' and output_path.exists():
        # VALIDATE ZIP INTEGRITY BEFORE DOWNLOAD
        try:
            with zipfile.ZipFile(output_path, 'r') as zipf:
                # testzip() returns None if valid, filename if corrupted
                bad_file = zipf.testzip()
                if bad_file:
                    logger = JobLogger(job_id=job_id)
                    logger.error(f"ZIP file corrupted: cannot read {bad_file}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"Output file is corrupted and cannot be extracted. "
                               f"Contact administrator with job ID {job_id}"
                    )
        except zipfile.BadZipFile:
            logger = JobLogger(job_id=job_id)
            logger.error(f"ZIP file is invalid/corrupted")
            raise HTTPException(
                status_code=500,
                detail=f"Output file is corrupted. Contact administrator with job ID {job_id}"
            )

        return FileResponse(
            path=output_path,
            filename=f"resolved_hands_{job_id}.zip",
            media_type="application/zip"
        )
    elif output_path.suffix == '.txt' and output_path.exists():
        # Legacy support for old TXT files
        return FileResponse(
            path=output_path,
            filename=f"resolved_hands_{job_id}.txt",
            media_type="text/plain"
        )
    else:
        raise HTTPException(status_code=404, detail="Output file not found on disk")


@app.get("/api/download-fallidos/{job_id}")
async def download_failed_files(job_id: int):
    """Download the ZIP file containing failed files (with unmapped IDs)"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Job is not completed yet")
    
    # Check if fallidos.zip exists
    fallidos_path = OUTPUTS_PATH / str(job_id) / "fallidos.zip"

    if not fallidos_path.exists():
        raise HTTPException(status_code=404, detail="No failed files found for this job")

    # VALIDATE ZIP INTEGRITY BEFORE DOWNLOAD
    try:
        with zipfile.ZipFile(fallidos_path, 'r') as zipf:
            # testzip() returns None if valid, filename if corrupted
            bad_file = zipf.testzip()
            if bad_file:
                logger = JobLogger(job_id=job_id)
                logger.error(f"ZIP file corrupted: cannot read {bad_file}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed files ZIP is corrupted and cannot be extracted. "
                           f"Contact administrator with job ID {job_id}"
                )
    except zipfile.BadZipFile:
        logger = JobLogger(job_id=job_id)
        logger.error(f"ZIP file is invalid/corrupted")
        raise HTTPException(
            status_code=500,
            detail=f"Failed files ZIP is corrupted. Contact administrator with job ID {job_id}"
        )

    return FileResponse(
        path=fallidos_path,
        filename=f"fallidos_{job_id}.zip",
        media_type="application/zip"
    )


@app.get("/api/jobs")
async def list_jobs():
    """Get list of all jobs"""
    jobs = get_all_jobs()
    return {"jobs": jobs}


@app.get("/api/config/budget")
async def get_budget():
    """Get current budget configuration and spending"""
    summary = get_budget_summary()
    return summary


@app.post("/api/config/budget")
async def update_budget(request: Request):
    """Update budget configuration"""
    data = await request.json()

    monthly_budget = data.get('monthly_budget')
    budget_reset_day = data.get('budget_reset_day', 1)

    if monthly_budget is None:
        raise HTTPException(status_code=400, detail="monthly_budget is required")

    if not isinstance(monthly_budget, (int, float)) or monthly_budget < 0:
        raise HTTPException(status_code=400, detail="monthly_budget must be a positive number")

    if not isinstance(budget_reset_day, int) or budget_reset_day < 1 or budget_reset_day > 28:
        raise HTTPException(status_code=400, detail="budget_reset_day must be between 1 and 28")

    save_budget_config(monthly_budget, budget_reset_day)

    return {"message": "Budget configuration updated", "monthly_budget": monthly_budget, "budget_reset_day": budget_reset_day}


@app.post("/api/validate-api-key")
async def validate_api_key(request: Request):
    """
    Validate a Gemini API key by testing it with a simple request

    Expects JSON body: {"api_key": "your-api-key-here"}
    Returns: {"valid": true/false, "error": "message" (if invalid)}
    """
    try:
        data = await request.json()
        api_key = data.get('api_key', '').strip()

        if not api_key:
            return JSONResponse(
                status_code=400,
                content={"valid": False, "error": "API key is required"}
            )

        # Test the API key with a minimal Gemini request
        # Create thread-safe client with the provided API key
        client = genai.Client(api_key=api_key)

        # Use the simplest possible request to test the key
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents='Test'
        )

        # If we got here, the API key is valid
        return {"valid": True, "message": "API key is valid"}

    except Exception as e:
        error_message = str(e)

        # Check for common error patterns
        if "API_KEY_INVALID" in error_message or "invalid API key" in error_message.lower():
            return JSONResponse(
                status_code=401,
                content={"valid": False, "error": "API key inválida. Verifica que sea correcta."}
            )
        elif "quota" in error_message.lower() or "limit" in error_message.lower():
            return JSONResponse(
                status_code=429,
                content={"valid": False, "error": "Límite de cuota excedido. Verifica tu saldo en Google Cloud."}
            )
        else:
            return JSONResponse(
                status_code=500,
                content={"valid": False, "error": f"Error al validar API key: {error_message}"}
            )


@app.get("/api/job/{job_id}/screenshots")
async def get_job_screenshots(job_id: int):
    """Get detailed screenshot results for a job"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    screenshot_results = get_screenshot_results(job_id)
    return {"screenshots": screenshot_results}


@app.get("/api/debug/{job_id}")
async def get_debug_info(job_id: int):
    """Get comprehensive debugging information for a job"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get all related data
    files = get_job_files(job_id)
    result = get_result(job_id)
    screenshot_results = get_screenshot_results(job_id)
    logs = get_job_logs(job_id, limit=1000)  # Last 1000 logs

    # Build comprehensive debug info
    debug_info = {
        "job": job,
        "files": {
            "txt_files": [f for f in files if f['file_type'] == 'txt'],
            "screenshots": [f for f in files if f['file_type'] == 'screenshot'],
            "total_txt": len([f for f in files if f['file_type'] == 'txt']),
            "total_screenshots": len([f for f in files if f['file_type'] == 'screenshot'])
        },
        "result": result,
        "screenshots": {
            "results": screenshot_results,
            "summary": {
                "total": len(screenshot_results),
                "success": len([s for s in screenshot_results if s.get('status') == 'success']),
                "warning": len([s for s in screenshot_results if s.get('status') == 'warning']),
                "error": len([s for s in screenshot_results if s.get('status') == 'error'])
            }
        },
        "logs": {
            "entries": logs,
            "count": len(logs),
            "by_level": {
                "DEBUG": len([l for l in logs if l.get('level') == 'DEBUG']),
                "INFO": len([l for l in logs if l.get('level') == 'INFO']),
                "WARNING": len([l for l in logs if l.get('level') == 'WARNING']),
                "ERROR": len([l for l in logs if l.get('level') == 'ERROR']),
                "CRITICAL": len([l for l in logs if l.get('level') == 'CRITICAL'])
            }
        },
        "statistics": {
            "txt_files": job.get('txt_files_count', 0),
            "screenshots": job.get('screenshot_files_count', 0),
            "hands_parsed": job.get('hands_parsed', 0),
            "matched_hands": job.get('matched_hands', 0),
            "name_mappings": job.get('name_mappings_count', 0),
            "processing_time": job.get('processing_time_seconds'),
            "ocr_processed": job.get('ocr_processed_count', 0),
            "ocr_total": job.get('ocr_total_count', 0)
        },
        "timestamps": {
            "created_at": job.get('created_at'),
            "started_at": job.get('started_at'),
            "completed_at": job.get('completed_at')
        }
    }

    return debug_info


def _export_debug_json(job_id: int) -> dict | None:
    """
    Helper function to export debug information to JSON file
    Returns dict with filepath, filename, and debug_info, or None if job not found
    """
    job = get_job(job_id)
    if not job:
        return None

    # Get all debug data
    files = get_job_files(job_id)
    result = get_result(job_id)
    screenshot_results = get_screenshot_results(job_id)
    logs = get_job_logs(job_id, limit=1000)

    # Build comprehensive debug info
    debug_info = {
        "job": job,
        "files": {
            "txt_files": [f for f in files if f['file_type'] == 'txt'],
            "screenshots": [f for f in files if f['file_type'] == 'screenshot'],
            "total_txt": len([f for f in files if f['file_type'] == 'txt']),
            "total_screenshots": len([f for f in files if f['file_type'] == 'screenshot'])
        },
        "result": result,
        "screenshots": {
            "results": screenshot_results,
            "summary": {
                "total": len(screenshot_results),
                "success": len([s for s in screenshot_results if s.get('status') == 'success']),
                "warning": len([s for s in screenshot_results if s.get('status') == 'warning']),
                "error": len([s for s in screenshot_results if s.get('status') == 'error'])
            }
        },
        "logs": {
            "entries": logs,
            "count": len(logs),
            "by_level": {
                "DEBUG": len([l for l in logs if l.get('level') == 'DEBUG']),
                "INFO": len([l for l in logs if l.get('level') == 'INFO']),
                "WARNING": len([l for l in logs if l.get('level') == 'WARNING']),
                "ERROR": len([l for l in logs if l.get('level') == 'ERROR']),
                "CRITICAL": len([l for l in logs if l.get('level') == 'CRITICAL'])
            }
        },
        "statistics": {
            "txt_files": job.get('txt_files_count', 0),
            "screenshots": job.get('screenshot_files_count', 0),
            "hands_parsed": job.get('hands_parsed', 0),
            "matched_hands": job.get('matched_hands', 0),
            "name_mappings": job.get('name_mappings_count', 0),
            "processing_time": job.get('processing_time_seconds'),
            "ocr_processed": job.get('ocr_processed_count', 0),
            "ocr_total": job.get('ocr_total_count', 0)
        },
        "timestamps": {
            "created_at": job.get('created_at'),
            "started_at": job.get('started_at'),
            "completed_at": job.get('completed_at')
        },
        "export_timestamp": datetime.utcnow().isoformat(),
        "export_info": {
            "exported_at": datetime.utcnow().isoformat(),
            "exporter": "GGRevealer Debug System",
            "version": "1.0.0"
        }
    }

    # Save to storage/debug/
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"debug_job_{job_id}_{timestamp}.json"
    filepath = DEBUG_PATH / filename

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(debug_info, f, indent=2, ensure_ascii=False)

    return {
        "filepath": str(filepath),
        "filename": filename,
        "debug_info": debug_info
    }


@app.post("/api/debug/{job_id}/export")
async def export_debug_info(job_id: int):
    """Export debug information to JSON file in storage/debug/"""
    result = _export_debug_json(job_id)

    if not result:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "success": True,
        "message": f"Debug info exported to {result['filename']}",
        "filepath": result['filepath'],
        "filename": result['filename'],
        "data": result['debug_info']
    }


def _analyze_debug_data(debug_json_path: str) -> dict:
    """
    Analiza el archivo JSON de debug y extrae información específica y accionable

    Returns:
        dict con análisis detallado incluyendo:
        - unmapped_players: lista de IDs no mapeados con tablas
        - validation_errors: errores de validación específicos
        - screenshot_failures: screenshots que fallaron OCR con detalles
        - critical_logs: logs ERROR/CRITICAL con contexto
        - patterns_detected: patrones identificados (ej: hero_position null)
        - priority_issues: lista priorizada de problemas
    """
    try:
        with open(debug_json_path, 'r') as f:
            debug_data = json.load(f)
    except Exception as e:
        return {
            "error": f"No se pudo leer el archivo debug: {str(e)}",
            "unmapped_players": [],
            "validation_errors": [],
            "screenshot_failures": [],
            "critical_logs": [],
            "patterns_detected": [],
            "priority_issues": []
        }

    analysis = {
        "unmapped_players": [],
        "validation_errors": [],
        "screenshot_failures": [],
        "critical_logs": [],
        "patterns_detected": [],
        "priority_issues": [],
        "specific_problems": []
    }

    # 1. Extraer unmapped players de result.stats
    result = debug_data.get('result') or {}
    stats = result.get('stats', {}) if result else {}

    if stats.get('unmapped_players'):
        for unmapped_id in stats['unmapped_players']:
            analysis['unmapped_players'].append({
                "player_id": unmapped_id,
                "count": stats['unmapped_players_count']
            })

    # Obtener unmapped_ids por archivo desde failed_files
    if stats.get('failed_files'):
        for failed_file in stats['failed_files']:
            table = failed_file.get('table')
            unmapped_ids = failed_file.get('unmapped_ids', [])
            for uid in unmapped_ids:
                analysis['unmapped_players'].append({
                    "player_id": uid,
                    "table": table,
                    "hands_in_table": failed_file.get('total_hands')
                })

    # 2. Extraer validation errors
    if stats.get('validation_errors'):
        for error in stats['validation_errors']:
            analysis['validation_errors'].append(error)
            # Detectar errores críticos
            if "CRITICAL" in error or "PokerTracker will REJECT" in error:
                analysis['priority_issues'].append({
                    "type": "VALIDATION_CRITICAL",
                    "description": error,
                    "severity": "HIGH"
                })

    # 3. Analizar screenshot results
    screenshots = debug_data.get('screenshots', {}).get('results', [])
    hero_position_issues = 0
    hand_id_missing = 0
    player_count_low = 0

    for screenshot in screenshots:
        if not screenshot.get('ocr_success'):
            analysis['screenshot_failures'].append({
                "filename": screenshot.get('screenshot_filename'),
                "error": screenshot.get('ocr_error'),
                "matches_found": screenshot.get('matches_found', 0)
            })
        else:
            # Analizar datos OCR para detectar patrones
            ocr_data = screenshot.get('ocr_data', {})

            # Detectar hero_position null
            if ocr_data.get('hero_position') is None and ocr_data.get('hero_name') is None:
                hero_position_issues += 1

            # Detectar hand_id faltante
            if not ocr_data.get('hand_id'):
                hand_id_missing += 1

            # Detectar pocos jugadores extraídos
            player_stacks = ocr_data.get('all_player_stacks', [])
            if len(player_stacks) < 3:  # Esperamos 3 jugadores en 3-max
                player_count_low += 1

            # Si no hubo matches, es un problema
            if screenshot.get('matches_found', 0) == 0:
                analysis['screenshot_failures'].append({
                    "filename": screenshot.get('screenshot_filename'),
                    "issue": "OCR exitoso pero 0 matches encontrados",
                    "hand_id_extracted": ocr_data.get('hand_id'),
                    "hero_position": ocr_data.get('hero_position'),
                    "players_extracted": len(player_stacks)
                })

    # 4. Extraer logs críticos
    logs = debug_data.get('logs', {}).get('entries', [])
    for log in logs:
        if log.get('level') in ['ERROR', 'CRITICAL']:
            analysis['critical_logs'].append({
                "level": log.get('level'),
                "message": log.get('message'),
                "timestamp": log.get('timestamp'),
                "extra_data": log.get('extra_data')
            })

    # 5. Detectar patrones
    total_screenshots = len(screenshots)

    if hero_position_issues > total_screenshots * 0.5:
        analysis['patterns_detected'].append({
            "pattern": "HERO_POSITION_NULL",
            "description": f"{hero_position_issues}/{total_screenshots} screenshots sin hero_position",
            "impact": "Impide el mapping de jugadores (visual position algorithm necesita hero_position)",
            "location": "ocr.py línea 46-117 (extracción de datos) o matcher.py línea 260 (_build_seat_mapping)"
        })
        analysis['priority_issues'].append({
            "type": "HERO_POSITION_NULL",
            "description": f"Mayoría de screenshots ({hero_position_issues}/{total_screenshots}) no tienen hero_position extraído",
            "severity": "HIGH",
            "suggested_fix": "Revisar prompt de OCR en ocr.py para asegurar que siempre extrae hero_position=1"
        })

    if hand_id_missing > total_screenshots * 0.3:
        analysis['patterns_detected'].append({
            "pattern": "HAND_ID_MISSING",
            "description": f"{hand_id_missing}/{total_screenshots} screenshots sin hand_id",
            "impact": "Sin hand_id, el matching es imposible",
            "location": "ocr.py línea 62-65 (extracción de Hand ID)"
        })

    if player_count_low > total_screenshots * 0.5:
        analysis['patterns_detected'].append({
            "pattern": "LOW_PLAYER_EXTRACTION",
            "description": f"{player_count_low}/{total_screenshots} screenshots con menos de 3 jugadores",
            "impact": "Mappings incompletos, algunos jugadores quedan sin mapear",
            "location": "ocr.py prompt de Gemini"
        })

    # 6. Crear lista de problemas específicos con contexto
    if analysis['unmapped_players']:
        analysis['specific_problems'].append({
            "problem": f"{len(analysis['unmapped_players'])} jugadores sin mapear",
            "details": f"IDs no mapeados en {len(set(p.get('table') for p in analysis['unmapped_players'] if p.get('table')))} tablas",
            "examples": [p['player_id'] for p in analysis['unmapped_players'][:5]],
            "action": "Revisar por qué estos IDs no se mapearon - falta screenshot o matching falló"
        })

    if analysis['screenshot_failures']:
        analysis['specific_problems'].append({
            "problem": f"{len(analysis['screenshot_failures'])} screenshots con problemas",
            "details": "Algunos screenshots no generaron matches a pesar de OCR exitoso",
            "examples": [s['filename'] for s in analysis['screenshot_failures'][:3]],
            "action": "Revisar matcher.py o calidad de extracción OCR"
        })

    return analysis


@app.post("/api/debug/{job_id}/generate-prompt")
async def generate_claude_prompt(job_id: int):
    """Generate a Claude Code debugging prompt using Gemini AI"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Export debug JSON first (so Claude Code can read it)
    debug_export = _export_debug_json(job_id)
    debug_json_path = debug_export['filepath'] if debug_export else "No disponible (error al exportar)"
    debug_json_filename = debug_export['filename'] if debug_export else "debug_info.json"

    # Analyze debug data to extract specific information
    detailed_analysis = _analyze_debug_data(debug_json_path) if debug_export else {}

    # Get all debug data
    files = get_job_files(job_id)
    result = get_result(job_id)
    screenshot_results = get_screenshot_results(job_id)
    logs = get_job_logs(job_id, limit=1000)

    # Filter error logs
    error_logs = [l for l in logs if l.get('level') in ['ERROR', 'CRITICAL']]
    warning_logs = [l for l in logs if l.get('level') == 'WARNING']

    # Get failed screenshots
    failed_screenshots = [s for s in screenshot_results if s.get('status') == 'error']

    # Calculate metrics
    stats = {
        "txt_files": job.get('txt_files_count', 0),
        "screenshots": job.get('screenshot_files_count', 0),
        "hands_parsed": job.get('hands_parsed', 0),
        "matched_hands": job.get('matched_hands', 0),
        "name_mappings": job.get('name_mappings_count', 0),
        "ocr_processed": job.get('ocr_processed_count', 0),
        "ocr_total": job.get('ocr_total_count', 0)
    }

    # Calculate key metrics
    match_rate = (stats['matched_hands'] / stats['hands_parsed'] * 100) if stats['hands_parsed'] > 0 else 0
    ocr_success_rate = (stats['ocr_processed'] / stats['ocr_total'] * 100) if stats['ocr_total'] > 0 else 0

    screenshot_summary = {
        "total": len(screenshot_results),
        "success": len([s for s in screenshot_results if s.get('status') == 'success']),
        "warning": len([s for s in screenshot_results if s.get('status') == 'warning']),
        "error": len([s for s in screenshot_results if s.get('status') == 'error'])
    }

    screenshot_success_rate = (screenshot_summary['success'] / screenshot_summary['total'] * 100) if screenshot_summary['total'] > 0 else 0

    # Identify problem type
    problem_indicators = []

    if job.get('status') == 'failed':
        problem_indicators.append("JOB_FAILED")

    if match_rate < 10:
        problem_indicators.append("VERY_LOW_MATCH_RATE")
    elif match_rate < 30:
        problem_indicators.append("LOW_MATCH_RATE")

    if screenshot_success_rate < 50:
        problem_indicators.append("LOW_OCR_SUCCESS")

    if ocr_success_rate < 100:
        problem_indicators.append("INCOMPLETE_OCR")

    if len(error_logs) > 0:
        problem_indicators.append("HAS_ERROR_LOGS")

    if len(warning_logs) > 5:
        problem_indicators.append("MANY_WARNINGS")

    if screenshot_summary['error'] > screenshot_summary['total'] * 0.3:
        problem_indicators.append("HIGH_SCREENSHOT_FAILURE_RATE")

    # Get failed screenshots with errors
    failed_screenshots_with_details = []
    for fs in failed_screenshots[:10]:
        failed_screenshots_with_details.append({
            "filename": fs.get('screenshot_filename'),
            "error": fs.get('ocr_error'),
            "ocr_success": fs.get('ocr_success')
        })

    # Build context for Gemini
    context = {
        "job_id": job_id,
        "status": job.get('status'),
        "error_message": job.get('error_message'),
        "problem_indicators": problem_indicators,
        "statistics": stats,
        "calculated_metrics": {
            "match_rate_percent": round(match_rate, 2),
            "ocr_success_rate_percent": round(ocr_success_rate, 2),
            "screenshot_success_rate_percent": round(screenshot_success_rate, 2)
        },
        "timestamps": {
            "created_at": job.get('created_at'),
            "started_at": job.get('started_at'),
            "completed_at": job.get('completed_at'),
            "processing_time_seconds": job.get('processing_time_seconds')
        },
        "error_logs": error_logs[:10],
        "warning_logs": warning_logs[:10],
        "failed_screenshots": failed_screenshots_with_details,
        "screenshot_summary": screenshot_summary,
        "debug_json_path": debug_json_path,
        "debug_json_filename": debug_json_filename
    }

    # If job has result with detailed stats, include them
    if result and result.get('stats'):
        context["result_stats"] = result['stats']

    # Add detailed analysis to context
    context["detailed_analysis"] = detailed_analysis

    # Configure Gemini
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key or api_key == 'your_gemini_api_key_here':
        # Fallback: generate simple prompt without AI
        return {
            "success": False,
            "message": "GEMINI_API_KEY not configured",
            "prompt": _generate_fallback_prompt(context, detailed_analysis),
            "debug_json_path": debug_json_path
        }

    try:
        # Create thread-safe client with API key
        client = genai.Client(api_key=api_key)

        # Build detailed problem summary
        problem_summary = []
        if detailed_analysis.get('unmapped_players'):
            unmapped_count = len(detailed_analysis['unmapped_players'])
            tables_affected = len(set(p.get('table') for p in detailed_analysis['unmapped_players'] if p.get('table')))
            problem_summary.append(f"- {unmapped_count} jugadores sin mapear en {tables_affected} tablas")

        if detailed_analysis.get('patterns_detected'):
            for pattern in detailed_analysis['patterns_detected']:
                problem_summary.append(f"- {pattern['pattern']}: {pattern['description']}")

        if detailed_analysis.get('validation_errors'):
            problem_summary.append(f"- {len(detailed_analysis['validation_errors'])} errores de validación")

        # Create prompt for Gemini
        gemini_prompt = f"""Eres un experto en debugging de aplicaciones Python, análisis de errores y detección de problemas en pipelines de procesamiento de datos.

Tu tarea es analizar la información de un job de GGRevealer y generar un prompt ÚTIL y ACCIONABLE para Claude Code.

**MUY IMPORTANTE - ARCHIVO JSON DE DEBUG:**
Se ha exportado un archivo JSON con información detallada del job:
- Ruta: {debug_json_path}
- Nombre: {debug_json_filename}

Este archivo contiene toda la información del job incluyendo logs completos, estadísticas detalladas, resultados de screenshots, etc.
En el prompt que generes, DEBES incluir una instrucción para que Claude Code LEA este archivo JSON primero antes de hacer cualquier análisis.

**CONTEXTO DE GGREVEALER:**
GGRevealer es una aplicación FastAPI que desanonimiza hand histories de poker usando OCR con Gemini Vision:
- Pipeline: Upload → Parse TXT → OCR Screenshots → Match Hands → Generate Mappings → Write Outputs
- El objetivo es HACER MATCH de manos con screenshots para identificar jugadores anónimos
- Un BUEN resultado tiene >80% match rate (manos matched / manos parseadas)
- Un MAL resultado tiene <30% match rate

**INFORMACIÓN DEL JOB A ANALIZAR:**

{json.dumps(context, indent=2, ensure_ascii=False)}

**ANÁLISIS DETALLADO (DATOS CONCRETOS EXTRAÍDOS DEL JSON):**

**Problemas Específicos Detectados:**
{chr(10).join(problem_summary) if problem_summary else 'No se detectaron problemas específicos'}

**Unmapped Players ({len(detailed_analysis.get('unmapped_players', []))} total):**
{json.dumps(detailed_analysis.get('unmapped_players', [])[:5], indent=2, ensure_ascii=False) if detailed_analysis.get('unmapped_players') else 'Ninguno'}

**Patrones Detectados:**
{json.dumps(detailed_analysis.get('patterns_detected', []), indent=2, ensure_ascii=False) if detailed_analysis.get('patterns_detected') else 'Ninguno'}

**Priority Issues:**
{json.dumps(detailed_analysis.get('priority_issues', []), indent=2, ensure_ascii=False) if detailed_analysis.get('priority_issues') else 'Ninguno'}

**Screenshot Failures ({len(detailed_analysis.get('screenshot_failures', []))} total):**
{json.dumps(detailed_analysis.get('screenshot_failures', [])[:3], indent=2, ensure_ascii=False) if detailed_analysis.get('screenshot_failures') else 'Ninguno'}

**Validation Errors:**
{json.dumps(detailed_analysis.get('validation_errors', [])[:5], indent=2, ensure_ascii=False) if detailed_analysis.get('validation_errors') else 'Ninguno'}

**INDICADORES DE PROBLEMAS DETECTADOS:**
{', '.join(problem_indicators) if problem_indicators else 'Ninguno detectado automáticamente'}

**USA EL ANÁLISIS DETALLADO para generar un prompt ESPECÍFICO:**

El análisis detallado ya extrajo información concreta del JSON:
- Unmapped Players: IDs específicos y en qué tablas están
- Patrones Detectados: problemas sistemáticos (ej: hero_position null en todos los screenshots)
- Priority Issues: problemas de alta severidad con suggested_fix
- Screenshot Failures: screenshots que no generaron matches con detalles de qué falló
- Validation Errors: errores de PokerTracker

**IDENTIFICA LA CAUSA RAÍZ:**

1. Si hay PATRONES DETECTADOS:
   - Usa el pattern['location'] para sugerir archivos y funciones EXACTAS
   - Usa el pattern['impact'] para explicar por qué es crítico
   - Usa el pattern['suggested_fix'] si existe

2. Si hay UNMAPPED PLAYERS con tablas:
   - Menciona IDs específicos (ej: "478db80b en tabla 7639")
   - Correlaciona con screenshots que deberían haber mapeado esos jugadores

3. Si hay PRIORITY ISSUES:
   - Priorízalos en el prompt
   - Incluye la severidad (HIGH/MEDIUM/LOW)
   - Menciona el suggested_fix

**GENERA UN PROMPT que:**

1. **PRIMERO: Instruye a Claude Code que lea el archivo JSON de debug**
   ```
   Lee el archivo {debug_json_path} para obtener información completa del job.
   ```

2. **Identifica el problema CONCRETO** (usa los datos específicos)
   - Ejemplo: "5 screenshots no tienen hero_position extraído, causando que _build_seat_mapping() en matcher.py:260 falle"
   - NO: "El matching no funciona bien"

3. **Menciona IDs, tablas, archivos ESPECÍFICOS**
   - Si hay unmapped ID "478db80b" en tabla "7639": menciónalo
   - Si screenshot "2025-10-27_10_55_AM.png" falló: menciónalo
   - Si función "_build_seat_mapping()" está involucrada: menciónala con línea

4. **Sugiere archivos/funciones EXACTAS basándote en los patrones detectados**
   - Usa pattern['location'] del análisis (ej: "ocr.py línea 46-117" o "matcher.py línea 260")
   - Proporciona el suggested_fix si existe

5. **Propone pasos ACCIONABLES**
   - Basados en el problema real detectado
   - Con comandos específicos si es posible

**FORMATO:**
- Markdown con secciones claras
- Máximo 500 palabras
- Enfócate en el problema #1 (el más crítico)
- Incluye ejemplos concretos (IDs, tablas, archivos con líneas)

**IMPORTANTE:**
- USA LOS DATOS ESPECÍFICOS del análisis detallado (unmapped players, patterns, priority issues)
- Menciona archivos Y líneas (ej: "matcher.py:260" no solo "matcher.py")
- Incluye IDs de jugadores, nombres de tablas, nombres de screenshots reales
- Si el análisis detallado tiene suggested_fix, ÚSALO

Genera SOLO el prompt para Claude Code (sin preamble, solo el prompt):"""

        # Call Gemini with thread-safe client
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=gemini_prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,  # Low temperature for consistent, focused output
                top_p=0.8,
                top_k=40,
                max_output_tokens=2048,
            )
        )

        generated_prompt = response.text.strip()

        # Validate the generated prompt
        validation_result = _validate_generated_prompt(generated_prompt, detailed_analysis, debug_json_path)

        if not validation_result['valid']:
            print(f"⚠️  Generated prompt has quality issues (score: {validation_result['quality_score']}):")
            for issue in validation_result['issues']:
                print(f"  - {issue}")

            # If validation fails badly (score < 50), use fallback instead
            if validation_result['quality_score'] < 50:
                print("❌ Prompt quality too low, using fallback instead")
                generated_prompt = _generate_fallback_prompt(context, detailed_analysis)
                validation_result = _validate_generated_prompt(generated_prompt, detailed_analysis, debug_json_path)
                print(f"✅ Fallback prompt quality score: {validation_result['quality_score']}")
        else:
            print(f"✅ Generated prompt passed validation (score: {validation_result['quality_score']})")

        return {
            "success": True,
            "prompt": generated_prompt,
            "context": context,
            "debug_json_path": debug_json_path,
            "debug_json_filename": debug_json_filename,
            "validation": validation_result
        }

    except Exception as e:
        print(f"Error calling Gemini for prompt generation: {e}")
        return {
            "success": False,
            "message": f"Error generating prompt: {str(e)}",
            "prompt": _generate_fallback_prompt(context, detailed_analysis),
            "debug_json_path": debug_json_path
        }


def _validate_generated_prompt(prompt: str, detailed_analysis: dict, debug_json_path: str) -> dict:
    """
    Validate the quality of a generated debugging prompt

    Returns:
        dict with 'valid' (bool) and 'issues' (list of problems found)
    """
    issues = []

    # Check 1: Prompt is not empty
    if not prompt or len(prompt.strip()) == 0:
        issues.append("Prompt está vacío")
        return {"valid": False, "issues": issues}

    # Check 2: Minimum length (200 chars for meaningful content)
    if len(prompt) < 200:
        issues.append(f"Prompt muy corto ({len(prompt)} chars, mínimo 200)")

    # Check 3: Contains debug JSON path reference
    if debug_json_path and debug_json_path not in prompt:
        issues.append("Prompt no menciona el archivo JSON de debug")

    # Check 4: If there are unmapped players, prompt should mention them
    if detailed_analysis.get('unmapped_players') and len(detailed_analysis['unmapped_players']) > 0:
        # Look for keywords: "unmapped", "sin mapear", "anónimos", "player"
        has_unmapped_mention = any(keyword in prompt.lower() for keyword in
                                  ['unmapped', 'sin mapear', 'anónimo', 'player', 'jugador'])
        if not has_unmapped_mention:
            issues.append("Hay jugadores sin mapear pero el prompt no los menciona")

    # Check 5: If there are patterns detected, prompt should mention them
    if detailed_analysis.get('patterns_detected') and len(detailed_analysis['patterns_detected']) > 0:
        has_pattern_mention = any(keyword in prompt.lower() for keyword in
                                 ['patrón', 'pattern', 'detectado'])
        if not has_pattern_mention:
            issues.append("Hay patrones detectados pero el prompt no los menciona")

    # Check 6: If there are priority issues, prompt should mention specific files/locations
    if detailed_analysis.get('priority_issues') and len(detailed_analysis['priority_issues']) > 0:
        # Check for file references like "file.py:123" or "file.py línea"
        import re
        has_file_references = re.search(r'\w+\.py:\d+', prompt) or 'línea' in prompt.lower()
        if not has_file_references:
            issues.append("Hay issues prioritarios pero el prompt no menciona archivos/líneas específicas")

    # Check 7: Prompt should have structure (sections with ##)
    if '##' not in prompt:
        issues.append("Prompt no tiene estructura (falta formato con ##)")

    # Validation passes if no issues or only minor issues
    valid = len(issues) == 0

    return {
        "valid": valid,
        "issues": issues,
        "quality_score": max(0, 100 - (len(issues) * 15))  # Each issue reduces score by 15%
    }


def _generate_fallback_prompt(context: dict, detailed_analysis: dict) -> str:
    """Generate a detailed prompt using analyzed debug data when Gemini is not available"""
    error_msg = context.get('error_message') or 'No hay mensaje de error explícito'
    stats = context.get('statistics', {})
    metrics = context.get('calculated_metrics', {})
    error_logs = context.get('error_logs', [])
    problem_indicators = context.get('problem_indicators', [])
    screenshot_summary = context.get('screenshot_summary', {})
    debug_json_path = context.get('debug_json_path', '')
    debug_json_filename = context.get('debug_json_filename', '')

    # Build detailed problem summary using analyzed data
    problems_detected = []

    if detailed_analysis.get('unmapped_players'):
        unmapped_count = len(detailed_analysis['unmapped_players'])
        tables_affected = len(set(p.get('table') for p in detailed_analysis['unmapped_players'] if p.get('table')))
        problems_detected.append(f"- **{unmapped_count} jugadores sin mapear** en {tables_affected} tablas diferentes")

    if detailed_analysis.get('patterns_detected'):
        for pattern in detailed_analysis['patterns_detected']:
            problems_detected.append(f"- **{pattern['pattern']}**: {pattern['description']} (Impacto: {pattern.get('impact', 'No especificado')})")

    if detailed_analysis.get('validation_errors'):
        validation_count = len(detailed_analysis['validation_errors'])
        problems_detected.append(f"- **{validation_count} errores de validación** en archivos de salida")

    if detailed_analysis.get('screenshot_failures'):
        failure_count = len(detailed_analysis['screenshot_failures'])
        problems_detected.append(f"- **{failure_count} screenshots fallidos** en OCR")

    # Identify main problem from priority issues
    main_problem = "Job completado con resultados subóptimos"

    if detailed_analysis.get('priority_issues') and len(detailed_analysis['priority_issues']) > 0:
        top_issue = detailed_analysis['priority_issues'][0]
        main_problem = f"{top_issue.get('problem', main_problem)} (Severidad: {top_issue.get('severity', 'unknown')})"
    elif 'JOB_FAILED' in problem_indicators:
        main_problem = f"Job falló: {error_msg}"
    elif 'VERY_LOW_MATCH_RATE' in problem_indicators:
        main_problem = f"Match rate muy bajo ({metrics.get('match_rate_percent', 0):.1f}%) - Problema de matching"
    elif 'LOW_MATCH_RATE' in problem_indicators:
        main_problem = f"Match rate bajo ({metrics.get('match_rate_percent', 0):.1f}%) - Revisar algoritmo de matching"
    elif 'LOW_OCR_SUCCESS' in problem_indicators:
        main_problem = f"OCR con baja tasa de éxito ({metrics.get('screenshot_success_rate_percent', 0):.1f}%)"

    prompt = f"""# Problema en GGRevealer - Job #{context.get('job_id')}

## IMPORTANTE: Lee el archivo de debug primero

**Antes de hacer cualquier análisis, lee el archivo JSON de debug completo:**
```
{debug_json_path}
```

Este archivo (`{debug_json_filename}`) contiene:
- Información completa del job
- Logs detallados (todos los niveles: DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Resultados de todos los screenshots con OCR y match counts
- Estadísticas completas
- Errores específicos de cada screenshot

Usa el comando Read para leer este archivo y obtener contexto completo antes de continuar.

---

## Problema Identificado
{main_problem}

## Métricas Clave
- **Match Rate:** {metrics.get('match_rate_percent', 0):.1f}% ({stats.get('matched_hands', 0)}/{stats.get('hands_parsed', 0)} manos)
- **OCR Success:** {metrics.get('screenshot_success_rate_percent', 0):.1f}% ({screenshot_summary.get('success', 0)}/{screenshot_summary.get('total', 0)} screenshots)
- **Archivos:** {stats.get('txt_files', 0)} TXT, {stats.get('screenshots', 0)} screenshots

## Problemas Específicos Detectados

{chr(10).join(problems_detected) if problems_detected else 'No se detectaron problemas específicos'}

"""

    # Add unmapped players details
    if detailed_analysis.get('unmapped_players'):
        prompt += f"\n### Jugadores Sin Mapear ({len(detailed_analysis['unmapped_players'])} total)\n\n"
        prompt += "Estos jugadores anónimos no pudieron ser identificados:\n\n"
        for i, player in enumerate(detailed_analysis['unmapped_players'][:10]):
            prompt += f"{i+1}. **ID:** `{player.get('player_id', 'N/A')}` | **Tabla:** `{player.get('table', 'N/A')}` | **Manos:** {player.get('hands_in_table', 'N/A')}\n"

        if len(detailed_analysis['unmapped_players']) > 10:
            prompt += f"\n...y {len(detailed_analysis['unmapped_players']) - 10} más (ver JSON completo)\n"
        prompt += "\n"

    # Add patterns detected details
    if detailed_analysis.get('patterns_detected'):
        prompt += f"\n### Patrones Detectados ({len(detailed_analysis['patterns_detected'])} total)\n\n"
        for pattern in detailed_analysis['patterns_detected']:
            prompt += f"**{pattern['pattern']}:**\n"
            prompt += f"- Descripción: {pattern.get('description', 'N/A')}\n"
            prompt += f"- Impacto: {pattern.get('impact', 'N/A')}\n"
            prompt += f"- Ubicación sugerida: `{pattern.get('location', 'N/A')}`\n\n"

    # Add priority issues with suggested fixes
    if detailed_analysis.get('priority_issues'):
        prompt += f"\n### Issues Priorizados ({len(detailed_analysis['priority_issues'])} total)\n\n"
        for i, issue in enumerate(detailed_analysis['priority_issues'][:5], 1):
            prompt += f"**{i}. [{issue.get('severity', 'UNKNOWN')}] {issue.get('problem', 'Sin descripción')}**\n"
            prompt += f"- Ubicación: `{issue.get('location', 'N/A')}`\n"
            if issue.get('suggested_fix'):
                prompt += f"- Solución sugerida: {issue.get('suggested_fix')}\n"
            if issue.get('evidence'):
                prompt += f"- Evidencia: {issue.get('evidence')}\n"
            prompt += "\n"

    # Add validation errors
    if detailed_analysis.get('validation_errors'):
        prompt += f"\n### Errores de Validación ({len(detailed_analysis['validation_errors'])} total)\n\n"
        for i, error in enumerate(detailed_analysis['validation_errors'][:5], 1):
            # Handle both string and dict formats
            if isinstance(error, str):
                prompt += f"{i}. {error}\n"
            else:
                prompt += f"{i}. **Archivo:** `{error.get('filename', 'N/A')}`\n"
                prompt += f"   - Validación fallida: {error.get('validation_failed', 'N/A')}\n"
                prompt += f"   - Detalles: {error.get('details', 'N/A')}\n"
            prompt += "\n"

    # Add screenshot failures
    if detailed_analysis.get('screenshot_failures'):
        prompt += f"\n### Screenshots Fallidos ({len(detailed_analysis['screenshot_failures'])} total)\n\n"
        for i, failure in enumerate(detailed_analysis['screenshot_failures'][:5], 1):
            # Handle both string and dict formats
            if isinstance(failure, str):
                prompt += f"{i}. {failure}\n\n"
            else:
                prompt += f"{i}. **Archivo:** `{failure.get('filename', 'N/A')}`\n"
                if 'error' in failure:
                    prompt += f"   - Error: {failure.get('error', 'N/A')}\n"
                if 'issue' in failure:
                    prompt += f"   - Issue: {failure.get('issue', 'N/A')}\n"
                if 'ocr_success' in failure:
                    prompt += f"   - Success: {failure.get('ocr_success', 'N/A')}\n"
                if 'matches_found' in failure:
                    prompt += f"   - Matches: {failure.get('matches_found', 'N/A')}\n"
                prompt += "\n"

    # Add critical logs
    if detailed_analysis.get('critical_logs'):
        prompt += f"\n### Logs Críticos ({len(detailed_analysis['critical_logs'])} total)\n\n"
        for log in detailed_analysis['critical_logs'][:5]:
            prompt += f"[{log.get('level', 'N/A')}] {log.get('message', 'Sin mensaje')}\n"
            if log.get('extra_data'):
                prompt += f"  Contexto: {json.dumps(log.get('extra_data'), indent=2, ensure_ascii=False)}\n"
            prompt += "\n"

    prompt += """
## Pasos de Debugging Sugeridos

1. **Lee el archivo JSON completo** para obtener contexto detallado
2. **Revisa las ubicaciones específicas** mencionadas en los patrones detectados
3. **Investiga los IDs sin mapear** - busca por qué no se encontraron matches
4. **Verifica los screenshots fallidos** - revisa si el OCR está funcionando correctamente
5. **Aplica las soluciones sugeridas** en los priority issues

**Archivos principales a revisar:**
- `main.py:740-1144` - Pipeline de procesamiento
- `matcher.py:37-76` - Algoritmo de matching
- `ocr.py:46-117` - Extracción de datos de screenshots
- `writer.py:174-282` - Generación de archivos de salida
"""

    return prompt


@app.post("/api/validate")
async def validate_hand_history(file: UploadFile = File(...)):
    """
    Validate a hand history file against PokerTracker 4 requirements

    This endpoint performs all 12 PT4 validations without processing the file.
    Supports multi-hand files (splits by triple newline and validates each hand separately).
    Useful for testing and debugging hand histories.

    Returns:
        JSON with validation results, including:
        - total_hands: number of hands in file
        - valid: whether PT4 would accept all hands
        - pt4_would_reject: whether PT4 would reject based on critical errors
        - hands_with_errors: number of hands with errors
        - hands_with_critical_errors: number of hands with critical errors
        - aggregated_errors: total errors across all hands
        - aggregated_warnings: total warnings across all hands
        - validation_summary: summary statistics
        - per_hand_results: detailed results for each hand
    """
    from validator import GGPokerHandHistoryValidator

    try:
        # Read file content
        content = await file.read()
        hand_history_text = content.decode('utf-8')

        # Create validator in permissive mode (only logs, doesn't reject)
        validator = GGPokerHandHistoryValidator(strict_mode=False)

        # Validate file (handles multi-hand files)
        file_results = validator.validate_file(hand_history_text)

        # Build response
        return {
            "success": True,
            "filename": file.filename,
            "total_hands": file_results['total_hands'],
            "valid": file_results['aggregated_errors'] == 0,
            "pt4_would_reject": file_results['pt4_would_reject'],
            "hands_with_errors": file_results['hands_with_errors'],
            "hands_with_warnings": file_results['hands_with_warnings'],
            "hands_valid": file_results['hands_valid'],
            "hands_with_critical_errors": file_results['hands_with_critical_errors'],
            "aggregated_errors": file_results['aggregated_errors'],
            "aggregated_warnings": file_results['aggregated_warnings'],
            "aggregated_critical": file_results['aggregated_critical'],
            "per_hand_results": file_results['per_hand_results']
        }

    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Expected UTF-8 text file.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")


@app.delete("/api/job/{job_id}")
async def delete_job_endpoint(job_id: int):
    """Delete a job and all its files"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_upload_path = UPLOADS_PATH / str(job_id)
    if job_upload_path.exists():
        shutil.rmtree(job_upload_path)
    
    job_output_path = OUTPUTS_PATH / str(job_id)
    if job_output_path.exists():
        shutil.rmtree(job_output_path)
    
    delete_job(job_id)
    
    return {"message": "Job deleted"}


def calculate_job_cost(ocr1_count: int, ocr2_count: int) -> float:
    """Calculate total API cost for a job based on OCR operations"""
    total_images = ocr1_count + ocr2_count
    return total_images * GEMINI_COST_PER_IMAGE


def run_processing_pipeline(job_id: int, api_key: str = None):
    """
    Execute the full processing pipeline for a job

    Args:
        job_id: Job ID to process
        api_key: Gemini API key (from user or fallback to env)
    """
    import time

    # Initialize logger for this job
    logger = get_job_logger(job_id)
    start_time = time.time()

    try:
        logger.info("🚀 Starting processing pipeline", job_id=job_id)

        # Mark job as started with timestamp
        mark_job_started(job_id)

        # Step 1: Load TXT files
        step_start = time.time()
        txt_files = get_job_files(job_id, 'txt')
        logger.info(f"📄 Found {len(txt_files)} TXT files",
                   count=len(txt_files),
                   duration_ms=int((time.time() - step_start) * 1000))

        # Step 2: Parse hands
        step_start = time.time()
        all_hands = []
        for i, txt_file in enumerate(txt_files, 1):
            file_start = time.time()
            content = Path(txt_file['file_path']).read_text(encoding='utf-8')
            hands = GGPokerParser.parse_file(content)
            all_hands.extend(hands)
            logger.debug(f"Parsed file {i}/{len(txt_files)}: {txt_file['filename']}",
                        file_num=i,
                        filename=txt_file['filename'],
                        hands_found=len(hands),
                        duration_ms=int((time.time() - file_start) * 1000))

        logger.info(f"✅ Parsed {len(all_hands)} hands from {len(txt_files)} files",
                   total_hands=len(all_hands),
                   total_files=len(txt_files),
                   duration_ms=int((time.time() - step_start) * 1000))

        if len(all_hands) == 0:
            logger.error("❌ No hands could be parsed from TXT files")
            raise Exception("No hands could be parsed")

        # Step 3: Load screenshots
        step_start = time.time()
        screenshot_files = get_job_files(job_id, 'screenshot')
        logger.info(f"🖼️  Found {len(screenshot_files)} screenshots",
                   count=len(screenshot_files),
                   duration_ms=int((time.time() - step_start) * 1000))
        
        # Set total count for progress tracking
        set_ocr_total_count(job_id, len(screenshot_files))

        # Step 4: Dual OCR - Phase 1 (Hand ID Extraction)
        logger.info(f"🔍 Phase 1: OCR1 - Extracting Hand IDs from {len(screenshot_files)} screenshots",
                   screenshot_count=len(screenshot_files),
                   max_concurrent=10)
        step_start = time.time()

        # Use provided API key or fallback to environment
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

        # Get API tier from job and configure rate limiting
        job = get_job(job_id)
        api_tier = job.get('api_tier', 'free') if job else 'free'

        if api_tier == 'free':
            # Free tier: 14 requests per minute (1 concurrent, 4.3s delay between requests)
            semaphore_limit = 1
            delay_between_requests = 60 / 14  # ~4.3 seconds
            logger.info("🔒 Free tier API detected - Rate limiting: 14 req/min (4.3s delay)")
        else:
            # Paid tier: No limits (10 concurrent requests)
            semaphore_limit = 10
            delay_between_requests = 0
            logger.info("⚡ Paid tier API detected - No rate limiting (10 concurrent)")

        # Semaphore will be created inside the unified event loop to avoid cross-loop binding
        semaphore = None

        # OCR1: Extract Hand IDs from ALL screenshots
        ocr1_results = {}  # {screenshot_filename: (success, hand_id, error)}

        async def process_ocr1(screenshot_file):
            """Run OCR1 (Hand ID extraction) with retry"""
            async with semaphore:
                screenshot_filename = screenshot_file['filename']
                screenshot_path = screenshot_file['file_path']

                success, hand_id, error = await ocr_hand_id_with_retry(
                    screenshot_path, screenshot_filename, job_id, api_key, logger
                )
                ocr1_results[screenshot_filename] = (success, hand_id, error)
                increment_ocr_processed_count(job_id)

                # Rate limiting for free tier
                if delay_between_requests > 0:
                    await asyncio.sleep(delay_between_requests)

                return success

        async def process_ocr2(screenshot_file, screenshot_filename):
            """Run OCR2 (player details extraction)"""
            async with semaphore:
                screenshot_path = screenshot_file['file_path']

                success, ocr_data, error = await ocr_player_details(screenshot_path, api_key)
                save_ocr2_result(job_id, screenshot_filename, success, ocr_data, error)
                ocr2_results[screenshot_filename] = (success, ocr_data, error)

                if success:
                    logger.debug(f"✅ OCR2 successful: {screenshot_filename}",
                               screenshot=screenshot_filename,
                               players_count=len(ocr_data.get('players', [])))
                else:
                    logger.error(f"❌ OCR2 failed: {screenshot_filename}",
                               screenshot=screenshot_filename,
                               error=error)

                # Rate limiting for free tier
                if delay_between_requests > 0:
                    await asyncio.sleep(delay_between_requests)

                return success

        async def run_all_ocr_phases():
            """Run OCR1 and OCR2 in unified event loop"""
            nonlocal semaphore, ocr1_results, ocr2_results

            # Create semaphore once for both phases
            semaphore = asyncio.Semaphore(semaphore_limit)

            # Phase 1: OCR1 - Hand ID extraction
            logger.info(f"🔍 Phase 2: OCR1 - Extracting hand IDs from {len(screenshot_files)} screenshots")
            ocr1_tasks = [process_ocr1(sf) for sf in screenshot_files]
            await asyncio.gather(*ocr1_tasks)

            # OCR1 results are now populated
            ocr1_success_count = sum(1 for s, _, _ in ocr1_results.values() if s)
            ocr1_duration = int((time.time() - step_start) * 1000)
            logger.info(f"✅ OCR1 completed: {ocr1_success_count}/{len(screenshot_files)} successful",
                       success_count=ocr1_success_count,
                       total_count=len(screenshot_files),
                       failed_count=len(screenshot_files) - ocr1_success_count,
                       duration_ms=ocr1_duration)

            # Step 5: Match by Hand ID
            logger.info("🔗 Phase 2: Matching screenshots to hands by Hand ID")
            match_start = time.time()

            matched_screenshots = {}  # {screenshot_filename: hand}
            unmatched_screenshots = []

            for screenshot_filename, (success, hand_id, error) in ocr1_results.items():
                if not success:
                    unmatched_screenshots.append((screenshot_filename, error))
                    continue

                # Find hand with matching Hand ID (use fuzzy matching)
                matched_hand = None
                for hand in all_hands:
                    if _normalize_hand_id(hand.hand_id) == _normalize_hand_id(hand_id):
                        matched_hand = hand
                        break

                if matched_hand:
                    matched_screenshots[screenshot_filename] = matched_hand
                    logger.debug(f"✅ Matched: {screenshot_filename} → Hand {hand_id}",
                               screenshot=screenshot_filename,
                               hand_id=hand_id)
                else:
                    unmatched_screenshots.append((screenshot_filename, f"No hand found for Hand ID {hand_id}"))
                    logger.warning(f"⚠️  No match: {screenshot_filename} (Hand ID: {hand_id})",
                                 screenshot=screenshot_filename,
                                 hand_id=hand_id)

            match_duration = int((time.time() - match_start) * 1000)
            logger.info(f"✅ Matched {len(matched_screenshots)}/{len(screenshot_files)} screenshots",
                       matched_count=len(matched_screenshots),
                       total_count=len(screenshot_files),
                       unmatched_count=len(unmatched_screenshots),
                       duration_ms=match_duration)

            # Step 6: Discard unmatched screenshots
            logger.info(f"🗑️  Phase 3: Discarding {len(unmatched_screenshots)} unmatched screenshots")
            discard_start = time.time()

            for screenshot_filename, reason in unmatched_screenshots:
                mark_screenshot_discarded(job_id, screenshot_filename, reason)
                logger.warning(f"Discarded: {screenshot_filename} - {reason}",
                             screenshot=screenshot_filename,
                             reason=reason)

            discard_duration = int((time.time() - discard_start) * 1000)
            logger.info(f"✅ Discarded {len(unmatched_screenshots)} screenshots",
                       discarded_count=len(unmatched_screenshots),
                       duration_ms=discard_duration)

            # Phase 2: OCR2 - Player details extraction (only on matched screenshots)
            logger.info(f"🔍 Phase 4: OCR2 - Extracting player details from {len(matched_screenshots)} matched screenshots")
            ocr2_start = time.time()

            ocr2_tasks = []
            for screenshot_file in screenshot_files:
                screenshot_filename = screenshot_file['filename']
                if screenshot_filename in matched_screenshots:
                    ocr2_tasks.append(process_ocr2(screenshot_file, screenshot_filename))

            await asyncio.gather(*ocr2_tasks)

            ocr2_success_count = sum(1 for s, _, _ in ocr2_results.values() if s)
            ocr2_duration = int((time.time() - ocr2_start) * 1000)
            logger.info(f"✅ OCR2 completed: {ocr2_success_count}/{len(matched_screenshots)} successful",
                       success_count=ocr2_success_count,
                       total_count=len(matched_screenshots),
                       failed_count=len(matched_screenshots) - ocr2_success_count,
                       duration_ms=ocr2_duration)

            return matched_screenshots, unmatched_screenshots

        # SINGLE event loop call for both OCR phases
        logger.info("🔄 Running OCR phases in unified event loop")
        ocr2_results = {}  # {screenshot_filename: (success, ocr_data, error)}
        matched_screenshots, unmatched_screenshots = asyncio.run(run_all_ocr_phases())

        # Step 8: Generate name mappings (Phase 2 - Table-wide approach)
        # NEW: Group by table → Aggregate mappings → Apply to ALL hands of that table
        logger.info("🗂️  Phase 5: Generating table-wide name mappings")
        step_start = time.time()

        # Step 8.1: Group hands by table
        table_groups = _group_hands_by_table(all_hands)
        logger.info(f"📊 Grouped {len(all_hands)} hands into {len(table_groups)} tables",
                   total_hands=len(all_hands),
                   table_count=len(table_groups),
                   table_names=list(table_groups.keys()))

        # Step 8.2: Build aggregated mapping per table
        table_mappings = {}  # Dict[table_name, Dict[anon_id, real_name]]
        total_mappings = 0

        for table_name, table_hands in table_groups.items():
            logger.info(f"🔨 Building mapping for table '{table_name}' ({len(table_hands)} hands)",
                       table=table_name,
                       hands_count=len(table_hands))

            mapping = _build_table_mapping(
                table_name=table_name,
                hands=table_hands,
                matched_screenshots=matched_screenshots,
                ocr2_results=ocr2_results,
                logger=logger
            )

            table_mappings[table_name] = mapping
            total_mappings += len(mapping)

            logger.info(f"✅ Table '{table_name}': Generated {len(mapping)} mappings",
                       table=table_name,
                       mapping_count=len(mapping))

        # Step 8.3: Convert table mappings to flat list of NameMapping objects for writer
        # The writer expects List[NameMapping], but we'll aggregate all mappings from all tables
        name_mappings = []
        for table_name, mapping in table_mappings.items():
            for anon_id, real_name in mapping.items():
                name_mappings.append(NameMapping(
                    anonymized_identifier=anon_id,
                    resolved_name=real_name,
                    source='auto-match',
                    confidence=99.0,  # High confidence from role-based matching
                    locked=False
                ))

        # Update screenshot results with match counts (1 match per matched screenshot)
        for screenshot_filename in matched_screenshots.keys():
            update_screenshot_result_matches(
                job_id=job_id,
                screenshot_filename=screenshot_filename,
                matches_found=1,
                status="success"
            )

        mapping_duration = int((time.time() - step_start) * 1000)
        logger.info(f"✅ Generated {len(name_mappings)} total name mappings from {len(table_mappings)} tables",
                   mappings_count=len(name_mappings),
                   tables_count=len(table_mappings),
                   duration_ms=mapping_duration)

        # Step 9: Calculate detailed metrics
        logger.info("📊 Phase 6: Calculating detailed metrics")
        step_start = time.time()

        detailed_metrics = _calculate_detailed_metrics(
            all_hands=all_hands,
            table_groups=table_groups,
            table_mappings=table_mappings,
            ocr1_results=ocr1_results,
            ocr2_results=ocr2_results,
            matched_screenshots=matched_screenshots,
            unmatched_screenshots=unmatched_screenshots
        )

        # Log key metrics
        logger.info(f"📈 Hands: {detailed_metrics['hands']['total']} total, "
                   f"{detailed_metrics['hands']['fully_mapped']} fully mapped "
                   f"({detailed_metrics['hands']['coverage_percentage']:.1f}%)",
                   hands_total=detailed_metrics['hands']['total'],
                   hands_fully_mapped=detailed_metrics['hands']['fully_mapped'],
                   hands_coverage=detailed_metrics['hands']['coverage_percentage'])

        logger.info(f"📈 Players: {detailed_metrics['players']['total_unique']} unique, "
                   f"{detailed_metrics['players']['mapped']} mapped "
                   f"({detailed_metrics['players']['mapping_rate']:.1f}%)",
                   players_total=detailed_metrics['players']['total_unique'],
                   players_mapped=detailed_metrics['players']['mapped'],
                   players_mapping_rate=detailed_metrics['players']['mapping_rate'])

        logger.info(f"📈 Tables: {detailed_metrics['tables']['total']} total, "
                   f"{detailed_metrics['tables']['fully_resolved']} fully resolved "
                   f"({detailed_metrics['tables']['resolution_rate']:.1f}%)",
                   tables_total=detailed_metrics['tables']['total'],
                   tables_fully_resolved=detailed_metrics['tables']['fully_resolved'],
                   tables_resolution_rate=detailed_metrics['tables']['resolution_rate'])

        logger.info(f"📈 Screenshots: {detailed_metrics['screenshots']['total']} total, "
                   f"{detailed_metrics['screenshots']['ocr1_success']} OCR1 success, "
                   f"{detailed_metrics['screenshots']['matched']} matched",
                   screenshots_total=detailed_metrics['screenshots']['total'],
                   screenshots_ocr1_success=detailed_metrics['screenshots']['ocr1_success'],
                   screenshots_matched=detailed_metrics['screenshots']['matched'])

        metrics_duration = int((time.time() - step_start) * 1000)
        logger.info(f"✅ Metrics calculated",
                   duration_ms=metrics_duration)

        # Step 7: Generate output files
        step_start = time.time()
        logger.info("📝 Generating output TXT files by table")

        # Generate separate TXT files by table with validation info (ALL HANDS, not just matched)
        txt_files_info = generate_txt_files_with_validation(all_hands, name_mappings)

        gen_duration = int((time.time() - step_start) * 1000)
        logger.info(f"✅ Generated {len(txt_files_info)} table files",
                   table_count=len(txt_files_info),
                   total_hands=len(all_hands),
                   duration_ms=gen_duration)
        
        # Step 8: Validate and write files
        step_start = time.time()
        logger.info("✍️  Validating and writing output files to disk")

        # Create output directory
        job_output_path = OUTPUTS_PATH / str(job_id)
        job_output_path.mkdir(exist_ok=True)

        # Validate all files and write them
        validation_errors_all = []
        validation_warnings_all = []
        successful_files = []
        failed_files = []
        all_unmapped_ids = set()

        for table_name, file_info in txt_files_info.items():
            final_txt = file_info['content']
            total_hands = file_info['total_hands']
            unmapped_ids = file_info['unmapped_ids']
            has_unmapped = file_info['has_unmapped']
            
            # Track all unmapped IDs across all files
            all_unmapped_ids.update(unmapped_ids)
            
            # Get original txt for this table to validate
            table_hands_raw = [h.raw_text for h in all_hands if table_name in h.raw_text or 'Unknown' in table_name]
            original_txt = '\n\n'.join(table_hands_raw)
            
            validation = validate_output_format(original_txt, final_txt)
            if not validation.valid:
                validation_errors_all.extend(validation.errors)
            validation_warnings_all.extend(validation.warnings)
            
            # Determine filename suffix based on unmapped IDs
            if has_unmapped:
                filename_suffix = "_fallado"
                failed_files.append({
                    'table': table_name,
                    'total_hands': total_hands,
                    'unmapped_ids': unmapped_ids
                })
            else:
                filename_suffix = "_resolved"
                successful_files.append({
                    'table': table_name,
                    'total_hands': total_hands
                })
            
            # Write individual TXT file with appropriate suffix
            txt_path = job_output_path / f"{table_name}{filename_suffix}.txt"
            txt_path.write_text(final_txt, encoding='utf-8')

            logger.debug(f"Wrote {table_name}{filename_suffix}.txt",
                        table=table_name,
                        suffix=filename_suffix,
                        hands=total_hands,
                        unmapped_ids_count=len(unmapped_ids),
                        has_unmapped=has_unmapped)

        write_duration = int((time.time() - step_start) * 1000)
        logger.info(f"✅ Validated and wrote {len(txt_files_info)} files",
                   total_files=len(txt_files_info),
                   successful=len(successful_files),
                   failed=len(failed_files),
                   validation_errors=len(validation_errors_all),
                   validation_warnings=len(validation_warnings_all),
                   duration_ms=write_duration)

        # Step 9: Create ZIP files
        step_start = time.time()
        logger.info("📦 Creating ZIP archives")

        # Create ZIP file for successful files
        zip_path = None
        if successful_files:
            zip_path = job_output_path / "resolved_hands.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for txt_file in job_output_path.glob("*_resolved.txt"):
                    zipf.write(txt_file, txt_file.name)
            logger.info(f"✅ Created resolved_hands.zip",
                       files_count=len(successful_files),
                       zip_path=str(zip_path))

        # Create ZIP file for failed files
        zip_path_failed = None
        if failed_files:
            zip_path_failed = job_output_path / "fallidos.zip"
            with zipfile.ZipFile(zip_path_failed, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for txt_file in job_output_path.glob("*_fallado.txt"):
                    zipf.write(txt_file, txt_file.name)
            logger.info(f"⚠️  Created fallidos.zip",
                       files_count=len(failed_files),
                       zip_path=str(zip_path_failed))

        zip_duration = int((time.time() - step_start) * 1000)
        logger.info(f"✅ ZIP archives created",
                   duration_ms=zip_duration)
        
        # Get screenshot results for stats
        screenshot_results = get_screenshot_results(job_id)
        screenshots_by_status = {'success': 0, 'warning': 0, 'error': 0}
        for sr in screenshot_results:
            status = sr.get('status', 'error')
            screenshots_by_status[status] = screenshots_by_status.get(status, 0) + 1
        
        # Use unmapped IDs from file analysis (more accurate than validation warnings)
        unmapped_players = sorted(list(all_unmapped_ids))
        
        # Get list of table names processed
        tables_processed = list(txt_files_info.keys())
        
        stats = {
            'total_hands': len(all_hands),
            'matched_hands': len(matched_screenshots),  # Number of screenshots matched to hands
            'mappings_count': len(name_mappings),
            'validation_passed': len(validation_errors_all) == 0,
            'validation_errors': validation_errors_all,
            'validation_warnings': validation_warnings_all,
            'screenshots_total': len(screenshot_files),
            'screenshots_success': screenshots_by_status.get('success', 0),
            'screenshots_warning': screenshots_by_status.get('warning', 0),
            'screenshots_error': screenshots_by_status.get('error', 0),
            'unmapped_players': unmapped_players,
            'unmapped_players_count': len(unmapped_players),
            'tables_processed': tables_processed,
            'tables_count': len(tables_processed),
            'successful_files': successful_files,
            'failed_files': failed_files,
            'successful_files_count': len(successful_files),
            'failed_files_count': len(failed_files),
            'has_failed_files': len(failed_files) > 0,
            # Add detailed metrics from comprehensive calculation
            'detailed_metrics': detailed_metrics
        }
        
        mappings_dict = [
            {
                'anonymized_identifier': m.anonymized_identifier,
                'resolved_name': m.resolved_name,
                'source': m.source,
                'confidence': m.confidence
            }
            for m in name_mappings
        ]
        
        # Save result with both ZIP paths
        output_path = str(zip_path) if zip_path else (str(zip_path_failed) if zip_path_failed else "")
        save_result(job_id, output_path, mappings_dict, stats)
        
        # Update job statistics and processing time
        update_job_stats(
            job_id,
            matched_hands=len(matched_screenshots),
            name_mappings_count=len(name_mappings),
            hands_parsed=len(all_hands)
        )

        # Update detailed metrics in database
        update_job_detailed_metrics(job_id, detailed_metrics)

        # Calculate and update API costs
        ocr1_count = len(screenshot_files)  # OCR1 runs on ALL screenshots
        ocr2_count = len(matched_screenshots)  # OCR2 runs only on matched screenshots
        total_cost = calculate_job_cost(ocr1_count, ocr2_count)
        update_job_cost(job_id, ocr1_count, ocr2_count, total_cost)

        logger.info(f"💰 API costs calculated",
                   ocr1_images=ocr1_count,
                   ocr2_images=ocr2_count,
                   total_images=ocr1_count + ocr2_count,
                   total_cost_usd=round(total_cost, 6))

        update_job_status(job_id, 'completed')

        # Final summary
        total_duration = int((time.time() - start_time) * 1000)
        logger.info(f"🎉 Processing completed successfully",
                   total_duration_ms=total_duration,
                   total_duration_sec=round(total_duration / 1000, 2),
                   total_hands=len(all_hands),
                   matched_screenshots=len(matched_screenshots),
                   name_mappings=len(name_mappings),
                   successful_files=len(successful_files),
                   failed_files=len(failed_files))

        # Persist logs to database
        logger.flush_to_db()

        # Auto-export debug JSON for analysis
        try:
            debug_export = _export_debug_json(job_id)
            if debug_export:
                logger.info(f"📋 Debug JSON exported automatically: {debug_export['filename']}")
                print(f"[JOB {job_id}] 📋 Debug JSON exported: {debug_export['filepath']}")
        except Exception as e:
            logger.warning(f"Failed to export debug JSON: {str(e)}")

    except Exception as error:
        total_duration = int((time.time() - start_time) * 1000)
        logger.critical(f"❌ Processing failed: {str(error)}",
                       error=str(error),
                       error_type=type(error).__name__,
                       total_duration_ms=total_duration)

        # Persist logs to database even on failure
        logger.flush_to_db()

        update_job_status(job_id, 'failed', str(error))

        # Auto-export debug JSON for analysis (especially important on failure)
        try:
            debug_export = _export_debug_json(job_id)
            if debug_export:
                logger.info(f"📋 Debug JSON exported automatically: {debug_export['filename']}")
                print(f"[JOB {job_id}] 📋 Debug JSON exported: {debug_export['filepath']}")
        except Exception as e:
            logger.warning(f"Failed to export debug JSON: {str(e)}")


def _calculate_detailed_metrics(
    all_hands: List[ParsedHand],
    table_groups: dict,
    table_mappings: dict,
    ocr1_results: dict,
    ocr2_results: dict,
    matched_screenshots: dict,
    unmatched_screenshots: list
) -> dict:
    """
    Calculate comprehensive metrics for the dual OCR pipeline.

    Args:
        all_hands: All parsed hands
        table_groups: Dict[table_name, List[ParsedHand]]
        table_mappings: Dict[table_name, Dict[anon_id, real_name]]
        ocr1_results: Dict[screenshot_filename, (success, hand_id, error)]
        ocr2_results: Dict[screenshot_filename, (success, ocr_data, error)]
        matched_screenshots: Dict[screenshot_filename, hand]
        unmatched_screenshots: List[(screenshot_filename, reason)]

    Returns:
        dict with detailed metrics at multiple levels:
        - hands: hand-level statistics
        - players: player-level statistics
        - tables: table-level statistics
        - screenshots: screenshot-level statistics
        - mappings: mapping-level statistics
    """

    # ======================================================================
    # 1. HAND-LEVEL METRICS
    # ======================================================================

    total_hands = len(all_hands)

    # Count hands with at least one mapping
    hands_with_mappings = set()
    hands_fully_mapped = []
    hands_partially_mapped = []
    hands_no_mappings = []

    for table_name, hands in table_groups.items():
        mapping = table_mappings.get(table_name, {})

        for hand in hands:
            # Get all unique anonymous IDs in this hand
            anon_ids = set(seat.player_id for seat in hand.seats if seat.player_id != 'Hero')

            if not anon_ids:
                # No anonymous IDs to map (e.g., all players are Hero?)
                hands_fully_mapped.append(hand.hand_id)
                continue

            # Count how many are mapped
            mapped_ids = sum(1 for anon_id in anon_ids if anon_id in mapping)

            if mapped_ids > 0:
                hands_with_mappings.add(hand.hand_id)

            if mapped_ids == len(anon_ids):
                hands_fully_mapped.append(hand.hand_id)
            elif mapped_ids > 0:
                hands_partially_mapped.append(hand.hand_id)
            else:
                hands_no_mappings.append(hand.hand_id)

    hands_metrics = {
        'total': total_hands,
        'fully_mapped': len(hands_fully_mapped),
        'partially_mapped': len(hands_partially_mapped),
        'no_mappings': len(hands_no_mappings),
        'coverage_percentage': round((len(hands_fully_mapped) / total_hands * 100) if total_hands > 0 else 0, 1)
    }

    # ======================================================================
    # 2. PLAYER-LEVEL METRICS
    # ======================================================================

    # Collect all unique anonymous IDs across all hands
    all_anon_ids = set()
    for hand in all_hands:
        for seat in hand.seats:
            if seat.player_id != 'Hero':
                all_anon_ids.add(seat.player_id)

    # Count mapped players (aggregate from all table mappings)
    all_mapped_ids = set()
    for mapping in table_mappings.values():
        all_mapped_ids.update(mapping.keys())

    # Only count mapped anonymized IDs (exclude Hero from mapped count)
    # This ensures mapping_rate = (mapped_anon_ids / total_anon_ids) stays <= 100%
    mapped_anon_ids = all_mapped_ids & all_anon_ids

    unmapped_ids = all_anon_ids - all_mapped_ids

    # Calculate average players per table
    players_per_table = []
    for hands in table_groups.values():
        if hands:
            # Get unique players for this table
            table_players = set()
            for hand in hands:
                for seat in hand.seats:
                    table_players.add(seat.player_id)
            players_per_table.append(len(table_players))

    avg_players_per_table = round(sum(players_per_table) / len(players_per_table), 1) if players_per_table else 0

    players_metrics = {
        'total_unique': len(all_anon_ids),
        'mapped': len(mapped_anon_ids),  # Changed: only count anonymized IDs (exclude Hero)
        'unmapped': len(unmapped_ids),
        'mapping_rate': round((len(mapped_anon_ids) / len(all_anon_ids) * 100) if all_anon_ids else 0, 1),  # Changed: use mapped_anon_ids
        'average_per_table': avg_players_per_table
    }

    # ======================================================================
    # 3. TABLE-LEVEL METRICS
    # ======================================================================

    total_tables = len(table_groups)
    tables_fully_resolved = []
    tables_partially_resolved = []
    tables_failed = []

    for table_name, hands in table_groups.items():
        mapping = table_mappings.get(table_name, {})

        # Get all unique anonymous IDs for this table
        table_anon_ids = set()
        for hand in hands:
            for seat in hand.seats:
                if seat.player_id != 'Hero':
                    table_anon_ids.add(seat.player_id)

        if not table_anon_ids:
            # No anonymous IDs to map
            tables_fully_resolved.append(table_name)
            continue

        # Calculate coverage
        mapped_count = sum(1 for anon_id in table_anon_ids if anon_id in mapping)
        coverage = (mapped_count / len(table_anon_ids) * 100) if table_anon_ids else 0

        if coverage == 100:
            tables_fully_resolved.append(table_name)
        elif coverage >= 50:
            tables_partially_resolved.append(table_name)
        else:
            tables_failed.append(table_name)

    tables_metrics = {
        'total': total_tables,
        'fully_resolved': len(tables_fully_resolved),
        'partially_resolved': len(tables_partially_resolved),
        'failed': len(tables_failed),
        'resolution_rate': round((len(tables_fully_resolved) / total_tables * 100) if total_tables > 0 else 0, 1),
        'average_coverage': round(
            ((len(tables_fully_resolved) * 100 + len(tables_partially_resolved) * 75) / total_tables) if total_tables > 0 else 0,
            1
        )
    }

    # ======================================================================
    # 4. SCREENSHOT-LEVEL METRICS
    # ======================================================================

    total_screenshots = len(ocr1_results)
    ocr1_success = sum(1 for success, _, _ in ocr1_results.values() if success)
    ocr1_failure = total_screenshots - ocr1_success

    # OCR1 retry count (from ocr1_results - we count retries in ocr_hand_id_with_retry)
    # Note: Current implementation doesn't track individual retry counts,
    # but we can infer from success/failure
    ocr1_retry_count = 0  # Placeholder - would need to be tracked in ocr_hand_id_with_retry

    ocr2_success = sum(1 for success, _, _ in ocr2_results.values() if success)
    ocr2_failure = len(ocr2_results) - ocr2_success

    screenshots_discarded = len(unmatched_screenshots)
    screenshots_matched = len(matched_screenshots)

    screenshots_metrics = {
        'total': total_screenshots,
        'ocr1_success': ocr1_success,
        'ocr1_failure': ocr1_failure,
        'ocr1_retry_count': ocr1_retry_count,
        'ocr1_success_rate': round((ocr1_success / total_screenshots * 100) if total_screenshots > 0 else 0, 1),
        'ocr2_success': ocr2_success,
        'ocr2_failure': ocr2_failure,
        'ocr2_success_rate': round((ocr2_success / len(ocr2_results) * 100) if ocr2_results else 0, 1),
        'matched': screenshots_matched,
        'discarded': screenshots_discarded,
        'match_rate': round((screenshots_matched / total_screenshots * 100) if total_screenshots > 0 else 0, 1)
    }

    # ======================================================================
    # 5. MAPPING-LEVEL METRICS
    # ======================================================================

    # Count total mappings
    total_mappings = sum(len(mapping) for mapping in table_mappings.values())

    # Count role-based vs visual position mappings
    # Note: Current implementation doesn't distinguish between these in the mapping dict
    # Both are stored the same way. We could track this if we added metadata to mappings.
    # For now, we'll use heuristics based on OCR2 data

    role_based_count = 0
    visual_position_count = 0

    for screenshot_filename, (success, ocr_data, error) in ocr2_results.items():
        if success and ocr_data:
            # If OCR2 extracted role indicators, mappings from this screenshot are role-based
            has_dealer = ocr_data.get('dealer_player') is not None
            has_sb = ocr_data.get('small_blind_player') is not None
            has_bb = ocr_data.get('big_blind_player') is not None

            if has_dealer or has_sb or has_bb:
                # Estimate: each screenshot contributes ~3 players on average
                role_based_count += len(ocr_data.get('players', []))
            else:
                # Fallback to visual position mapping
                visual_position_count += len(ocr_data.get('players', []))

    # Conflicts detected (would need to be tracked in _build_table_mapping)
    # For now, we can't track this without modifying the mapping function
    conflicts_detected = 0
    tables_rejected = 0

    mappings_metrics = {
        'total': total_mappings,
        'role_based': role_based_count,
        'visual_position': visual_position_count,
        'conflicts_detected': conflicts_detected,
        'tables_rejected': tables_rejected
    }

    # ======================================================================
    # RETURN AGGREGATED METRICS
    # ======================================================================

    return {
        'hands': hands_metrics,
        'players': players_metrics,
        'tables': tables_metrics,
        'screenshots': screenshots_metrics,
        'mappings': mappings_metrics
    }


def _normalize_table_name(table_name: str) -> str:
    """
    Normalize table names for comparison.
    Maps all unknown table variants to 'Unknown' for consistent matching.

    Args:
        table_name: Original table name (e.g., "Cartney", "Unknown", "unknown_table_1")

    Returns:
        Normalized table name ("Unknown" for all unknown variants, original name otherwise)

    Example:
        _normalize_table_name("Unknown") → "Unknown"
        _normalize_table_name("unknown_table_1") → "Unknown"
        _normalize_table_name("unknown_table_42") → "Unknown"
        _normalize_table_name("Cartney") → "Cartney"
    """
    if table_name == "Unknown" or table_name.startswith("unknown_table_"):
        return "Unknown"
    return table_name


def _group_hands_by_table(parsed_hands: List[ParsedHand]) -> dict[str, List[ParsedHand]]:
    """
    Group parsed hands by table name.

    Args:
        parsed_hands: List of ParsedHand objects

    Returns:
        Dict[table_name, List[ParsedHand]]
    """
    from collections import defaultdict

    tables = defaultdict(list)
    unknown_counter = 1

    for hand in parsed_hands:
        # Extract table name from raw text
        table_name = extract_table_name(hand.raw_text)

        # Fallback for unknown tables
        if table_name == "Unknown":
            table_name = f"unknown_table_{unknown_counter}"
            unknown_counter += 1

        tables[table_name].append(hand)

    return dict(tables)


def _table_matches(hand_table_name: str, group_table_name: str) -> bool:
    """
    Check if two table names refer to the same table.
    Handles unknown_table_N pattern correctly.

    Args:
        hand_table_name: Table name from hand history
        group_table_name: Table name from grouping (e.g., 'unknown_table_1')

    Returns:
        True if tables match, False otherwise

    Example:
        _table_matches('unknown_table_1', 'unknown_table_1') → True
        _table_matches('unknown_table_1', 'unknown_table_2') → False
        _table_matches('RealTable', 'RealTable') → True
        _table_matches('RealTable', 'unknown_table_1') → False
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


def _build_table_mapping(
    table_name: str,
    hands: List[ParsedHand],
    matched_screenshots: dict[str, ParsedHand],
    ocr2_results: dict[str, tuple],
    logger
) -> dict[str, str]:
    """
    Build aggregated name mapping for entire table from all matched screenshots.

    This is the CRITICAL change for Phase 2:
    - OLD: Map per-hand (only players in matched hand)
    - NEW: Map per-table (ALL players visible in ANY screenshot for this table)

    Args:
        table_name: Name of the table
        hands: All hands for this table
        matched_screenshots: Dict[screenshot_filename, matched_hand]
        ocr2_results: Dict[screenshot_filename, (success, ocr_data, error)]
        logger: Job logger

    Returns:
        Dict[anonymized_id, real_name] - Aggregated for entire table
    """
    aggregated_mapping = {}
    conflict_tracker = {}  # Track {anon_id: [real_names]} to detect conflicts
    screenshots_for_table = []

    # Step 1: Find all screenshots that match ANY hand in this table
    for screenshot_filename, matched_hand in matched_screenshots.items():
        # Check if this screenshot matches a hand from this table
        # CRITICAL FIX (Issue #2): Use _table_matches for consistent unknown table handling
        hand_table_name = extract_table_name(matched_hand.raw_text)
        if _table_matches(hand_table_name, table_name):
            screenshots_for_table.append((screenshot_filename, matched_hand))

    logger.info(f"📊 Table '{table_name}': {len(hands)} hands, {len(screenshots_for_table)} matched screenshots",
                table=table_name,
                hands_count=len(hands),
                screenshots_count=len(screenshots_for_table))

    # Step 2: Extract role-based mappings from each matched screenshot
    for screenshot_filename, matched_hand in screenshots_for_table:
        # Get OCR2 data for this screenshot
        if screenshot_filename not in ocr2_results:
            logger.warning(f"No OCR2 data for {screenshot_filename}",
                         screenshot=screenshot_filename)
            continue

        success, ocr_data, error = ocr2_results[screenshot_filename]

        # FIX: Parse JSON string to dict if ocr_data is stored as string
        if isinstance(ocr_data, str):
            import json
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

        if not success:
            logger.warning(f"OCR2 failed for {screenshot_filename}: {error}",
                         screenshot=screenshot_filename,
                         error=error)
            continue

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

        # Build screenshot analysis object
        from models import ScreenshotAnalysis, PlayerStack

        # Build player stacks from separate lists
        players_list = ocr_data.get('players', [])
        stacks_list = ocr_data.get('stacks', [])
        positions_list = ocr_data.get('positions', [])

        # Calculate SB/BB from dealer position (NEW LOGIC)
        dealer_player = ocr_data.get('roles', {}).get('dealer')
        small_blind_player = None
        big_blind_player = None

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
            # Find dealer index in players list
            dealer_index = players_list.index(dealer_player)
            total_players = len(players_list)

            # Calculate SB and BB positions (clockwise from dealer)
            # In 3-max: Dealer → SB → BB (clockwise order)
            sb_index = (dealer_index + 1) % total_players
            bb_index = (dealer_index + 2) % total_players

            small_blind_player = players_list[sb_index]
            big_blind_player = players_list[bb_index]

            logger.debug(
                f"✓ Calculated blinds from dealer",
                screenshot=screenshot_filename,
                table=table_name,
                dealer=dealer_player,
                sb=small_blind_player,
                bb=big_blind_player
            )

        # Ensure all lists have the same length
        min_length = min(len(players_list), len(stacks_list), len(positions_list)) if positions_list else len(players_list)

        all_player_stacks = [
            PlayerStack(
                player_name=players_list[i],
                stack=stacks_list[i] if i < len(stacks_list) else 0.0,
                position=positions_list[i] if i < len(positions_list) and positions_list[i] is not None else i+1
            ) for i in range(min_length)
        ]

        screenshot = ScreenshotAnalysis(
            screenshot_id=screenshot_filename,
            hand_id=ocr_data.get('hand_id'),
            dealer_player=dealer_player,
            small_blind_player=small_blind_player,
            big_blind_player=big_blind_player,
            all_player_stacks=all_player_stacks
        )

        # Use role-based mapping to get mapping for this screenshot
        screenshot_mapping = _build_seat_mapping_by_roles(screenshot, matched_hand, logger)

        if not screenshot_mapping:
            logger.warning(f"Failed to build mapping for {screenshot_filename}",
                         screenshot=screenshot_filename,
                         hand_id=matched_hand.hand_id)
            continue

        logger.debug(f"Screenshot {screenshot_filename} contributed {len(screenshot_mapping)} mappings",
                    screenshot=screenshot_filename,
                    mapping_count=len(screenshot_mapping),
                    mapping=screenshot_mapping)

        # Step 3: Merge mapping into aggregated mapping
        for anon_id, real_name in screenshot_mapping.items():
            # Track all names seen for this anon_id
            if anon_id not in conflict_tracker:
                conflict_tracker[anon_id] = []
            conflict_tracker[anon_id].append(real_name)

            # Add to aggregated mapping (first occurrence wins)
            if anon_id not in aggregated_mapping:
                aggregated_mapping[anon_id] = real_name
                logger.debug(f"Added mapping: {anon_id} → {real_name}",
                           anon_id=anon_id,
                           real_name=real_name)

    # Step 4: Detect conflicts (same anon_id → different real names)
    conflicts_found = False
    for anon_id, names in conflict_tracker.items():
        unique_names = set(names)
        if len(unique_names) > 1:
            logger.error(f"CONFLICT: {anon_id} mapped to multiple names: {unique_names}",
                       anon_id=anon_id,
                       conflicting_names=list(unique_names),
                       table=table_name)
            conflicts_found = True

    # CRITICAL FIX (Issue #1): Reject table if conflicts exist
    if conflicts_found:
        conflict_count = sum(1 for names in conflict_tracker.values() if len(set(names)) > 1)
        logger.error(
            f"❌ Table '{table_name}': REJECTED due to mapping conflicts",
            table=table_name,
            conflict_count=conflict_count
        )
        return {}  # Return empty mapping to fail the table

    # Step 5: Calculate statistics
    unique_players = set()
    for hand in hands:
        for seat in hand.seats:
            unique_players.add(seat.player_id)

    mapped_players = len(aggregated_mapping)
    total_players = len(unique_players)
    coverage = (mapped_players / total_players * 100) if total_players > 0 else 0

    unmapped_players = unique_players - set(aggregated_mapping.keys())

    logger.info(f"✅ Table '{table_name}' mapping: {mapped_players}/{total_players} players mapped ({coverage:.1f}% coverage)",
                table=table_name,
                mapped_players=mapped_players,
                total_players=total_players,
                coverage_pct=coverage,
                conflicts=conflicts_found)

    if unmapped_players:
        logger.warning(f"⚠️  Table '{table_name}': Unmapped players: {list(unmapped_players)}",
                     table=table_name,
                     unmapped_count=len(unmapped_players),
                     unmapped_ids=list(unmapped_players))

    return aggregated_mapping


def _normalize_hand_id(hand_id: str) -> str:
    """
    Normalize Hand ID for fuzzy matching (remove prefixes)

    Args:
        hand_id: Original Hand ID (e.g., "SG3247423387", "RC1234567890")

    Returns:
        Normalized ID without prefix (e.g., "3247423387", "1234567890")
    """
    import re
    # Remove common prefixes: SG, RC, OM, MT, TT, HD, HH
    normalized = re.sub(r'^(SG|RC|OM|MT|TT|HD|HH)', '', hand_id, flags=re.IGNORECASE)
    return normalized.strip()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
