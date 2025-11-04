"""
Smart matcher for PT4 failed files to original GGRevealer jobs
"""

from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from pathlib import Path
import json
import re

from database import get_files_by_table_number, get_job_outputs_path, get_job_files


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


def _extract_hand_ids_from_txt(txt_path: str) -> Set[str]:
    r"""
    Extract all hand IDs from a TXT file

    Hand IDs are typically formatted as: SG3247289962, MT123456, etc.
    Regex pattern: Poker Hand #(\S+):

    Args:
        txt_path: Path to TXT file

    Returns:
        Set of unique hand IDs found in the file
    """
    try:
        with open(txt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        hand_ids = set()
        hand_id_pattern = r'Poker Hand #(\S+):'
        for match in re.finditer(hand_id_pattern, content):
            full_hand_id = match.group(1)
            hand_ids.add(full_hand_id)

            # Also add version without prefix for matching flexibility
            hand_id_without_prefix = re.sub(r'^(SG|HH|MT|TT)', '', full_hand_id)
            if hand_id_without_prefix != full_hand_id:
                hand_ids.add(hand_id_without_prefix)

        return hand_ids
    except Exception as e:
        print(f"Error extracting hand IDs from {txt_path}: {e}")
        return set()


def match_failed_files_to_jobs(failed_files: List[Dict], preferred_job_id: Optional[int] = None) -> List[FailedFileMatch]:
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
        preferred_job_id: Optional job ID to prefer when multiple jobs have same table

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

        # Group files by job_id
        job_files = {}
        for file in files:
            job_id = file['job_id']
            if job_id not in job_files:
                job_files[job_id] = []
            job_files[job_id].append(file)

        # Select job: prefer user-specified job_id, fallback to most recent
        if preferred_job_id and preferred_job_id in job_files:
            selected_job_id = preferred_job_id
        else:
            # Use most recent job (highest job_id)
            selected_job_id = max(job_files.keys())

        # Get ALL files for this job (not just those matching table number)
        # This is important for hand-ID-based matching where screenshots
        # may not have table number in the filename
        job_file_list = get_job_files(selected_job_id)

        # Extract paths
        match.matched_job_id = selected_job_id

        # Find original TXT (input)
        # Match files that contain the table number in the filename
        # Examples: "46798.txt", "GG... - 4374643746 - ... .txt"
        for file in job_file_list:
            if file['file_type'] == 'txt' and str(table_number) in file['filename']:
                match.original_txt_path = file['file_path']
                break

        # Find processed TXT (output)
        outputs_path = get_job_outputs_path(selected_job_id)
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
        # Strategy: First try to match by hand ID, then fallback to table number

        # Step 1: Extract hand IDs from the original TXT file
        hand_ids = set()
        if match.original_txt_path:
            hand_ids = _extract_hand_ids_from_txt(match.original_txt_path)

        # Step 2: Try to find screenshots matching hand IDs
        found_by_hand_id = False
        if hand_ids:
            for file in job_file_list:
                if file['file_type'] == 'screenshot':
                    filename = file['filename'].lower()
                    # Check if any hand ID appears in screenshot filename
                    for hand_id in hand_ids:
                        if hand_id.lower() in filename:
                            match.screenshot_paths.append(file['file_path'])
                            found_by_hand_id = True
                            break

        # Step 3: Fallback to table number matching if no hand ID matches found
        if not found_by_hand_id:
            for file in job_file_list:
                if file['file_type'] == 'screenshot' and str(table_number) in file['filename']:
                    match.screenshot_paths.append(file['file_path'])

        matches.append(match)

    return matches
