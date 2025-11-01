# Error Recovery System - Integration Guide
**Date**: 2025-11-01
**Status**: Design Complete - Ready for Integration

## Overview

This document explains how to integrate the error recovery modules into the existing GGRevealer system.

**Completed Modules** (Tasks 1-4):
- ✅ `error_parser.py` - Parse PT4 error logs
- ✅ `error_analyzer.py` - Gemini AI analysis
- ✅ `repair_strategy.py` - Generate repair plans
- ✅ `repair_executor.py` - Execute repairs

**Integration Required** (Tasks 5-6):
- 📋 API endpoints in `main.py`
- 📋 Frontend UI in `templates/index.html` and `static/js/app.js`

---

## Task 5: API Endpoints Integration

### Add to `main.py`

```python
# Import error recovery modules
from error_parser import parse_error_log, map_errors_to_files
from error_analyzer import analyze_errors_with_gemini
from repair_strategy import generate_repair_plan
from repair_executor import RepairExecutor

# ==========================================
# ERROR RECOVERY ENDPOINTS
# ==========================================

@app.post("/api/fix-errors/{job_id}")
async def analyze_pt4_errors(
    job_id: int,
    error_log: str = Form(...)
):
    """
    Step 1: Analyze PT4 error log and generate repair plan

    User pastes PT4 error log, system:
    1. Parses errors
    2. Analyzes with Gemini AI
    3. Generates repair plan
    4. Returns plan for user review

    Does NOT execute repairs - user must approve first.
    """
    try:
        # Parse error log
        errors = parse_error_log(error_log)

        if not errors:
            return JSONResponse({
                "status": "no_errors_found",
                "message": "No PT4 errors found in log"
            })

        # Map errors to files
        errors_by_file = map_errors_to_files(job_id, errors, db)

        # Analyze with Gemini
        analyses = await analyze_errors_with_gemini(
            job_id=job_id,
            errors=errors_by_file,
            db_connection=db
        )

        # Generate repair plan
        repair_plan = generate_repair_plan(
            job_id=job_id,
            errors=errors_by_file,
            analyses=analyses
        )

        # Store plan in database for later execution
        plan_id = db.save_repair_plan(job_id, repair_plan)

        # Return plan for user review
        return JSONResponse({
            "status": "plan_ready",
            "plan_id": plan_id,
            "repair_plan": {
                "total_errors": repair_plan.total_errors,
                "high_confidence_fixes": repair_plan.high_confidence_fixes,
                "medium_confidence_fixes": repair_plan.medium_confidence_fixes,
                "low_confidence_fixes": repair_plan.low_confidence_fixes,
                "estimated_success_rate": repair_plan.estimated_success_rate,
                "actions": [
                    {
                        "error_id": a.error_id,
                        "action_type": a.action_type,
                        "affected_phase": a.affected_phase,
                        "confidence": a.confidence,
                        "gemini_suggested": a.gemini_suggested
                    }
                    for a in repair_plan.execution_order
                ]
            }
        })

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@app.post("/api/execute-repairs/{job_id}")
async def execute_repair_plan(
    job_id: int,
    plan_id: str = Form(...)
):
    """
    Step 2: Execute approved repair plan

    User has reviewed plan and clicked "Approve & Apply Fixes".
    System executes all repairs and returns results.
    """
    try:
        # Load repair plan from database
        repair_plan = db.get_repair_plan(plan_id)

        if not repair_plan:
            return JSONResponse({
                "status": "error",
                "message": "Repair plan not found"
            }, status_code=404)

        # Execute repairs
        executor = RepairExecutor(db=db, api_key=os.getenv("GEMINI_API_KEY"))

        results = await executor.execute_repair_plan(
            job_id=job_id,
            repair_plan=repair_plan,
            user_approved=True  # User clicked approve
        )

        # Store results
        db.save_repair_results(job_id, plan_id, results)

        return JSONResponse({
            "status": "completed",
            "results": {
                "total_executed": results["total_executed"],
                "success_count": results["success_count"],
                "failed_count": results["failed_count"],
                "success_rate": results["success_rate"],
                "modified_files": results["modified_files"]
            }
        })

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)


@app.get("/api/download-repaired/{job_id}")
async def download_repaired_files(job_id: int):
    """
    Step 3: Download repaired files

    Returns ZIP with all repaired hand history files.
    """
    try:
        # Get repaired files from storage
        zip_path = f"storage/outputs/{job_id}/repaired_hands.zip"

        if not os.path.exists(zip_path):
            return JSONResponse({
                "status": "error",
                "message": "Repaired files not found"
            }, status_code=404)

        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"repaired_hands_job{job_id}.zip"
        )

    except Exception as e:
        return JSONResponse({
            "status": "error",
            "message": str(e)
        }, status_code=500)
```

