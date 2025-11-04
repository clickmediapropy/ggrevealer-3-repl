import pytest
from database import init_db, create_pt4_import_attempt, create_pt4_failed_file, get_db

def test_create_pt4_import_attempt():
    """Test creating a PT4 import attempt record"""
    init_db()

    pt4_log = """06:58:32 pm: Import file: /path/46798_resolved.txt
06:58:32 pm: Error: GG Poker: Duplicate player...
06:58:32 pm:         + Complete (0 hands, 0 summaries, 5 errors, 0 duplicates)"""

    attempt_id = create_pt4_import_attempt(
        job_id=1,
        import_log=pt4_log,
        total_files=1,
        failed_files_count=1
    )

    assert attempt_id is not None
    assert attempt_id > 0

    # Verify stored in database
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM pt4_import_attempts WHERE id = ?",
            (attempt_id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['job_id'] == 1
        assert row['total_files'] == 1
        assert row['failed_files_count'] == 1

def test_create_pt4_failed_file():
    """Test creating a PT4 failed file record"""
    init_db()

    # Create parent import attempt
    attempt_id = create_pt4_import_attempt(
        job_id=1,
        import_log="test log",
        total_files=1,
        failed_files_count=1
    )

    # Create failed file record
    import json
    failed_file_id = create_pt4_failed_file(
        pt4_import_attempt_id=attempt_id,
        filename="46798_resolved.txt",
        table_number=46798,
        error_count=5,
        error_details=json.dumps([
            "Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247438352) (Line #5)"
        ]),
        associated_job_id=1
    )

    assert failed_file_id is not None
    assert failed_file_id > 0

    # Verify stored
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT * FROM pt4_failed_files WHERE id = ?",
            (failed_file_id,)
        )
        row = cursor.fetchone()
        assert row is not None
        assert row['filename'] == "46798_resolved.txt"
        assert row['table_number'] == 46798
        assert row['error_count'] == 5
