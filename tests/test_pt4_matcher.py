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
