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
    ocr_total_count INTEGER DEFAULT 0,
    api_tier TEXT DEFAULT 'free' CHECK(api_tier IN ('free', 'paid'))
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

-- Screenshot results table (granular tracking)
CREATE TABLE IF NOT EXISTS screenshot_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    screenshot_filename TEXT NOT NULL,
    ocr1_success INTEGER DEFAULT 0,
    ocr1_hand_id TEXT,
    ocr1_error TEXT,
    ocr1_retry_count INTEGER DEFAULT 0,
    ocr2_success INTEGER DEFAULT 0,
    ocr2_data TEXT,
    ocr2_error TEXT,
    matches_found INTEGER DEFAULT 0,
    discard_reason TEXT,
    unmapped_players TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
);

-- Logs table (structured logging)
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    timestamp TEXT NOT NULL,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    extra_data TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_logs_job_id ON logs(job_id);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp);

-- PT4 import attempts table (second-stage failure tracking)
CREATE TABLE IF NOT EXISTS pt4_import_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    import_log TEXT NOT NULL,
    parsed_at TEXT NOT NULL,
    total_files INTEGER DEFAULT 0,
    failed_files_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pt4_attempts_job_id ON pt4_import_attempts(job_id);

-- PT4 failed files table (individual failed files)
CREATE TABLE IF NOT EXISTS pt4_failed_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pt4_import_attempt_id INTEGER NOT NULL,
    filename TEXT NOT NULL,
    table_number INTEGER,
    error_count INTEGER DEFAULT 0,
    error_details TEXT,
    associated_job_id INTEGER,
    associated_original_txt_path TEXT,
    associated_processed_txt_path TEXT,
    associated_screenshot_paths TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (pt4_import_attempt_id) REFERENCES pt4_import_attempts (id) ON DELETE CASCADE,
    FOREIGN KEY (associated_job_id) REFERENCES jobs (id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_pt4_failed_files_attempt_id ON pt4_failed_files(pt4_import_attempt_id);
CREATE INDEX IF NOT EXISTS idx_pt4_failed_files_table_number ON pt4_failed_files(table_number);

-- App config table (cost tracking and budget management)
CREATE TABLE IF NOT EXISTS app_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    monthly_budget REAL DEFAULT 200.0,
    budget_reset_day INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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
        if 'ocr1_success_count' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN ocr1_success_count INTEGER DEFAULT 0")
        if 'ocr1_failure_count' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN ocr1_failure_count INTEGER DEFAULT 0")
        if 'ocr2_success_count' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN ocr2_success_count INTEGER DEFAULT 0")
        if 'ocr2_failure_count' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN ocr2_failure_count INTEGER DEFAULT 0")
        if 'tables_fully_resolved' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN tables_fully_resolved INTEGER DEFAULT 0")
        if 'tables_total' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN tables_total INTEGER DEFAULT 0")
        if 'ocr1_images_processed' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN ocr1_images_processed INTEGER DEFAULT 0")
        if 'ocr2_images_processed' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN ocr2_images_processed INTEGER DEFAULT 0")
        if 'total_api_cost' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN total_api_cost REAL DEFAULT 0.0")
        if 'cost_calculated_at' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN cost_calculated_at TEXT")
        if 'api_tier' not in columns:
            migrations.append("ALTER TABLE jobs ADD COLUMN api_tier TEXT DEFAULT 'free' CHECK(api_tier IN ('free', 'paid'))")

        for migration in migrations:
            conn.execute(migration)

        # NEW: Dual OCR migrations for screenshot_results
        cursor = conn.execute("PRAGMA table_info(screenshot_results)")
        ss_columns = [row[1] for row in cursor.fetchall()]

        dual_ocr_migrations = []

        # Drop old columns if they exist
        if 'ocr_success' in ss_columns:
            # SQLite doesn't support DROP COLUMN directly, need to recreate table
            dual_ocr_migrations.append("DROP_OLD_COLUMNS")

        # Add new columns if not exist
        if 'ocr1_success' not in ss_columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr1_success INTEGER DEFAULT 0"
            )
        if 'ocr1_hand_id' not in ss_columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr1_hand_id TEXT"
            )
        if 'ocr1_error' not in ss_columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr1_error TEXT"
            )
        if 'ocr1_retry_count' not in ss_columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr1_retry_count INTEGER DEFAULT 0"
            )
        if 'ocr2_success' not in ss_columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr2_success INTEGER DEFAULT 0"
            )
        if 'ocr2_data' not in ss_columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr2_data TEXT"
            )
        if 'ocr2_error' not in ss_columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN ocr2_error TEXT"
            )
        if 'discard_reason' not in ss_columns:
            dual_ocr_migrations.append(
                "ALTER TABLE screenshot_results ADD COLUMN discard_reason TEXT"
            )

        # Execute migrations
        for migration in dual_ocr_migrations:
            if migration == "DROP_OLD_COLUMNS":
                # Recreate table without old columns
                _recreate_screenshot_results_table(conn)
            else:
                conn.execute(migration)

        if dual_ocr_migrations:
            print(f"✅ Applied {len(dual_ocr_migrations)} dual OCR migrations")

    print("✅ Database initialized")


