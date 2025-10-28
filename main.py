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


@app.post("/api/debug/{job_id}/export")
async def export_debug_info(job_id: int):
    """Export debug information to JSON file in storage/debug/"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

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
        "success": True,
        "message": f"Debug info exported to {filename}",
        "filepath": str(filepath),
        "filename": filename,
        "data": debug_info
    }


@app.post("/api/debug/{job_id}/generate-prompt")
async def generate_claude_prompt(job_id: int):
    """Generate a Claude Code debugging prompt using Gemini AI"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

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
        "screenshot_summary": screenshot_summary
    }

    # If job has result with detailed stats, include them
    if result and result.get('stats'):
        context["result_stats"] = result['stats']

    # Configure Gemini
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key or api_key == 'your_gemini_api_key_here':
        # Fallback: generate simple prompt without AI
        return {
            "success": False,
            "message": "GEMINI_API_KEY not configured",
            "prompt": _generate_fallback_prompt(context)
        }

    try:
        genai.configure(api_key=api_key)
        # Use Gemini 2.5 Flash with thinking mode for better debugging analysis
        model = genai.GenerativeModel('gemini-2.5-flash')

        # Create prompt for Gemini
        gemini_prompt = f"""Eres un experto en debugging de aplicaciones Python, análisis de errores y detección de problemas en pipelines de procesamiento de datos.

Tu tarea es analizar la información de un job de GGRevealer y generar un prompt ÚTIL y ACCIONABLE para Claude Code.

**CONTEXTO DE GGREVEALER:**
GGRevealer es una aplicación FastAPI que desanonimiza hand histories de poker usando OCR con Gemini Vision:
- Pipeline: Upload → Parse TXT → OCR Screenshots → Match Hands → Generate Mappings → Write Outputs
- El objetivo es HACER MATCH de manos con screenshots para identificar jugadores anónimos
- Un BUEN resultado tiene >80% match rate (manos matched / manos parseadas)
- Un MAL resultado tiene <30% match rate

**INFORMACIÓN DEL JOB A ANALIZAR:**

{json.dumps(context, indent=2, ensure_ascii=False)}

**INDICADORES DE PROBLEMAS DETECTADOS:**
{', '.join(problem_indicators) if problem_indicators else 'Ninguno detectado automáticamente'}

**TU ANÁLISIS DEBE IDENTIFICAR:**

1. **¿Cuál es el problema REAL?**
   - Si match_rate es bajo (<30%): El problema es en el MATCHING (matcher.py o calidad de screenshots)
   - Si OCR success rate es bajo: El problema es en OCR (ocr.py o calidad de imágenes)
   - Si hay error_message: Analiza el error específico
   - Si no hay errores pero resultados malos: Identifica qué métrica está mal

2. **¿Por qué está fallando?**
   - Analiza error_logs para patrones
   - Revisa failed_screenshots para errores comunes
   - Considera warning_logs si son relevantes

3. **¿Dónde buscar?**
   - main.py (líneas 400-800): Pipeline y OCR paralelo
   - matcher.py: Algoritmo de matching (Hand ID, scoring)
   - ocr.py: Llamadas a Gemini Vision
   - parser.py: Parsing de TXT files

**GENERA UN PROMPT que:**

1. **Identifique el problema de forma ESPECÍFICA** (no genérico)
   - Ejemplo BUENO: "Match rate de 3.4% indica que el algoritmo de matching no está funcionando"
   - Ejemplo MALO: "Hay un error en el procesamiento"

2. **Proporcione MÉTRICAS CLAVE**
   - Match rate, OCR success rate, screenshots procesados
   - Comparar con lo esperado

3. **Liste ERRORES ESPECÍFICOS** (si los hay)
   - Con nombre de archivo, línea si es posible
   - Patrones detectados

4. **Sugiera ARCHIVOS Y FUNCIONES CONCRETAS** a revisar
   - No solo "revisa matcher.py" sino "revisa la función find_best_matches() en matcher.py:37"

5. **Proponga PASOS CONCRETOS de debugging**
   - Qué logs revisar, qué agregar, qué cambiar

6. **Sea ACCIONABLE**
   - Claude Code debe poder empezar a trabajar inmediatamente

**FORMATO:**
Usa markdown, secciones claras, bullets. Máximo 400 palabras. ENFÓCATE en lo más importante.

**IMPORTANTE:**
- NO generes prompt genérico si el problema es obvio (ej: match rate bajo = problema de matching)
- Si no hay errores explícitos, ANALIZA las métricas y encuentra el problema real
- Sé ESPECÍFICO y TÉCNICO

Genera SOLO el prompt para Claude Code:"""

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

        return {
            "success": True,
            "prompt": generated_prompt,
            "context": context
        }

    except Exception as e:
        print(f"Error calling Gemini for prompt generation: {e}")
        return {
            "success": False,
            "message": f"Error generating prompt: {str(e)}",
            "prompt": _generate_fallback_prompt(context)
        }