---

## Task 6: Frontend UI Integration

### Add to `templates/index.html`

Add this section after the existing job processing UI:

```html
<!-- ERROR RECOVERY SECTION -->
<div id="errorRecoverySection" class="card mt-4" style="display: none;">
  <div class="card-header bg-warning">
    <h5>🔧 Error Recovery System</h5>
    <small class="text-muted">Fix PokerTracker import errors with AI assistance</small>
  </div>

  <div class="card-body">

    <!-- Step 1: Paste Error Log -->
    <div id="step1-paste" class="step">
      <h6>Step 1: Paste PokerTracker Error Log</h6>
      <textarea
        id="errorLogInput"
        class="form-control"
        rows="8"
        placeholder="Paste error log from PokerTracker here...

Example:
Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247401164) (Line #46)
Error: GG Poker: Invalid pot size: Expected $45.50, found $44.00 (Hand #RC3247401165) (Line #12)"
      ></textarea>

      <button
        id="analyzeErrorsBtn"
        class="btn btn-warning mt-3"
        onclick="analyzeErrors()"
      >
        <i class="fas fa-brain"></i> Analyze Errors with AI
      </button>
    </div>

    <!-- Step 2: Review Repair Plan -->
    <div id="step2-review" class="step" style="display: none;">
      <h6>Step 2: Review Repair Plan</h6>

      <div class="alert alert-info">
        <strong>AI Analysis Complete!</strong>
        <div id="planSummary"></div>
      </div>

      <div id="actionsList" class="list-group mb-3">
        <!-- Populated by JavaScript -->
      </div>

      <button
        id="approvePlanBtn"
        class="btn btn-success"
        onclick="executeRepairs()"
      >
        ✅ Approve & Apply Fixes
      </button>

      <button
        class="btn btn-secondary"
        onclick="cancelRepairs()"
      >
        Cancel
      </button>
    </div>

    <!-- Step 3: Execution Progress -->
    <div id="step3-executing" class="step" style="display: none;">
      <h6>Step 3: Applying Fixes...</h6>
      <div class="progress">
        <div id="repairProgress" class="progress-bar progress-bar-striped progress-bar-animated"
          style="width: 0%"></div>
      </div>
      <div id="executionLog" class="mt-3 bg-light p-3" style="max-height: 300px; overflow-y: auto;">
        <!-- Execution logs appear here -->
      </div>
    </div>

    <!-- Step 4: Results -->
    <div id="step4-results" class="step" style="display: none;">
      <h6>Step 4: Repair Results</h6>

      <div class="row">
        <div class="col-md-3">
          <div class="card text-center">
            <div class="card-body">
              <h3 id="successRate" class="text-success">0%</h3>
              <p class="text-muted">Success Rate</p>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card text-center">
            <div class="card-body">
              <h3 id="fixedCount" class="text-info">0</h3>
              <p class="text-muted">Errors Fixed</p>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card text-center">
            <div class="card-body">
              <h3 id="failedCount" class="text-danger">0</h3>
              <p class="text-muted">Failed</p>
            </div>
          </div>
        </div>
        <div class="col-md-3">
          <div class="card text-center">
            <div class="card-body">
              <h3 id="filesModified" class="text-warning">0</h3>
              <p class="text-muted">Files Modified</p>
            </div>
          </div>
        </div>
      </div>

      <button
        id="downloadRepairedBtn"
        class="btn btn-success mt-3"
        onclick="downloadRepairedFiles()"
      >
        <i class="fas fa-download"></i> Download Repaired Files
      </button>
    </div>

  </div>
</div>
```

