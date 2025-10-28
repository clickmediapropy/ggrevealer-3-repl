"""
FastAPI application entry point
"""

import os
import asyncio
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

from database import init_db, create_job, get_job, get_all_jobs, update_job_status, add_file, get_job_files, save_result, get_result, update_job_file_counts, delete_job, mark_job_started, update_job_stats, set_ocr_total_count, increment_ocr_processed_count, save_screenshot_result, get_screenshot_results, update_screenshot_result_matches
from parser import GGPokerParser
from ocr import ocr_screenshot
from matcher import find_best_matches
from writer import generate_txt_files_by_table, validate_output_format
from models import NameMapping

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

UPLOADS_PATH.mkdir(parents=True, exist_ok=True)
OUTPUTS_PATH.mkdir(parents=True, exist_ok=True)

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
    """Start processing a job in the background"""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job['status'] == 'processing':
        raise HTTPException(status_code=400, detail="Job is already processing")
    
    background_tasks.add_task(run_processing_pipeline, job_id)
    update_job_status(job_id, 'processing')
    
    return {"job_id": job_id, "status": "processing"}


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
    """Download the processed ZIP file for a job"""
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
    try:
        print(f"[JOB {job_id}] Starting processing...")
        
        # Mark job as started with timestamp
        mark_job_started(job_id)
        
        txt_files = get_job_files(job_id, 'txt')
        print(f"[JOB {job_id}] Found {len(txt_files)} TXT files")
        
        all_hands = []
        for txt_file in txt_files:
            content = Path(txt_file['file_path']).read_text(encoding='utf-8')
            hands = GGPokerParser.parse_file(content)
            all_hands.extend(hands)
        
        print(f"[JOB {job_id}] Parsed {len(all_hands)} hands")
        
        if len(all_hands) == 0:
            raise Exception("No hands could be parsed")
        
        screenshot_files = get_job_files(job_id, 'screenshot')
        print(f"[JOB {job_id}] Found {len(screenshot_files)} screenshots")
        
        # Set total count for progress tracking
        set_ocr_total_count(job_id, len(screenshot_files))
        
        # Process screenshots in parallel with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests
        
        async def process_single_screenshot(screenshot_file):
            """Process one screenshot and update progress, save results"""
            filename = screenshot_file['filename']
            ocr_success = False
            ocr_error = None
            ocr_data = None
            status = "error"
            
            try:
                result = await ocr_screenshot(
                    screenshot_file['file_path'],
                    filename,
                    semaphore
                )
                ocr_success = True
                ocr_data = result
                status = "success"
                
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
                print(f"[JOB {job_id}] ❌ OCR failed for {filename}: {ocr_error}")
                return None
        
        async def process_all_screenshots():
            tasks = [
                process_single_screenshot(screenshot_file)
                for screenshot_file in screenshot_files
            ]
            return await asyncio.gather(*tasks)
        
        ocr_results_raw = asyncio.run(process_all_screenshots())
        ocr_results = [r for r in ocr_results_raw if r is not None]
        
        print(f"[JOB {job_id}] OCR completed: {len(ocr_results)} screenshots analyzed")
        
        if len(ocr_results) == 0:
            raise Exception("No screenshots could be analyzed")
        
        matches = find_best_matches(all_hands, ocr_results, confidence_threshold=50)
        print(f"[JOB {job_id}] Found {len(matches)} matches")
        
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
        
        print(f"[JOB {job_id}] Generated {len(name_mappings)} name mappings")
        
        matched_hands = [hand for hand in all_hands if hand.hand_id in matched_hand_ids]
        
        # Generate separate TXT files by table
        txt_files_by_table = generate_txt_files_by_table(matched_hands, name_mappings)
        
        print(f"[JOB {job_id}] Generated {len(txt_files_by_table)} table files")
        
        # Create output directory
        job_output_path = OUTPUTS_PATH / str(job_id)
        job_output_path.mkdir(exist_ok=True)
        
        # Validate all files and write them
        validation_errors_all = []
        validation_warnings_all = []
        
        for table_name, final_txt in txt_files_by_table.items():
            # Get original txt for this table to validate
            table_hands_raw = [h.raw_text for h in matched_hands if table_name in h.raw_text or 'Unknown' in table_name]
            original_txt = '\n\n'.join(table_hands_raw)
            
            validation = validate_output_format(original_txt, final_txt)
            if not validation.valid:
                validation_errors_all.extend(validation.errors)
            validation_warnings_all.extend(validation.warnings)
            
            # Write individual TXT file
            txt_path = job_output_path / f"{table_name}_resolved.txt"
            txt_path.write_text(final_txt, encoding='utf-8')
            print(f"[JOB {job_id}] ✓ Wrote {table_name}_resolved.txt")
        
        # Create ZIP file with all TXT files
        zip_path = job_output_path / "resolved_hands.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for txt_file in job_output_path.glob("*_resolved.txt"):
                zipf.write(txt_file, txt_file.name)
        
        print(f"[JOB {job_id}] ✓ Created ZIP with {len(txt_files_by_table)} files")
        
        # Get screenshot results for stats
        screenshot_results = get_screenshot_results(job_id)
        screenshots_by_status = {'success': 0, 'warning': 0, 'error': 0}
        for sr in screenshot_results:
            status = sr.get('status', 'error')
            screenshots_by_status[status] = screenshots_by_status.get(status, 0) + 1
        
        # Extract unmapped players from validation warnings
        unmapped_players = []
        for warning in validation_warnings_all:
            if 'unmapped anonymous IDs' in warning:
                # Extract IDs from warning message
                parts = warning.split(':')
                if len(parts) > 1:
                    ids_part = parts[1].split('.')[0]
                    unmapped_players = [id.strip() for id in ids_part.split(',')]
                break
        
        # Get list of table names processed
        tables_processed = list(txt_files_by_table.keys())
        
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
            'tables_count': len(tables_processed)
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
        
        save_result(job_id, str(zip_path), mappings_dict, stats)
        
        # Update job statistics and processing time
        update_job_stats(
            job_id,
            matched_hands=len(matched_hands),
            name_mappings_count=len(name_mappings),
            hands_parsed=len(all_hands)
        )
        
        update_job_status(job_id, 'completed')
        
        print(f"[JOB {job_id}] ✅ Processing completed successfully")
        
    except Exception as error:
        print(f"[JOB {job_id}] ❌ Processing failed: {error}")
        update_job_status(job_id, 'failed', str(error))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
