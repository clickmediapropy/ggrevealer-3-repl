import pytest
from fastapi.testclient import TestClient
from main import app
from database import init_db, create_job, add_file

client = TestClient(app)

def test_upload_pt4_log_success():
    """Test uploading PT4 log and parsing failed files"""
    init_db()

    # Create a job with files first
    job_id = create_job()
    add_file(job_id, "46798.txt", "txt", f"/storage/uploads/{job_id}/txt/46798.txt")
    add_file(job_id, "screenshot_46798_001.png", "screenshot", f"/storage/uploads/{job_id}/screenshots/screenshot_46798_001.png")

    pt4_log = """06:58:32 pm: Importing files from disk...
06:58:32 pm: Import file: /Users/nicodelgadob/Downloads/resolved_hands_35 (1)/46798_resolved.txt
06:58:32 pm: Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247438352) (Line #5)
06:58:32 pm:         + Complete (0 hands, 0 summaries, 1 error, 0 duplicates)
06:58:32 pm: Import complete. 0 hands in 1 file were imported. (1 error, 0 duplicates)"""

    response = client.post(
        "/api/pt4-log/upload",
        data={"log_text": pt4_log, "job_id": job_id}
    )

    assert response.status_code == 200
    data = response.json()

    assert data['success'] is True
    assert data['attempt_id'] is not None
    assert data['total_files'] == 1
    assert data['failed_files_count'] == 1
    assert len(data['failed_files']) == 1

    failed_file = data['failed_files'][0]
    assert failed_file['filename'] == '46798_resolved.txt'
    assert failed_file['table_number'] == 46798
    assert failed_file['matched_job_id'] == job_id
    assert failed_file['original_txt_path'] is not None
    assert len(failed_file['screenshot_paths']) > 0

def test_upload_pt4_log_no_failures():
    """Test uploading PT4 log with no errors"""
    init_db()

    pt4_log = """06:58:32 pm: Importing files from disk...
06:58:32 pm: Import file: /path/43746_resolved.txt
06:58:32 pm:         + Complete (9 hands, 0 summaries, 0 errors, 0 duplicates)
06:58:32 pm: Import complete. 9 hands in 1 file were imported. (0 errors, 0 duplicates)"""

    response = client.post(
        "/api/pt4-log/upload",
        data={"log_text": pt4_log}
    )

    assert response.status_code == 200
    data = response.json()

    assert data['success'] is True
    assert data['failed_files_count'] == 0
    assert len(data['failed_files']) == 0