def _recreate_screenshot_results_table(conn):
    """Recreate screenshot_results table without old columns"""
    # Get all data
    rows = conn.execute("SELECT * FROM screenshot_results").fetchall()

    # Drop old table
    conn.execute("DROP TABLE screenshot_results")

    # Create new table with new schema (will be created by SCHEMA)
    conn.executescript("""
        CREATE TABLE screenshot_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            screenshot_filename TEXT NOT NULL,
            ocr1_success INTEGER DEFAULT 0,
            ocr1_hand_id TEXT,
            ocr1_error TEXT,
            ocr1_retry_count INTEGER DEFAULT 0,
            ocr2_success INTEGER DEFAULT 0,
            ocr2_data TEXT,
            ocr2_error TEXT,
            matches_found INTEGER DEFAULT 0,
            discard_reason TEXT,
            unmapped_players TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs (id) ON DELETE CASCADE
        );
    """)

    # Migrate data (map old columns to new where possible)
    for row in rows:
        conn.execute("""
            INSERT INTO screenshot_results
            (id, job_id, screenshot_filename, matches_found, unmapped_players, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            row['id'], row['job_id'], row['screenshot_filename'],
            row.get('matches_found', 0), row.get('unmapped_players'),
            row['status'], row['created_at']
        ))


# ============================================================================
# JOB OPERATIONS
# ============================================================================

def create_job(api_tier: str = 'free') -> int:
    """Create a new job and return job ID"""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO jobs (created_at, status, api_tier) VALUES (?, ?, ?)",
            (datetime.utcnow().isoformat(), 'pending', api_tier)
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


def update_job_detailed_metrics(job_id: int, detailed_metrics: dict):
    """Update job with detailed metrics from dual OCR pipeline"""
    with get_db() as conn:
        conn.execute(
            """UPDATE jobs
               SET ocr1_success_count = ?,
                   ocr1_failure_count = ?,
                   ocr2_success_count = ?,
                   ocr2_failure_count = ?,
                   tables_fully_resolved = ?,
                   tables_total = ?
               WHERE id = ?""",
            (
                detailed_metrics['screenshots']['ocr1_success'],
                detailed_metrics['screenshots']['ocr1_failure'],
                detailed_metrics['screenshots']['ocr2_success'],
                detailed_metrics['screenshots']['ocr2_failure'],
                detailed_metrics['tables']['fully_resolved'],
                detailed_metrics['tables']['total'],
                job_id
            )
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


# ============================================================================
# SCREENSHOT RESULT OPERATIONS
# ============================================================================

def save_screenshot_result(
    job_id: int,
    screenshot_filename: str,
    ocr_success: bool,
    ocr_error: Optional[str] = None,
    ocr_data: Optional[Dict] = None,
    matches_found: int = 0,
    unmapped_players: Optional[List[str]] = None,
    status: str = "success"
):
    """Save individual screenshot processing result"""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO screenshot_results 
            (job_id, screenshot_filename, ocr_success, ocr_error, ocr_data, matches_found, unmapped_players, status, created_at) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                screenshot_filename,
                1 if ocr_success else 0,
                ocr_error,
                json.dumps(ocr_data) if ocr_data else None,
                matches_found,
                json.dumps(unmapped_players) if unmapped_players else None,
                status,
                datetime.utcnow().isoformat()
            )
        )


def get_screenshot_results(job_id: int) -> List[Dict]:
    """Get all screenshot results for a job"""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM screenshot_results WHERE job_id = ? ORDER BY created_at",
            (job_id,)
        ).fetchall()
        results = []
        for row in rows:
            result = dict(row)
            if result.get('ocr_data'):
                result['ocr_data'] = json.loads(result['ocr_data'])
            if result.get('unmapped_players'):
                result['unmapped_players'] = json.loads(result['unmapped_players'])
            result['ocr_success'] = bool(result.get('ocr_success'))
            results.append(result)
        return results


def update_screenshot_result_matches(
    job_id: int,
    screenshot_filename: str,
    matches_found: int,
    unmapped_players: Optional[List[str]] = None,
    status: str = "success"
):
    """Update screenshot result with match count and status"""
    with get_db() as conn:
        conn.execute(
            """UPDATE screenshot_results
            SET matches_found = ?, unmapped_players = ?, status = ?
            WHERE job_id = ? AND screenshot_filename = ?""",
            (
                matches_found,
                json.dumps(unmapped_players) if unmapped_players else None,
                status,
                job_id,
                screenshot_filename
            )
        )


# ============================================================================
# LOG OPERATIONS
# ============================================================================

def save_log(
    job_id: Optional[int],
    timestamp: str,
    level: str,
    message: str,
    extra_data: Optional[Dict] = None
):
    """Save a single log entry"""
    with get_db() as conn:
        conn.execute(
            """INSERT INTO logs (job_id, timestamp, level, message, extra_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                timestamp,
                level,
                message,
                json.dumps(extra_data) if extra_data else None,
                datetime.utcnow().isoformat()
            )
        )


