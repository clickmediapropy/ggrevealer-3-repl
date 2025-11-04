"""
Smart matcher for PT4 failed files to original GGRevealer jobs
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from pathlib import Path
import json

from database import get_files_by_table_number, get_job_outputs_path


@dataclass
class FailedFileMatch:
    """Match result for a PT4 failed file"""
    filename: str
    table_number: Optional[int]
    error_count: int
    errors: List[str]
    matched_job_id: Optional[int]
    original_txt_path: Optional[str]
    processed_txt_path: Optional[str]
    screenshot_paths: List[str]


def match_failed_files_to_jobs(failed_files: List[Dict]) -> List[FailedFileMatch]:
    """
    Match PT4 failed files to original GGRevealer jobs

    Strategy:
    1. Extract table number from failed filename (e.g., 46798_resolved.txt → 46798)
    2. Search database for files matching that table number
    3. Find original TXT input (46798.txt)
    4. Find processed output (46798_resolved.txt in outputs/)
    5. Find all screenshots containing that table number

    Args:
        failed_files: List of dicts from PT4 parser

    Returns:
        List of FailedFileMatch objects with matched paths
    """
    matches = []

    for failed_file in failed_files:
        filename = failed_file['filename']
        table_number = failed_file['table_number']
        error_count = failed_file['error_count']
        errors = failed_file['errors']

        # Initialize match with no associations
        match = FailedFileMatch(
            filename=filename,
            table_number=table_number,
            error_count=error_count,
            errors=errors,
            matched_job_id=None,
            original_txt_path=None,
            processed_txt_path=None,
            screenshot_paths=[]
        )

        # If no table number, can't match
        if table_number is None:
            matches.append(match)
            continue

        # Search for files with this table number
        files = get_files_by_table_number(table_number)

        if not files:
            matches.append(match)
            continue

        # Group files by job_id (prefer most recent job)
        job_files = {}
        for file in files:
            job_id = file['job_id']
            if job_id not in job_files:
                job_files[job_id] = []
            job_files[job_id].append(file)

        # Use most recent job (highest job_id)
        most_recent_job_id = max(job_files.keys())
        job_file_list = job_files[most_recent_job_id]

        # Extract paths
        match.matched_job_id = most_recent_job_id

        # Find original TXT (input)
        for file in job_file_list:
            if file['file_type'] == 'txt' and f"{table_number}.txt" in file['filename']:
                match.original_txt_path = file['file_path']
                break

        # Find processed TXT (output)
        outputs_path = get_job_outputs_path(most_recent_job_id)
        if outputs_path:
            processed_path = Path(outputs_path) / f"{table_number}_resolved.txt"
            if processed_path.exists():
                match.processed_txt_path = str(processed_path)
            else:
                # Try fallado version
                fallado_path = Path(outputs_path) / f"{table_number}_fallado.txt"
                if fallado_path.exists():
                    match.processed_txt_path = str(fallado_path)

        # Find screenshots
        for file in job_file_list:
            if file['file_type'] == 'screenshot' and str(table_number) in file['filename']:
                match.screenshot_paths.append(file['file_path'])

        matches.append(match)

    return matches