def _generate_fallback_prompt(context: dict) -> str:
    """Generate a basic prompt when Gemini is not available"""
    error_msg = context.get('error_message') or 'No hay mensaje de error explícito'
    stats = context.get('statistics', {})
    metrics = context.get('calculated_metrics', {})
    error_logs = context.get('error_logs', [])
    problem_indicators = context.get('problem_indicators', [])
    screenshot_summary = context.get('screenshot_summary', {})

    # Identify main problem
    main_problem = "Job completado con resultados subóptimos"

    if 'JOB_FAILED' in problem_indicators:
        main_problem = f"Job falló: {error_msg}"
    elif 'VERY_LOW_MATCH_RATE' in problem_indicators:
        main_problem = f"Match rate muy bajo ({metrics.get('match_rate_percent', 0):.1f}%) - Problema de matching"
    elif 'LOW_MATCH_RATE' in problem_indicators:
        main_problem = f"Match rate bajo ({metrics.get('match_rate_percent', 0):.1f}%) - Revisar algoritmo de matching"
    elif 'LOW_OCR_SUCCESS' in problem_indicators:
        main_problem = f"OCR con baja tasa de éxito ({metrics.get('screenshot_success_rate_percent', 0):.1f}%)"

    prompt = f"""# Problema en GGRevealer - Job #{context.get('job_id')}

## Problema Identificado
{main_problem}

## Métricas Clave
- **Match Rate:** {metrics.get('match_rate_percent', 0):.1f}% ({stats.get('matched_hands', 0)}/{stats.get('hands_parsed', 0)} manos)
- **OCR Success:** {metrics.get('screenshot_success_rate_percent', 0):.1f}% ({screenshot_summary.get('success', 0)}/{screenshot_summary.get('total', 0)} screenshots)
- **Archivos:** {stats.get('txt_files', 0)} TXT, {stats.get('screenshots', 0)} screenshots

## Análisis

"""

    # Add specific analysis based on problem
    if metrics.get('match_rate_percent', 0) < 30:
        prompt += """### Problema: Match Rate Bajo
El problema principal es que muy pocas manos están siendo matched con screenshots.

**Posibles causas:**
1. Hand IDs no coinciden entre TXT y screenshots
2. Algoritmo de scoring en matcher.py no funciona bien
3. Screenshots de calidad pobre o formato diferente
4. OCR no extrae Hand IDs correctamente

**Archivos a revisar:**
- `matcher.py:37-76` - Función find_best_matches()
- `ocr.py:46-117` - Extracción de Hand ID
- Logs de matching para ver scores

"""

    if screenshot_summary.get('error', 0) > 0:
        prompt += f"""### Screenshots Fallidos: {screenshot_summary.get('error', 0)}
Hay screenshots que fallaron en OCR. Revisa los errores específicos.

"""

    if error_logs:
        prompt += "## Logs de Error\n"
        for log in error_logs[:5]:
            prompt += f"\n[{log.get('level')}] {log.get('message')}"
            if log.get('extra_data'):
                prompt += f"\n  Extra: {json.dumps(log.get('extra_data'))}"
        prompt += "\n"

    prompt += """
## Pasos de Debugging

1. Revisa los logs del job en la sección de debugging
2. Verifica qué está retornando el OCR (Hand IDs, player names)
3. Chequea el algoritmo de matching y sus scores
4. Exporta el debug JSON para análisis detallado

**Archivos principales:** main.py, parser.py, ocr.py, matcher.py, writer.py"""

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

    except Exception as error:
        total_duration = int((time.time() - start_time) * 1000)
        logger.critical(f"❌ Processing failed: {str(error)}",
                       error=str(error),
                       error_type=type(error).__name__,
                       total_duration_ms=total_duration)

        # Persist logs to database even on failure
        logger.flush_to_db()

        update_job_status(job_id, 'failed', str(error))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