def save_logs_batch(job_id: int, log_entries: List[Dict]):
    """Save multiple log entries at once"""
    with get_db() as conn:
        for log_entry in log_entries:
            conn.execute(
                """INSERT INTO logs (job_id, timestamp, level, message, extra_data, created_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    job_id,
                    log_entry.get('timestamp'),
                    log_entry.get('level'),
                    log_entry.get('message'),
                    json.dumps(log_entry.get('extra')) if log_entry.get('extra') else None,
                    datetime.utcnow().isoformat()
                )
            )


def get_job_logs(job_id: int, level: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
    """Get logs for a specific job, optionally filtered by level"""
    with get_db() as conn:
        query = "SELECT * FROM logs WHERE job_id = ?"
        params = [job_id]

        if level:
            query += " AND level = ?"
            params.append(level)

        query += " ORDER BY timestamp DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            result = dict(row)
            if result.get('extra_data'):
                result['extra_data'] = json.loads(result['extra_data'])
            results.append(result)
        return results


def get_system_logs(level: Optional[str] = None, limit: Optional[int] = None) -> List[Dict]:
    """Get system logs (logs without job_id)"""
    with get_db() as conn:
        query = "SELECT * FROM logs WHERE job_id IS NULL"
        params = []

        if level:
            query += " AND level = ?"
            params.append(level)

        query += " ORDER BY timestamp DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        rows = conn.execute(query, params).fetchall()
        results = []
        for row in rows:
            result = dict(row)
            if result.get('extra_data'):
                result['extra_data'] = json.loads(result['extra_data'])
            results.append(result)
        return results


def clear_job_results(job_id: int):
    """
    Clear all processing results for a job to allow reprocessing
    Deletes: screenshot_results, results, logs
    Resets: job stats and timestamps
    Keeps: files table (uploaded files remain)
    """
    with get_db() as conn:
        # Delete related data from other tables
        conn.execute("DELETE FROM screenshot_results WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM results WHERE job_id = ?", (job_id,))
        conn.execute("DELETE FROM logs WHERE job_id = ?", (job_id,))

        # Reset job stats and timestamps
        conn.execute("""
            UPDATE jobs
            SET matched_hands = 0,
                name_mappings_count = 0,
                hands_parsed = 0,
                ocr_processed_count = 0,
                ocr_total_count = 0,
                ocr1_images_processed = 0,
                ocr2_images_processed = 0,
                total_api_cost = 0.0,
                cost_calculated_at = NULL,
                started_at = NULL,
                completed_at = NULL,
                processing_time_seconds = NULL,
                error_message = NULL,
                status = 'pending'
            WHERE id = ?
        """, (job_id,))


# ============================================================================
# DUAL OCR OPERATIONS
# ============================================================================

def save_ocr1_result(job_id: int, screenshot_filename: str,
                     success: bool, hand_id: str = None, error: str = None,
                     retry_count: int = 0):
    """Save first OCR (Hand ID extraction) result"""
    with get_db() as conn:
        # Check if entry exists
        existing = conn.execute(
            "SELECT id FROM screenshot_results WHERE job_id = ? AND screenshot_filename = ?",
            (job_id, screenshot_filename)
        ).fetchone()

        if existing:
            # Update existing
            conn.execute("""
                UPDATE screenshot_results
                SET ocr1_success = ?, ocr1_hand_id = ?, ocr1_error = ?,
                    ocr1_retry_count = ?, status = ?
                WHERE id = ?
            """, (int(success), hand_id, error, retry_count, 'ocr1_completed', existing['id']))
        else:
            # Insert new
            conn.execute("""
                INSERT INTO screenshot_results
                (job_id, screenshot_filename, ocr1_success, ocr1_hand_id, ocr1_error,
                 ocr1_retry_count, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (job_id, screenshot_filename, int(success), hand_id, error,
                  retry_count, 'ocr1_completed', datetime.utcnow().isoformat()))


def save_ocr2_result(job_id: int, screenshot_filename: str,
                     success: bool, ocr_data: dict = None, error: str = None):
    """Save second OCR (player details) result"""
    with get_db() as conn:
        conn.execute("""
            UPDATE screenshot_results
            SET ocr2_success = ?, ocr2_data = ?, ocr2_error = ?, status = ?
            WHERE job_id = ? AND screenshot_filename = ?
        """, (int(success), json.dumps(ocr_data) if ocr_data else None,
              error, 'ocr2_completed', job_id, screenshot_filename))


def mark_screenshot_discarded(job_id: int, screenshot_filename: str, reason: str):
    """Mark screenshot as discarded after retry failures"""
    with get_db() as conn:
        conn.execute("""
            UPDATE screenshot_results
            SET discard_reason = ?, status = ?
            WHERE job_id = ? AND screenshot_filename = ?
        """, (reason, 'discarded', job_id, screenshot_filename))


# ============================================================================
# COST TRACKING OPERATIONS
# ============================================================================

def update_job_cost(job_id: int, ocr1_count: int, ocr2_count: int, total_cost: float):
    """Update job with OCR counts and total API cost"""
    with get_db() as conn:
        conn.execute("""
            UPDATE jobs
            SET ocr1_images_processed = ?,
                ocr2_images_processed = ?,
                total_api_cost = ?,
                cost_calculated_at = ?
            WHERE id = ?
        """, (ocr1_count, ocr2_count, total_cost, datetime.utcnow().isoformat(), job_id))


def get_budget_config() -> Optional[Dict]:
    """Get current budget configuration"""
    with get_db() as conn:
        row = conn.execute("SELECT * FROM app_config WHERE id = 1").fetchone()
        if row:
            return dict(row)
    return None


def save_budget_config(monthly_budget: float, budget_reset_day: int):
    """Save or update budget configuration"""
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM app_config WHERE id = 1").fetchone()

        if existing:
            # Update existing config
            conn.execute("""
                UPDATE app_config
                SET monthly_budget = ?, budget_reset_day = ?, updated_at = ?
                WHERE id = 1
            """, (monthly_budget, budget_reset_day, datetime.utcnow().isoformat()))
        else:
            # Insert new config
            now = datetime.utcnow().isoformat()
            conn.execute("""
                INSERT INTO app_config (id, monthly_budget, budget_reset_day, created_at, updated_at)
                VALUES (1, ?, ?, ?, ?)
            """, (monthly_budget, budget_reset_day, now, now))


def get_monthly_spending() -> float:
    """Get total spending for the current month"""
    with get_db() as conn:
        result = conn.execute("""
            SELECT SUM(total_api_cost) as monthly_total
            FROM jobs
            WHERE strftime('%Y-%m', created_at) = strftime('%Y-%m', 'now')
            AND status = 'completed'
        """).fetchone()
        return result['monthly_total'] if result['monthly_total'] else 0.0


def get_budget_summary() -> Dict:
    """Get complete budget summary including spending and percentage"""
    config = get_budget_config()
    monthly_spending = get_monthly_spending()

    if not config:
        # Default values if no config exists
        monthly_budget = 200.0
        budget_reset_day = 1
    else:
        monthly_budget = config['monthly_budget']
        budget_reset_day = config['budget_reset_day']

    remaining_budget = monthly_budget - monthly_spending
    percentage_used = (monthly_spending / monthly_budget * 100) if monthly_budget > 0 else 0

    return {
        'monthly_budget': monthly_budget,
        'monthly_spending': monthly_spending,
        'remaining_budget': remaining_budget,
        'percentage_used': percentage_used,
        'budget_reset_day': budget_reset_day
    }


def create_pt4_import_attempt(
    job_id: int,
    import_log: str,
    total_files: int,
    failed_files_count: int
) -> int:
    """Create a new PT4 import attempt record"""
    from datetime import datetime

    now = datetime.now().isoformat()

    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO pt4_import_attempts
            (job_id, import_log, parsed_at, total_files, failed_files_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_id, import_log, now, total_files, failed_files_count, now)
        )
        return cursor.lastrowid


