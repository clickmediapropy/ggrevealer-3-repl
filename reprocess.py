"""
Reprocessing pipeline for failed files
"""

import asyncio
import json
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from logger import get_job_logger
from database import (
    get_db, get_job, update_pt4_failed_file_screenshots,
    get_job_files, save_result, get_result
)
# TODO: Import update_reprocess_attempt once implemented in Task 6
from parser import GGPokerParser
from ocr import ocr_hand_id, ocr_player_details
from matcher import find_best_matches, _build_seat_mapping_by_roles
from writer import generate_txt_files_with_validation
from models import NameMapping

STORAGE_PATH = Path("storage")
UPLOADS_PATH = STORAGE_PATH / "uploads"
OUTPUTS_PATH = STORAGE_PATH / "outputs"

# Stub function until Task 6 is implemented
def update_reprocess_attempt(attempt_id: int, status: str, logs: Optional[str] = None, error_message: Optional[str] = None):
    """Placeholder - will be moved to database.py in Task 6"""
    pass


async def run_reprocess_pipeline(
    job_id: int,
    attempt_ids: List[int],
    files: List[dict]
) -> None:
    """
    Reprocess failed files through full pipeline

    Execution:
    1. For each file: Load TXT, run OCR1+OCR2, match, generate output
    2. Update reprocess_attempts with status and logs
    3. Update pt4_failed_files.reprocess_count
    4. Regenerate output ZIPs

    Args:
        job_id: Job ID being reprocessed
        attempt_ids: List of reprocess_attempts.id values
        files: List of file specs [{"source": "pt4", "id": X}, ...]
    """
    logger = get_job_logger(job_id)
    logger.info(f"Starting reprocess pipeline for {len(files)} files")

    job = get_job(job_id)
    if not job:
        logger.error(f"Job {job_id} not found")
        return

    # Get screenshots for this job
    screenshots_path = UPLOADS_PATH / str(job_id) / "screenshots"
    screenshot_files = list(screenshots_path.glob("*.png")) if screenshots_path.exists() else []
    logger.info(f"Found {len(screenshot_files)} screenshots")

    # Get TXT files for this job
    txt_path = UPLOADS_PATH / str(job_id) / "txt"
    txt_files = list(txt_path.glob("*.txt")) if txt_path.exists() else []
    logger.info(f"Found {len(txt_files)} TXT files")

    try:
        # Update all attempts to 'processing'
        for attempt_id in attempt_ids:
            update_reprocess_attempt(attempt_id, 'processing')

        # For now, placeholder that marks all as success
        # TODO: Implement full OCR + matching + generation pipeline

        for attempt_id in attempt_ids:
            logs = "[REPROCESS] Placeholder implementation - full pipeline TBD"
            update_reprocess_attempt(attempt_id, 'success', logs=logs)
            logger.info(f"Attempt {attempt_id} marked success (placeholder)")

        logger.info("Reprocess pipeline completed")

    except Exception as e:
        logger.error(f"Reprocess pipeline failed: {str(e)}", exc_info=True)
        for attempt_id in attempt_ids:
            update_reprocess_attempt(
                attempt_id,
                'failed',
                error_message=f"Pipeline error: {str(e)}"
            )
