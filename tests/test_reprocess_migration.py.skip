import pytest
import sqlite3
from database import init_db, DATABASE_PATH

def test_reprocess_attempts_table_exists():
    """Test that reprocess_attempts table is created during init"""
    init_db()

    # Direct connection for testing
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Query table schema
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reprocess_attempts'")
    result = cursor.fetchone()

    conn.close()

    assert result is not None, "reprocess_attempts table should exist"

def test_reprocess_attempts_table_schema():
    """Test that reprocess_attempts has correct columns"""
    init_db()

    # Direct connection for testing
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(reprocess_attempts)")
    columns = {row[1] for row in cursor.fetchall()}

    conn.close()

    required_cols = {
        'id', 'job_id', 'file_source', 'file_id', 'file_name',
        'attempt_number', 'status', 'error_message', 'logs_json', 'created_at'
    }

    assert required_cols.issubset(columns), f"Missing columns: {required_cols - columns}"

def test_pt4_failed_files_has_reprocess_columns():
    """Test that pt4_failed_files has reprocess tracking columns"""
    init_db()

    # Direct connection for testing
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(pt4_failed_files)")
    columns = {row[1] for row in cursor.fetchall()}

    conn.close()

    required_cols = {'reprocess_count', 'last_reprocess_attempt_id'}

    assert required_cols.issubset(columns), f"Missing columns: {required_cols - columns}"
