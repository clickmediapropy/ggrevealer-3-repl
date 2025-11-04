import pytest
import json
from pathlib import Path
from database import init_db, create_job, add_file
from pt4_matcher import match_failed_files_to_jobs, FailedFileMatch

def test_match_failed_files_by_table_number():
    """Test matching PT4 failed files to original jobs by table number"""
    init_db()

    # Create a job with files
    job_id = create_job()

    # Add uploaded files (simulating original uploads)
    add_file(job_id, "46798.txt", "txt", f"/storage/uploads/{job_id}/txt/46798.txt")
    add_file(job_id, "screenshot_46798_001.png", "screenshot", f"/storage/uploads/{job_id}/screenshots/screenshot_46798_001.png")
    add_file(job_id, "screenshot_46798_002.png", "screenshot", f"/storage/uploads/{job_id}/screenshots/screenshot_46798_002.png")

    # Create outputs directory and file (simulating processed output)
    outputs_dir = Path(f"storage/outputs/{job_id}")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    processed_file = outputs_dir / "46798_resolved.txt"
    processed_file.write_text("test content")

    # Failed files from PT4 log
    failed_files = [{
        'filename': '46798_resolved.txt',
        'table_number': 46798,
        'error_count': 5,
        'errors': ['Error 1', 'Error 2']
    }]

    try:
        # Match failed files to jobs
        matches = match_failed_files_to_jobs(failed_files)

        assert len(matches) == 1

        match = matches[0]
        assert match.filename == '46798_resolved.txt'
        assert match.table_number == 46798
        assert match.matched_job_id == job_id
        assert match.original_txt_path == f"/storage/uploads/{job_id}/txt/46798.txt"
        assert match.processed_txt_path == f"storage/outputs/{job_id}/46798_resolved.txt"
        assert len(match.screenshot_paths) == 2
        assert all('46798' in p for p in match.screenshot_paths)
    finally:
        # Cleanup
        if processed_file.exists():
            processed_file.unlink()
        if outputs_dir.exists():
            outputs_dir.rmdir()

def test_match_failed_files_no_match():
    """Test when failed file has no matching job"""
    init_db()

    failed_files = [{
        'filename': '99999_resolved.txt',
        'table_number': 99999,
        'error_count': 1,
        'errors': ['Error']
    }]

    matches = match_failed_files_to_jobs(failed_files)

    assert len(matches) == 1
    match = matches[0]
    assert match.matched_job_id is None
    assert match.original_txt_path is None
    assert len(match.screenshot_paths) == 0


def test_match_failed_files_by_hand_id():
    """Test matching PT4 failed files to jobs by hand ID in screenshot names"""
    init_db()

    # Create a job with files
    job_id = create_job()

    # Create a TXT file with hand IDs (simulating real hand history)
    txt_dir = Path(f"storage/uploads/{job_id}/txt")
    txt_dir.mkdir(parents=True, exist_ok=True)
    txt_file = txt_dir / "46798.txt"
    txt_file.write_text("""Poker Hand #SG3247289962: Hold'em No Limit ($0.1/$0.2) - 2025/11/03 10:20:30
Seat 1: Hero
Seat 2: Player2

Poker Hand #SG3247289963: Hold'em No Limit ($0.1/$0.2) - 2025/11/03 10:21:00
Seat 1: Hero
Seat 2: Player2
""")

    # Add uploaded file to database
    add_file(job_id, "46798.txt", "txt", str(txt_file))

    # Add screenshots with hand IDs in filenames (different naming convention)
    screenshot_dir = Path(f"storage/uploads/{job_id}/screenshots")
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    # Screenshots named by hand ID instead of table number
    screenshot1 = screenshot_dir / "2025-10-22_10_50_AM_10_20_#SG3247289962.png"
    screenshot1.write_text("screenshot1")
    add_file(job_id, screenshot1.name, "screenshot", str(screenshot1))

    screenshot2 = screenshot_dir / "2025-10-22_10_51_AM_10_21_#SG3247289963.png"
    screenshot2.write_text("screenshot2")
    add_file(job_id, screenshot2.name, "screenshot", str(screenshot2))

    # Create outputs directory and file
    outputs_dir = Path(f"storage/outputs/{job_id}")
    outputs_dir.mkdir(parents=True, exist_ok=True)
    processed_file = outputs_dir / "46798_resolved.txt"
    processed_file.write_text("test content")

    # Failed file from PT4 log
    failed_files = [{
        'filename': '46798_resolved.txt',
        'table_number': 46798,
        'error_count': 1,
        'errors': ['Some error']
    }]

    try:
        # Match failed files to jobs
        matches = match_failed_files_to_jobs(failed_files)

        assert len(matches) == 1

        match = matches[0]
        assert match.filename == '46798_resolved.txt'
        assert match.table_number == 46798
        assert match.matched_job_id == job_id
        assert match.original_txt_path == str(txt_file)
        assert match.processed_txt_path == str(processed_file)

        # Most important: screenshots should be found by hand ID
        assert len(match.screenshot_paths) == 2
        assert all('sg3247289962' in p.lower() or 'sg3247289963' in p.lower()
                   for p in match.screenshot_paths)
    finally:
        # Cleanup
        if txt_file.exists():
            txt_file.unlink()
        if screenshot1.exists():
            screenshot1.unlink()
        if screenshot2.exists():
            screenshot2.unlink()
        if txt_dir.exists():
            txt_dir.rmdir()
        if screenshot_dir.exists():
            screenshot_dir.rmdir()
        if processed_file.exists():
            processed_file.unlink()
        if outputs_dir.exists():
            outputs_dir.rmdir()