### Add to `static/js/app.js`

```javascript
// ==========================================
// ERROR RECOVERY FUNCTIONS
// ==========================================

let currentJobId = null;
let currentPlanId = null;

function showErrorRecovery(jobId) {
  /**
   * Show error recovery section for a completed job
   */
  currentJobId = jobId;
  document.getElementById('errorRecoverySection').style.display = 'block';

  // Reset to step 1
  showStep('step1-paste');
}

function analyzeErrors() {
  /**
   * Step 1: Analyze PT4 error log with AI
   */
  const errorLog = document.getElementById('errorLogInput').value;

  if (!errorLog.trim()) {
    alert('Please paste an error log first');
    return;
  }

  const analyzeBtn = document.getElementById('analyzeErrorsBtn');
  analyzeBtn.disabled = true;
  analyzeBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';

  // Call API
  fetch(`/api/fix-errors/${currentJobId}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: `error_log=${encodeURIComponent(errorLog)}`
  })
  .then(response => response.json())
  .then(data => {
    analyzeBtn.disabled = false;
    analyzeBtn.innerHTML = '<i class="fas fa-brain"></i> Analyze Errors with AI';

    if (data.status === 'plan_ready') {
      currentPlanId = data.plan_id;
      displayRepairPlan(data.repair_plan);
      showStep('step2-review');
    } else {
      alert(`Analysis failed: ${data.message || 'Unknown error'}`);
    }
  })
  .catch(error => {
    analyzeBtn.disabled = false;
    analyzeBtn.innerHTML = '<i class="fas fa-brain"></i> Analyze Errors with AI';
    alert(`Error: ${error.message}`);
  });
}

function displayRepairPlan(plan) {
  /**
   * Display repair plan for user review
   */
  // Summary
  const summary = document.getElementById('planSummary');
  summary.innerHTML = `
    <ul class="mb-0">
      <li>Total Errors: <strong>${plan.total_errors}</strong></li>
      <li>High Confidence Fixes (>80%): <strong>${plan.high_confidence_fixes}</strong></li>
      <li>Medium Confidence (50-80%): <strong>${plan.medium_confidence_fixes}</strong></li>
      <li>Low Confidence (<50%): <strong>${plan.low_confidence_fixes}</strong></li>
      <li>Estimated Success Rate: <strong>${(plan.estimated_success_rate * 100).toFixed(1)}%</strong></li>
    </ul>
  `;

  // Actions list
  const actionsList = document.getElementById('actionsList');
  actionsList.innerHTML = '';

  for (const action of plan.actions) {
    const confidenceClass = action.confidence > 0.8 ? 'success'
      : action.confidence > 0.5 ? 'warning' : 'danger';

    const item = document.createElement('div');
    item.className = `list-group-item list-group-item-${confidenceClass}`;
    item.innerHTML = `
      <div class="d-flex justify-content-between align-items-start">
        <div>
          <h6 class="mb-1">Hand: <code>${action.error_id}</code></h6>
          <p class="mb-1">${action.gemini_suggested}</p>
          <small><strong>Phase:</strong> ${action.affected_phase} | <strong>Action:</strong> ${action.action_type}</small>
        </div>
        <div>
          <span class="badge bg-${confidenceClass}">${(action.confidence * 100).toFixed(0)}%</span>
        </div>
      </div>
    `;
    actionsList.appendChild(item);
  }
}

