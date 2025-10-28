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
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import List
import shutil

from database import init_db, create_job, get_job, get_all_jobs, update_job_status, add_file, get_job_files, save_result, get_result, update_job_file_counts, delete_job, mark_job_started, update_job_stats, set_ocr_total_count, increment_ocr_processed_count, save_screenshot_result, get_screenshot_results, update_screenshot_result_matches, get_job_logs, clear_job_results
from parser import GGPokerParser
from ocr import ocr_screenshot
from matcher import find_best_matches
from writer import generate_txt_files_by_table, generate_txt_files_with_validation, validate_output_format
from models import NameMapping
from logger import get_job_logger
import google.generativeai as genai

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
    screenshots: List[UploadFile] = File(...)
):
    """Upload TXT files and screenshots for a new job"""
    job_id = create_job()
    
    job_upload_path = UPLOADS_PATH / str(job_id)
    job_upload_path.mkdir(exist_ok=True)
    
    txt_path = job_upload_path / "txt"
    screenshots_path = job_upload_path / "screenshots"
    txt_path.mkdir(exist_ok=True)
    screenshots_path.mkdir(exist_ok=True)
    
    for txt_file in txt_files:
        file_path = txt_path / txt_file.filename
        with open(file_path, "wb") as f:
            shutil.copyfileobj(txt_file.file, f)
        add_file(job_id, txt_file.filename, "txt", str(file_path))
    
    for screenshot in screenshots:
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
async def process_job(job_id: int, background_tasks: BackgroundTasks):
    """Start processing a job in the background (supports reprocessing)"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job['status'] == 'processing':
        raise HTTPException(status_code=400, detail="Job is already processing")

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

    background_tasks.add_task(run_processing_pipeline, job_id)
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
        }
    }
    
    # Add detailed result stats if completed
    if job['status'] == 'completed':
        result = get_result(job_id)
        if result and result.get('stats'):
            response['detailed_stats'] = result['stats']
            
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


def _export_debug_json(job_id: int) -> dict:
    """
    Helper function to export debug information to JSON file
    Returns dict with filepath, filename, and debug_info
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
    result = debug_data.get('result', {})
    stats = result.get('stats', {})

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
            "impact": "Impide el mapping de jugadores (counter-clockwise algorithm necesita hero_position)",
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
        genai.configure(api_key=api_key)
        # Use Gemini 2.5 Flash with thinking mode for better debugging analysis
        model = genai.GenerativeModel('gemini-2.5-flash')

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

        # Call Gemini
        response = await asyncio.to_thread(
            model.generate_content,
            gemini_prompt,
            generation_config={
                "temperature": 0.3,  # Low temperature for consistent, focused output
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
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


def run_processing_pipeline(job_id: int):
    """Execute the full processing pipeline for a job"""
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

        # Step 4: Process screenshots with OCR
        logger.info(f"🔍 Starting OCR processing for {len(screenshot_files)} screenshots",
                   screenshot_count=len(screenshot_files),
                   max_concurrent=10)
        step_start = time.time()

        # Process screenshots in parallel with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests

        async def process_single_screenshot(screenshot_file):
            """Process one screenshot and update progress, save results"""
            filename = screenshot_file['filename']
            ocr_success = False
            ocr_error = None
            ocr_data = None
            status = "error"
            
            ocr_start = time.time()
            try:
                result = await ocr_screenshot(
                    screenshot_file['file_path'],
                    filename,
                    semaphore
                )
                ocr_success = True
                ocr_data = result
                status = "success"

                ocr_duration = int((time.time() - ocr_start) * 1000)
                logger.debug(f"✅ OCR successful: {filename}",
                           filename=filename,
                           hand_id=result.hand_id if result else None,
                           duration_ms=ocr_duration)

                # Save initial screenshot result (matches will be updated later)
                # Convert ScreenshotAnalysis dataclass to dict for JSON serialization
                save_screenshot_result(
                    job_id=job_id,
                    screenshot_filename=filename,
                    ocr_success=True,
                    ocr_data=asdict(result),  # Convert dataclass to dict
                    matches_found=0,  # Will be updated after matching
                    status="pending_match"
                )

                increment_ocr_processed_count(job_id)
                return result

            except Exception as e:
                ocr_error = str(e)
                status = "error"
                ocr_duration = int((time.time() - ocr_start) * 1000)

                logger.error(f"❌ OCR failed: {filename}",
                           filename=filename,
                           error=ocr_error,
                           duration_ms=ocr_duration)

                # Save failed screenshot result
                save_screenshot_result(
                    job_id=job_id,
                    screenshot_filename=filename,
                    ocr_success=False,
                    ocr_error=ocr_error,
                    matches_found=0,
                    status="error"
                )

                increment_ocr_processed_count(job_id)
                return None
        
        async def process_all_screenshots():
            tasks = [
                process_single_screenshot(screenshot_file)
                for screenshot_file in screenshot_files
            ]
            return await asyncio.gather(*tasks)
        
        ocr_results_raw = asyncio.run(process_all_screenshots())
        ocr_results = [r for r in ocr_results_raw if r is not None]

        ocr_duration = int((time.time() - step_start) * 1000)
        logger.info(f"✅ OCR completed: {len(ocr_results)}/{len(screenshot_files)} screenshots analyzed",
                   success_count=len(ocr_results),
                   total_count=len(screenshot_files),
                   failed_count=len(screenshot_files) - len(ocr_results),
                   duration_ms=ocr_duration)

        if len(ocr_results) == 0:
            logger.error("❌ No screenshots could be analyzed")
            raise Exception("No screenshots could be analyzed")

        # Step 5: Match hands with screenshots
        step_start = time.time()
        logger.info(f"🔗 Starting hand matching (threshold: 50)",
                   hands_count=len(all_hands),
                   screenshots_count=len(ocr_results))

        matches = find_best_matches(all_hands, ocr_results, confidence_threshold=50)

        match_duration = int((time.time() - step_start) * 1000)
        logger.info(f"✅ Found {len(matches)} matches",
                   matches_count=len(matches),
                   hands_count=len(all_hands),
                   match_rate=round(len(matches) / len(all_hands) * 100, 1) if len(all_hands) > 0 else 0,
                   duration_ms=match_duration)
        
        # Track matches per screenshot
        screenshot_match_count = {}
        for match in matches:
            screenshot_name = match.screenshot_id  # Use screenshot_id from HandMatch
            screenshot_match_count[screenshot_name] = screenshot_match_count.get(screenshot_name, 0) + 1
        
        # Update screenshot results with match counts
        for ocr_result in ocr_results:
            screenshot_name = ocr_result.screenshot_id  # Use screenshot_id from ScreenshotAnalysis dataclass
            match_count = screenshot_match_count.get(screenshot_name, 0)
            status = "success" if match_count > 0 else "warning"
            update_screenshot_result_matches(
                job_id=job_id,
                screenshot_filename=screenshot_name,
                matches_found=match_count,
                status=status
            )
        
        # Step 6: Generate name mappings
        step_start = time.time()
        logger.info("🏷️  Generating name mappings from matches")

        name_mappings = []
        matched_hand_ids = set()

        for match in matches:
            matched_hand_ids.add(match.hand_id)
            if match.auto_mapping:
                for anon_id, real_name in match.auto_mapping.items():
                    existing = next((m for m in name_mappings if m.anonymized_identifier == anon_id), None)
                    if not existing:
                        name_mappings.append(NameMapping(
                            anonymized_identifier=anon_id,
                            resolved_name=real_name,
                            source='auto-match',
                            confidence=match.confidence,
                            locked=False
                        ))

        mapping_duration = int((time.time() - step_start) * 1000)
        logger.info(f"✅ Generated {len(name_mappings)} name mappings",
                   mappings_count=len(name_mappings),
                   unique_players=len(set(m.resolved_name for m in name_mappings)),
                   duration_ms=mapping_duration)

        matched_hands = [hand for hand in all_hands if hand.hand_id in matched_hand_ids]

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
            'matched_hands': len(matched_hands),
            'mappings_count': len(name_mappings),
            'high_confidence_matches': sum(1 for m in matches if m.confidence >= 80),
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
            'has_failed_files': len(failed_files) > 0
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
            matched_hands=len(matched_hands),
            name_mappings_count=len(name_mappings),
            hands_parsed=len(all_hands)
        )
        
        update_job_status(job_id, 'completed')

        # Final summary
        total_duration = int((time.time() - start_time) * 1000)
        logger.info(f"🎉 Processing completed successfully",
                   total_duration_ms=total_duration,
                   total_duration_sec=round(total_duration / 1000, 2),
                   total_hands=len(all_hands),
                   matched_hands=len(matched_hands),
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
