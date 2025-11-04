import pytest
from database import init_db, get_db, create_job, get_failed_files_for_job, create_reprocess_attempt
import json
from datetime import datetime

@pytest.fixture
def setup_db():
    """Setup fresh DB for testing"""
    init_db()
    yield
    # Cleanup

def test_get_failed_files_returns_both_sources(setup_db):
    """Test that get_failed_files_for_job returns PT4 and App failures"""
    job_id = create_job(api_tier='free')

    # Manually insert PT4 import attempt first (required by FK constraint)
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute('''
            INSERT INTO pt4_import_attempts (job_id, import_log, parsed_at, created_at)
            VALUES (?, ?, datetime('now'), datetime('now'))
        ''', (job_id, 'test log'))
        attempt_id = cursor.lastrowid

        # Manually insert PT4 failure
        cursor.execute('''
            INSERT INTO pt4_failed_files (pt4_import_attempt_id, filename, table_number, error_details, error_count,
                                          associated_job_id, created_at, reprocess_count, last_reprocess_attempt_id)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?, ?)
        ''', (attempt_id, '46798_resolved.txt', 46798, 'hero count error', 1, job_id, 0, None))

        # Manually insert app result with failed_files in stats_json
        stats = {
            'failed_files': [
                {'table_name': '46798', 'unmapped_ids': ['a1b2c3'], 'unmapped_count': 1}
            ]
        }
        cursor.execute('''
            INSERT INTO results (job_id, stats_json, created_at)
            VALUES (?, ?, datetime('now'))
        ''', (job_id, json.dumps(stats)))
        db.commit()

    # Call function
    failed_files = get_failed_files_for_job(job_id)

    # Verify structure
    assert 'pt4_failures' in failed_files
    assert 'app_failures' in failed_files
    assert len(failed_files['pt4_failures']) == 1
    assert len(failed_files['app_failures']) == 1
    assert failed_files['pt4_failures'][0]['filename'] == '46798_resolved.txt'
    assert failed_files['app_failures'][0]['table_name'] == '46798'

def test_create_reprocess_attempt(setup_db):
    """Test creating a reprocess attempt record"""
    job_id = create_job(api_tier='free')

    attempt_id = create_reprocess_attempt(
        job_id=job_id,
        file_source='pt4',
        file_id=1,
        file_name='46798_resolved.txt',
        attempt_number=1
    )

    assert attempt_id > 0

    # Verify stored in DB
    with get_db() as db:
        cursor = db.cursor()
        cursor.execute('SELECT * FROM reprocess_attempts WHERE id = ?', (attempt_id,))
        row = cursor.fetchone()

    assert row is not None
    assert row[1] == job_id  # job_id
    assert row[2] == 'pt4'   # file_source
    assert row[3] == 1       # file_id
    assert row[4] == '46798_resolved.txt'  # file_name
    assert row[5] == 1       # attempt_number
    assert row[6] == 'pending'  # status
