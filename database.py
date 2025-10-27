"""
SQLite database setup and models
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict
from contextlib import contextmanager

DATABASE_PATH = "ggrevealer.db"


# ============================================================================
# DATABASE SCHEMA
# ============================================================================

SCHEMA = """
-- Jobs table
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL,
    txt_files_count INTEGER DEFAULT 0,
    screenshot_files_count INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    processing_time_seconds REAL,
    matched_hands INTEGER DEFAULT 0,
    name_mappings_count INTEGER DEFAULT 0,
    hands_parsed INTEGER DEFAULT 0,
    ocr_processed_count INTEGER DEFAULT 0,
    ocr_total_count INTEGER DEFAULT 0
);

-- Files table
CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_path TEXT NOT NULL,
    uploaded_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
);

-- Results table
CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL UNIQUE,
    output_txt_path TEXT,
    mappings_json TEXT,
    stats_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
);
"""


# ============================================================================
# DATABASE FUNCTIONS
# ============================================================================

@contextmanager
def get_db():
    """Get database connection with context manager"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Initialize database with schema"""
    with get_db() as conn:
        conn.executescript(SCHEMA)
        
        # Migration: Add new columns if they don't exist
        cursor = conn.execute("PRAGMA table_info(jobs)")
        columns = [row[1] for row in cursor.fetchall()]
        
        migrations = []
        if 'started_at' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN started_at TEXT")
        if 'processing_time_seconds' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN processing_time_seconds REAL")
        if 'matched_hands' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN matched_hands INTEGER DEFAULT 0")
        if 'name_mappings_count' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN name_mappings_count INTEGER DEFAULT 0")
        if 'hands_parsed' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN hands_parsed INTEGER DEFAULT 0")
        if 'ocr_processed_count' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN ocr_processed_count INTEGER DEFAULT 0")
        if 'ocr_total_count' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN ocr_total_count INTEGER DEFAULT 0")
        
        for migration in migrations:
            conn.execute(migration)
            
    print("✅ Database initialized")


# ============================================================================
# JOB OPERATIONS
# ============================================================================

def create_job() -> int:
    """Create a new job and return job ID"""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO jobs (created_at, status) VALUES (?, ?)",
            (datetime.utcnow().isoformat(), 'pending')
        )
        return cursor.lastrowid


def get_job(job_id: int) -> Optional[Dict]:
    """Get job by ID"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row:
            return dict(row)
    return None


def get_all_jobs() -> List[Dict]:
    """Get all jobs ordered by created_at desc"""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]


def update_job_status(job_id: int, status: str, error_message: Optional[str] = None):
    """Update job status"""
    completed_at = datetime.utcnow().isoformat() if status == 'completed' else None
    with get_db() as conn:
        conn.execute(
            "UPDATE jobs SET status = ?, error_message = ?, completed_at = ? WHERE id = ?",
            (status, error_message, completed_at, job_id)
        )


def mark_job_started(job_id: int):
    """Mark job as started with timestamp"""
    with get_db() as conn:
        conn.execute(
            "UPDATE jobs SET started_at = ?, status = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), 'processing', job_id)
        )


def update_job_stats(job_id: int, matched_hands: int, name_mappings_count: int, hands_parsed: int):
    """Update job statistics after processing"""
    with get_db() as conn:
        # Get started_at to calculate processing time
        row = conn.execute("SELECT started_at FROM jobs WHERE id = ?", (job_id,)).fetchone()
        processing_time = None
        if row and row['started_at']:
            started = datetime.fromisoformat(row['started_at'])
            completed = datetime.utcnow()
            processing_time = (completed - started).total_seconds()
        
        conn.execute(
            """UPDATE jobs 
               SET matched_hands = ?, 
                   name_mappings_count = ?, 
                   hands_parsed = ?,
                   processing_time_seconds = ?
               WHERE id = ?""",
            (matched_hands, name_mappings_count, hands_parsed, processing_time, job_id)
        )


def update_job_file_counts(job_id: int, txt_count: int, screenshot_count: int):
    """Update file counts for a job"""
    with get_db() as conn:
        conn.execute(
            "UPDATE jobs SET txt_files_count = ?, screenshot_files_count = ? WHERE id = ?",
            (txt_count, screenshot_count, job_id)
        )


def set_ocr_total_count(job_id: int, total: int):
    """Set total count of OCR screenshots to process"""
    with get_db() as conn:
        conn.execute(
            "UPDATE jobs SET ocr_total_count = ?, ocr_processed_count = 0 WHERE id = ?",
            (total, job_id)
        )


def increment_ocr_processed_count(job_id: int):
    """Increment OCR processed count by 1"""
    with get_db() as conn:
        conn.execute(
            "UPDATE jobs SET ocr_processed_count = ocr_processed_count + 1 WHERE id = ?",
            (job_id,)
        )


def delete_job(job_id: int):
    """Delete job and all related data"""
    with get_db() as conn:
        conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))


# ============================================================================
# FILE OPERATIONS
# ============================================================================

def add_file(job_id: int, filename: str, file_type: str, file_path: str):
    """Add a file to the database"""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO files (job_id, filename, file_type, file_path, uploaded_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, filename, file_type, file_path, datetime.utcnow().isoformat())
        )


def get_job_files(job_id: int, file_type: Optional[str] = None) -> List[Dict]:
    """Get all files for a job, optionally filtered by type"""
    with get_db() as conn:
        if file_type:
            rows = conn.execute(
                "SELECT * FROM files WHERE job_id = ? AND file_type = ?",
                (job_id, file_type)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM files WHERE job_id = ?",
                (job_id,)
            ).fetchall()
        return [dict(row) for row in rows]


# ============================================================================
# RESULT OPERATIONS
# ============================================================================

def save_result(job_id: int, output_txt_path: str, mappings: List[Dict], stats: Dict):
    """Save processing result"""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO results (job_id, output_txt_path, mappings_json, stats_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, output_txt_path, json.dumps(mappings), json.dumps(stats), datetime.utcnow().isoformat())
        )


def get_result(job_id: int) -> Optional[Dict]:
    """Get result for a job"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM results WHERE job_id = ?", (job_id,)).fetchone()
        if row:
            result = dict(row)
            if result.get('mappings_json'):
                result['mappings'] = json.loads(result['mappings_json'])
            if result.get('stats_json'):
                result['stats'] = json.loads(result['stats_json'])
            return result
    return None
