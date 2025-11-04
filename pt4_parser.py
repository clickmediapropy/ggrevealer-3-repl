"""
PokerTracker 4 import log parser
Extracts failed files from PT4 import logs
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class PT4ParsedResult:
    """Result of parsing a PT4 import log"""
    total_files: int
    total_hands_imported: int
    total_errors: int
    total_duplicates: int
    failed_files: List[Dict]


def extract_table_number(filename: str) -> Optional[int]:
    """
    Extract table number from filename like '46798_resolved.txt'

    Args:
        filename: Filename with or without path

    Returns:
        Table number as int, or None if not found
    """
    # Extract just the filename if path included
    basename = filename.split('/')[-1]

    # Match pattern: {digits}_{suffix}.txt
    match = re.match(r'^(\d+)_(?:resolved|fallado)\.txt$', basename)
    if match:
        return int(match.group(1))
    return None


def parse_pt4_import_log(log_text: str) -> Optional[PT4ParsedResult]:
    """
    Parse PokerTracker 4 import log to extract failed files

    Args:
        log_text: Raw PT4 import log text

    Returns:
        PT4ParsedResult with parsed data, or None if invalid log
    """
    lines = log_text.strip().split('\n')

    failed_files = []
    current_file = None
    current_errors = []

    total_files = 0
    total_hands = 0
    total_errors = 0
    total_duplicates = 0

    for line in lines:
        # Match: Import file: /path/to/46798_resolved.txt
        file_match = re.search(r'Import file:\s+(.+\.txt)$', line)
        if file_match:
            # Save previous file if it had errors
            if current_file and current_errors:
                filename = current_file.split('/')[-1]
                table_num = extract_table_number(filename)
                failed_files.append({
                    'filename': filename,
                    'table_number': table_num,
                    'error_count': len(current_errors),
                    'errors': current_errors.copy()
                })

            # Start new file
            current_file = file_match.group(1)
            current_errors = []
            total_files += 1
            continue

        # Match: Error: GG Poker: Duplicate player...
        error_match = re.search(r'^\d{2}:\d{2}:\d{2}\s+[ap]m:\s+Error:\s+(.+)$', line)
        if error_match:
            current_errors.append(error_match.group(1))
            continue

        # Match: + Complete (X hands, Y summaries, Z errors, W duplicates)
        complete_match = re.search(
            r'\+\s+Complete\s+\((\d+)\s+hands?,\s+\d+\s+summaries?,\s+(\d+)\s+errors?,\s+(\d+)\s+duplicates?\)',
            line
        )
        if complete_match:
            hands = int(complete_match.group(1))
            errors = int(complete_match.group(2))
            duplicates = int(complete_match.group(3))

            total_hands += hands
            total_errors += errors
            total_duplicates += duplicates

            # If errors > 0, save this file
            if errors > 0 and current_file:
                filename = current_file.split('/')[-1]
                table_num = extract_table_number(filename)
                failed_files.append({
                    'filename': filename,
                    'table_number': table_num,
                    'error_count': len(current_errors),
                    'errors': current_errors.copy()
                })

            # Reset for next file
            current_file = None
            current_errors = []
            continue

    return PT4ParsedResult(
        total_files=total_files,
        total_hands_imported=total_hands,
        total_errors=total_errors,
        total_duplicates=total_duplicates,
        failed_files=failed_files
    )
