# Unified Failed Files Reprocessing System

**Date**: November 4, 2025
**Status**: Design Approved
**Objective**: Enable users to reprocese ALL failed files from a job (both PT4 import failures and app processing failures) with unified UI, complete audit trail, and detailed logging.

---

## Problem Statement

Currently, GGRevealer tracks failed files from two separate sources:

1. **PT4 Failed Files** - Extracted from PokerTracker 4 import logs
2. **App Failed Files** - Detected during hand history processing (unmapped IDs)

However:
- Users can only reprocese PT4 failures via UI
- App failures (unmapped IDs) cannot be reprocesed from the UI
- No unified view of all failures across both sources
- No audit trail or attempt history

**Solution**: Create a unified reprocess system with two tabs (PT4 | App Processing), combined with complete attempt history and detailed logging.

---

## Solution Architecture

### 1. Database Schema

#### New Table: `reprocess_attempts`
Stores audit trail for every reprocess attempt.

```sql
CREATE TABLE reprocess_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    file_source TEXT NOT NULL,              -- 'pt4' | 'app'
    file_id INTEGER,                        -- ref to pt4_failed_files.id or results.id
    file_name TEXT NOT NULL,                -- e.g., "46798_resolved.txt" or table name
    attempt_number INTEGER NOT NULL,        -- 0-indexed: 0=initial, 1=first reprocess, etc
    status TEXT NOT NULL,                   -- 'pending', 'processing', 'success', 'failed'
    error_message TEXT,                     -- If status='failed', error details
    logs_json TEXT,                         -- Full processing logs (~150 lines)
    created_at TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
);

CREATE INDEX idx_reprocess_attempts_job ON reprocess_attempts(job_id);
CREATE INDEX idx_reprocess_attempts_status ON reprocess_attempts(status);
```

#### Modified Tables

**pt4_failed_files** - Add columns:
```sql
ALTER TABLE pt4_failed_files ADD COLUMN reprocess_count INTEGER DEFAULT 0;
ALTER TABLE pt4_failed_files ADD COLUMN last_reprocess_attempt_id INTEGER;
```

**results.stats_json** - New key (updated during app failure reprocessing):
```json
{
  "reprocess_history": [
    {
      "attempt_number": 1,
      "attempt_id": 42,
      "timestamp": "2025-11-04T14:30:00",
      "status": "success",
      "files_affected": ["46798", "46799"]
    }
  ]
}
```

---

### 2. API Endpoints

#### `GET /api/failed-files/{job_id}`
Returns unified view of all failures (both PT4 and app).

**Response**:
```json
{
  "job_id": 5,
  "pt4_failures": [
    {
      "id": 12,
      "filename": "46798_resolved.txt",
      "table_number": 46798,
      "error_count": 3,
      "errors": [
        "Validation error: hero count unchanged violated",
        "Error: pot size mismatch",
        "Error: unmapped IDs detected"
      ],
      "reprocess_count": 0,
      "last_reprocess_date": null,
      "status": "failed"
    }
  ],
  "app_failures": [
    {
      "table_name": "46798",
      "unmapped_ids": ["a1b2c3", "d4e5f6", "f7g8h9"],
      "unmapped_count": 3,
      "reprocess_count": 0,
      "last_reprocess_date": null,
      "status": "failed"
    }
  ],
  "total_pt4_failures": 2,
  "total_app_failures": 3,
  "total_failures": 5
}
```

---

#### `POST /api/reprocess/{job_id}`
Initiate reprocessing of selected failed files.

**Request**:
```json
{
  "files": [
    {"source": "pt4", "id": 12},
    {"source": "pt4", "id": 13},
    {"source": "app", "table_name": "46798"}
  ]
}
```

**Response**:
```json
{
  "reprocess_id": 45,
  "job_id": 5,
  "files_selected": 3,
  "status": "started",
  "estimated_time_seconds": 180
}
```

**Behavior**:
1. Validate all files exist and belong to job
2. Create `reprocess_attempts` row with status='pending'
3. Queue background task: `run_reprocess_pipeline(job_id, files, attempt_id)`
4. Return immediately to frontend

---

#### `GET /api/reprocess-history/{job_id}`
Return all reprocess attempts for a job with full logs.

**Response**:
```json
{
  "job_id": 5,
  "total_attempts": 2,
  "attempts": [
    {
      "id": 45,
      "attempt_number": 1,
      "file_source": "pt4",
      "file_name": "46798_resolved.txt",
      "status": "success",
      "created_at": "2025-11-04T14:30:00Z",
      "logs": "[14:30:00] Starting pipeline...\n[14:30:15] OCR1 success...\n..."
    },
    {
      "id": 44,
      "attempt_number": 0,
      "file_source": "app",
      "file_name": "46798",
      "status": "failed",
      "error_message": "Screenshot not found for hand ID 12345678",
      "created_at": "2025-11-04T10:15:00Z",
      "logs": "[10:15:00] Starting pipeline...\n[10:15:10] OCR1 failed: No hand ID...\n..."
    }
  ]
}
```

---

### 3. Frontend UI Components

#### Section: "Archivos Fallidos" (Tabbed)