def create_pt4_failed_file(
    pt4_import_attempt_id: int,
    filename: str,
    table_number: Optional[int],
    error_count: int,
    error_details: str,
    associated_job_id: Optional[int] = None,
    associated_original_txt_path: Optional[str] = None,
    associated_processed_txt_path: Optional[str] = None,
    associated_screenshot_paths: Optional[str] = None
) -> int:
    """Create a new PT4 failed file record"""
    from datetime import datetime

    now = datetime.now().isoformat()

    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO pt4_failed_files
            (pt4_import_attempt_id, filename, table_number, error_count, error_details,
             associated_job_id, associated_original_txt_path, associated_processed_txt_path,
             associated_screenshot_paths, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (pt4_import_attempt_id, filename, table_number, error_count, error_details,
             associated_job_id, associated_original_txt_path, associated_processed_txt_path,
             associated_screenshot_paths, now)
        )
        return cursor.lastrowid


def get_files_by_table_number(table_number: int) -> List[Dict]:
    """
    Get all files associated with a table number across all jobs

    Args:
        table_number: Table number to search for (e.g., 46798)

    Returns:
        List of dicts with job_id, filename, file_type, file_path
    """
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT job_id, filename, file_type, file_path
            FROM files
            WHERE filename LIKE ? OR filename LIKE ?
            ORDER BY job_id DESC, uploaded_at DESC
            """,
            (f"{table_number}.txt", f"%{table_number}%")
        )
        return [dict(row) for row in cursor.fetchall()]


def get_job_outputs_path(job_id: int) -> Optional[str]:
    """Get the outputs directory path for a job"""
    from pathlib import Path
    outputs_path = Path("storage/outputs") / str(job_id)
    if outputs_path.exists():
        return str(outputs_path)
    return None


def get_pt4_failed_files_for_job(job_id: int) -> List[Dict]:
    """
    Get all PT4 failed files associated with a job

    Args:
        job_id: Job ID to filter by

    Returns:
        List of dicts with failed file details
    """
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT pff.*, pia.import_log, pia.parsed_at
            FROM pt4_failed_files pff
            JOIN pt4_import_attempts pia ON pff.pt4_import_attempt_id = pia.id
            WHERE pff.associated_job_id = ?
            ORDER BY pff.created_at DESC
            """,
            (job_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_all_pt4_failed_files() -> List[Dict]:
    """Get all PT4 failed files across all jobs"""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT pff.*, pia.import_log, pia.parsed_at, j.created_at as job_created_at
            FROM pt4_failed_files pff
            JOIN pt4_import_attempts pia ON pff.pt4_import_attempt_id = pia.id
            LEFT JOIN jobs j ON pff.associated_job_id = j.id
            ORDER BY pff.created_at DESC
            """
        )
        return [dict(row) for row in cursor.fetchall()]


def get_app_failed_files_for_job(job_id: int) -> List[Dict]:
    """
    Get app-detected failed files (with unmapped IDs) for a job

    Args:
        job_id: Job ID to query

    Returns:
        List of dicts with table name and unmapped_ids
    """
    result = get_result(job_id)
    if not result or not result.get('stats_json'):
        return []

    import json
    stats = json.loads(result['stats_json'])

    return stats.get('failed_files', [])