function executeRepairs() {
  /**
   * Step 3: Execute approved repair plan
   */
  if (!confirm('Are you sure you want to apply these fixes?')) {
    return;
  }

  showStep('step3-executing');

  // Call API
  fetch(`/api/execute-repairs/${currentJobId}`, {
    method: 'POST',
    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
    body: `plan_id=${currentPlanId}`
  })
  .then(response => response.json())
  .then(data => {
    if (data.status === 'completed') {
      displayRepairResults(data.results);
      showStep('step4-results');
    } else {
      alert(`Execution failed: ${data.message || 'Unknown error'}`);
    }
  })
  .catch(error => {
    alert(`Error: ${error.message}`);
  });
}

function displayRepairResults(results) {
  /**
   * Display repair execution results
   */
  document.getElementById('successRate').textContent =
    `${(results.success_rate * 100).toFixed(1)}%`;
  document.getElementById('fixedCount').textContent = results.success_count;
  document.getElementById('failedCount').textContent = results.failed_count;
  document.getElementById('filesModified').textContent = results.modified_files.length;
}

function downloadRepairedFiles() {
  /**
   * Download repaired files ZIP
   */
  window.location.href = `/api/download-repaired/${currentJobId}`;
}

function cancelRepairs() {
  /**
   * Cancel and return to step 1
   */
  showStep('step1-paste');
  document.getElementById('errorLogInput').value = '';
}

function showStep(stepId) {
  /**
   * Show specific step, hide others
   */
  const steps = ['step1-paste', 'step2-review', 'step3-executing', 'step4-results'];
  steps.forEach(id => {
    document.getElementById(id).style.display = id === stepId ? 'block' : 'none';
  });
}
```

---

## Database Schema Updates

Add these tables to `database.py`:

```sql
CREATE TABLE IF NOT EXISTS repair_plans (
    id TEXT PRIMARY KEY,
    job_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_log TEXT,
    plan_json TEXT,
    status TEXT DEFAULT 'pending',
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS repair_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_plan_id TEXT,
    error_id TEXT,
    action_type TEXT,
    affected_phase TEXT,
    confidence REAL,
    action_params TEXT,
    execution_status TEXT DEFAULT 'pending',
    execution_result TEXT,
    executed_at TIMESTAMP,
    FOREIGN KEY (repair_plan_id) REFERENCES repair_plans(id)
);

CREATE TABLE IF NOT EXISTS repaired_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    original_file_id INTEGER,
    repaired_content TEXT,
    repair_plan_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (repair_plan_id) REFERENCES repair_plans(id)
);
```

---

## Testing the Integration

### 1. Upload Files & Process Job

```bash
# Normal workflow
1. Upload TXT files + screenshots
2. Process job
3. Download results
```

### 2. Test Error Recovery

```bash
# If PT4 rejects files
1. Try importing to PT4
2. Copy error log from PT4 dialog
3. Go back to GGRevealer job page
4. Click "Error Recovery" button
5. Paste error log
6. Click "Analyze Errors with AI"
7. Review repair plan
8. Click "Approve & Apply Fixes"
9. Download repaired files
10. Import to PT4 (should work now!)
```

---

## Success Metrics

After implementing Tasks 5-6, the system should:

- ✅ Accept PT4 error logs via UI
- ✅ Parse errors automatically
- ✅ Analyze with Gemini AI
- ✅ Show repair plan with confidence scores
- ✅ Require user approval before executing
- ✅ Execute repairs and validate
- ✅ Provide downloadable repaired files
- ✅ Track success/failure statistics

**Expected Results:**
- Fix 85%+ of duplicate player errors
- Fix 70%+ of pot calculation errors
- Overall success rate: 80%+

---

## Next Steps

1. **Implement API endpoints** in `main.py` (copy from this document)
2. **Implement frontend UI** in `templates/index.html` and `static/js/app.js`
3. **Add database migrations** for new tables
4. **Test end-to-end** with real PT4 error logs
5. **Deploy to staging** for user testing

---

**Document Version**: 1.0
**Last Updated**: 2025-11-01
**Status**: Ready for Implementation