**Layout**:
```
┌──────────────────────────────────────────────────┐
│ ARCHIVOS FALLIDOS                                │
├─────────────────┬──────────────────────────────┤
│ [PT4] | [Procesar]                             │
├──────────────────────────────────────────────────┤
│ ☐ 46798_resolved.txt                           │
│   Error: hero count unchanged violated          │
│   Reprocess attempts: 0                          │
│                                                  │
│ ☐ 46799_resolved.txt                           │
│   Error: unmapped IDs detected (3)              │
│   Reprocess attempts: 0                          │
│                                                  │
│ [Reprocesar Seleccionados (2)]  [Ver Historial]│
└──────────────────────────────────────────────────┘
```

**Behaviors**:
- Each tab (PT4 | App) shows relevant failures
- Checkboxes enable multi-select across tabs
- "Reprocesar" button disabled if no selection
- Click action:
  1. Disable button, show spinner
  2. POST to `/api/reprocess/{job_id}` with selected files
  3. Show success message with reprocess_id
  4. Auto-refresh status after 3 seconds
  5. Re-enable button

**PT4 Tab Fields**:
- Filename (e.g., "46798_resolved.txt")
- Error summary (human-readable)
- Reprocess count + last attempt date
- Checkbox

**App Processing Tab Fields**:
- Table name
- Unmapped IDs list
- Unmapped count
- Reprocess count + last attempt date
- Checkbox

---

#### Section: "Historial de Intentos"

**Layout**:
```
┌──────────────────────────────────────────────────┐
│ HISTORIAL DE INTENTOS                            │
├──────────────────────────────────────────────────┤
│ ▼ 2025-11-04 14:30 - Intento #1 [SUCCESS]       │
│    Archivos: 46798_resolved.txt (PT4)            │
│    Duración: 2m 30s                              │
│    [Ver Logs Completos (150 líneas)]             │
│                                                  │
│ ▼ 2025-11-04 10:15 - Intento #0 (Inicial) [FAIL]│
│    Razón: Screenshot not found for hand ID      │
│    Archivos: 46798 (App)                         │
│    [Ver Logs Completos]                          │
└──────────────────────────────────────────────────┘
```

**Behaviors**:
- Timeline format, newest first
- Click row to expand/collapse
- Expand shows:
  - Full error message (if failed)
  - Affected files list
  - Duration
  - Log viewer (copyable, scrollable)
- "Ver Logs" opens modal with full logs

---

### 4. Backend Processing Logic

#### `run_reprocess_pipeline(job_id, files, attempt_id)`

**Steps** (executed in background):

1. **Update attempt status** → `processing`

2. **For each selected file**:
   - Determine file type (PT4 or App)
   - Load original TXT file from storage
   - Re-run full pipeline:
     - Phase 1: OCR1 (extract hand IDs)
     - Phase 2: Match by hand ID
     - Phase 3: OCR2 (extract player names)
     - Phase 4: Generate output TXT
   - Capture all logs

3. **Validate output**:
   - Check if still has unmapped IDs
   - If no unmapped IDs → mark as `_resolved.txt`
   - If has unmapped IDs → mark as `_fallado.txt`

4. **Update database**:
   - `reprocess_attempts.status = 'success'` + `logs_json`
   - `pt4_failed_files.reprocess_count += 1` (if PT4)
   - `pt4_failed_files.last_reprocess_attempt_id = attempt_id`
   - Regenerate output ZIPs

5. **Handle failures**:
   - If any step fails → `reprocess_attempts.status = 'failed'` + error message
   - Do NOT lose original output files
   - Log error with full stack trace

---

#### Database Migrations (backward compatible)

```python
def migrate_reprocess_tables():
    """Add reprocess audit tables and update existing columns"""
    db = get_db()
    cursor = db.cursor()

    # Create new reprocess_attempts table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reprocess_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            file_source TEXT NOT NULL,
            file_id INTEGER,
            file_name TEXT NOT NULL,
            attempt_number INTEGER NOT NULL,
            status TEXT NOT NULL,
            error_message TEXT,
            logs_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
        )
    ''')

    # Update pt4_failed_files if columns don't exist
    cursor.execute("PRAGMA table_info(pt4_failed_files)")
    columns = {row[1] for row in cursor.fetchall()}

    if 'reprocess_count' not in columns:
        cursor.execute('''
            ALTER TABLE pt4_failed_files
            ADD COLUMN reprocess_count INTEGER DEFAULT 0
        ''')

    if 'last_reprocess_attempt_id' not in columns:
        cursor.execute('''
            ALTER TABLE pt4_failed_files
            ADD COLUMN last_reprocess_attempt_id INTEGER
        ''')

    db.commit()
```

---

## Implementation Order

1. **Database** - Schema migrations
2. **API Endpoints** - GET /failed-files, POST /reprocess, GET /reprocess-history
3. **Backend Logic** - run_reprocess_pipeline function
4. **Frontend** - Two-tab UI + history section
5. **Testing** - Unit tests for pipeline, integration tests for endpoints

---

## Success Criteria

- ✅ Users can reprocese BOTH PT4 and App failures from single UI
- ✅ Two separate tabs showing distinct failure sources
- ✅ Complete audit trail: every attempt logged with full logs
- ✅ Reprocess attempts show in history with timestamps
- ✅ Pipeline re-runs full OCR + matching for each file
- ✅ Output ZIPs regenerated after successful reprocess
- ✅ Backward compatible (no data loss)

---

## Known Constraints

- Reprocess attempts will re-use existing screenshots (user can't add new ones)
- Pipeline executes sequentially (no parallel batch processing within single reprocess)
- Logs limited to ~150 lines per attempt (truncate if longer)
- PT4 failures must have `table_number` extractable from filename
