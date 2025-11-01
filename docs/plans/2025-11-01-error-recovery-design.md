# Error Recovery System Design Document
**Date**: 2025-11-01
**Author**: Claude Code
**Status**: Design Complete - Ready for Implementation

## Executive Summary

This document outlines the design for a **PokerTracker Error Recovery System** that allows users to upload PT4 error logs, have AI analyze the root causes, and automatically fix the errors in their hand history files. The system reuses data from previous jobs and applies surgical fixes only where needed.

**Key Features**:
- Parse PT4 error logs to identify failing hands
- Use Gemini AI to analyze root causes with full job context
- Generate confidence-scored repair plans
- User reviews and approves plan before execution
- Apply phase-specific fixes (parser, matcher, OCR, writer)
- Validate repairs with PT4 validator
- Generate comprehensive report

---

## 1. Problem Statement

### Current Situation
When users import GGRevealer-processed files to PokerTracker 4:
- PT4 rejects ~22% of files with errors
- Common errors: duplicate players, invalid pots, unmapped IDs
- Users must manually identify and fix errors
- No automated recovery mechanism

### Example PT4 Error
```
Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247401164) (Line #46)
Error: GG Poker: Invalid pot size: Expected $45.50, found $44.00 (Hand #RC3247401165)
Error: GG Poker: Unmapped ID: a4c8f2 in file 43746_resolved.txt (Line #12)
```

### Solution Requirements
1. Parse error logs from PT4
2. Identify root cause of each error
3. Apply targeted fixes without full reprocessing
4. User approval before applying fixes
5. Validate that fixes work

---

## 2. Architecture Overview

### System Components

```
┌─────────────────┐
│   User Upload   │
│  PT4 Error Log  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│  Error Parser   │────▶│ PTError      │
│  (error_parser) │     │ Objects      │
└────────┬────────┘     └──────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│ Gemini Analyzer │────▶│ ErrorAnalysis│
│(error_analyzer) │     │ Objects      │
└────────┬────────┘     └──────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│ Repair Planner  │────▶│ RepairPlan   │
│(repair_strategy)│     │ Object       │
└────────┬────────┘     └──────────────┘
         │
         ▼
┌─────────────────┐
│  User Reviews   │
│  & Approves     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│ Repair Executor │────▶│ Fixed Files  │
│(repair_executor)│     │              │
└────────┬────────┘     └──────────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│   Validator     │────▶│   Report     │
│                 │     │              │
└─────────────────┘     └──────────────┘
```

### Data Flow

1. **Input**: PT4 error log (text)
2. **Parse**: Extract structured error objects
3. **Analyze**: Gemini determines root causes
4. **Plan**: Generate ordered repair actions
5. **Review**: User sees plan with confidence scores
6. **Execute**: Apply phase-specific fixes
7. **Validate**: Check fixes with PT4 validator
8. **Output**: ZIP with repaired files

---

## 3. Detailed Component Design

### 3.1 Error Parser Module (`error_parser.py`)

**Purpose**: Parse unstructured PT4 error logs into structured objects

**Data Structures**:
```python
@dataclass
class PTError:
    hand_id: str                    # "SG3247401164"
    error_type: str                 # "duplicate_player"
    player_name: Optional[str]      # "TuichAAreko"
    seats_involved: List[int]       # [2, 3]
    line_number: int                # 46
    raw_message: str                # Full error line
    filename: Optional[str] = None  # "43746_resolved.txt"
```

**Error Type Patterns**:
| Error Type | Pattern | Example |
|------------|---------|---------|
| duplicate_player | `Duplicate player: (\w+).*seat (\d+).*seat (\d+)` | TuichAAreko in seat 2 and 3 |
| invalid_pot | `Invalid pot.*Expected \$([0-9.]+).*found \$([0-9.]+)` | Expected $45.50, found $44.00 |
| unmapped_id | `Unmapped ID: ([a-f0-9]{6,8})` | Unmapped ID: a4c8f2 |
| missing_blind | `Missing (small\|big) blind` | Missing small blind |
| invalid_stack | `Invalid stack.*seat (\d+)` | Invalid stack for seat 1 |

**Key Functions**:
- `parse_error_log(text: str) -> List[PTError]`
- `map_errors_to_files(job_id: int, errors: List[PTError]) -> Dict[str, List[PTError]]`

---

### 3.2 Error Analyzer Module (`error_analyzer.py`)

**Purpose**: Use Gemini AI to analyze root causes with full job context

**Data Structures**:
```python
@dataclass
class ErrorAnalysis:
    error_type: str         # "duplicate_player"
    root_cause: str         # "Screenshot matched to wrong hand"
    affected_phase: str     # "matcher"
    confidence: float       # 0.95
    suggested_fix: str      # "Remove seat 3 mapping"
    auto_fixable: bool      # True
    fix_code: str          # Specific repair action
```

**Gemini Prompt Structure**:
```
You are analyzing PokerTracker import errors.

CONTEXT:
- Parsed hands: {json of hands structure}
- OCR results: {extracted player names}
- Current mappings: {anon_id → real_name}
- Errors: {error log}

For each error, determine:
1. Root cause (why did this happen?)
2. Which phase failed (parser/matcher/ocr/writer)
3. How to fix it (specific action)
4. Confidence (0.0-1.0)
5. Can system auto-fix? (yes/no)
```

**Key Functions**:
- `analyze_errors_with_gemini(job_id, errors) -> Dict[str, ErrorAnalysis]`

---

### 3.3 Repair Strategy Module (`repair_strategy.py`)

**Purpose**: Generate executable repair plan with confidence scoring

**Data Structures**:
```python
@dataclass
class RepairAction:
    error_id: str           # "SG3247401164"
    action_type: str        # "remove_duplicate_mapping"
    affected_phase: str     # "matcher"
    confidence: float       # 0.95
    auto_executable: bool   # True
    action_params: Dict     # {"seat": 3, "name": "TuichAAreko"}
    gemini_suggested: str   # Human-readable description

@dataclass
class RepairPlan:
    actions: List[RepairAction]
    execution_order: List[str]  # Topologically sorted
    total_errors: int
    high_confidence_fixes: int   # > 0.8
    medium_confidence_fixes: int # 0.5-0.8
    low_confidence_fixes: int    # < 0.5
    estimated_success_rate: float
```

**Confidence Thresholds**:
- **High (>0.8)**: Auto-apply without question
- **Medium (0.5-0.8)**: Auto-apply but flag in report
- **Low (<0.5)**: Require manual review

**Key Functions**:
- `generate_repair_plan(job_id, errors, analyses) -> RepairPlan`

---

### 3.4 Repair Executor Module (`repair_executor.py`)

**Purpose**: Execute repairs with phase-specific strategies

**Phase-Specific Repairs**:

| Phase | Common Actions | Strategy |
|-------|---------------|----------|
| **Parser** | Fix pot calculations, blind amounts | Re-parse with corrections |
| **Matcher** | Remove duplicate mappings, rematch | Clear and rematch with constraints |
| **OCR** | Re-run with hints | OCR2 with role hints |
| **Writer** | Regenerate with fixed mappings | Apply corrected mappings |

**Key Functions**:
- `execute_repair_plan(job_id, plan, approved=True) -> Dict`
- `_repair_matching(job_id, action) -> Dict`
- `_repair_writer(job_id, action) -> Dict`
- `_repair_parser(job_id, action) -> Dict`
- `_repair_ocr(job_id, action) -> Dict`

**Example: Duplicate Player Fix**:
```python
# Action to fix duplicate player
action = RepairAction(
    error_id="SG3247401164",
    action_type="remove_duplicate_mapping",
    affected_phase="matcher",
    action_params={
        "hand_id": "SG3247401164",
        "seat": 3,
        "player_name": "TuichAAreko"
    }
)

# Execution
1. Load current mapping for hand
2. Find anonymized ID for seat 3
3. Remove that mapping entry
4. Regenerate TXT file
5. Validate with PT4 validator
```

---

## 4. API Endpoints

### 4.1 Analyze Errors
```python
POST /api/fix-errors/{job_id}
Body: {
    "error_log": "Error: GG Poker: Duplicate..."
}

Response: {
    "status": "plan_ready",
    "repair_plan": {
        "actions": [...],
        "total_errors": 5,
        "high_confidence_fixes": 4,
        "estimated_success_rate": 0.85
    }
}
```

### 4.2 Execute Repairs
```python
POST /api/execute-repairs/{job_id}
Body: {
    "repair_plan_id": "plan_123",
    "user_approved": true
}

Response: {
    "status": "complete",
    "results": {
        "executed_actions": 4,
        "failed_actions": 1,
        "modified_files": 3,
        "success_rate": 0.8
    },
    "download_path": "/api/download-repaired/{job_id}"
}
```

### 4.3 Download Repaired Files
```python
GET /api/download-repaired/{job_id}

Response: ZIP file with repaired hand histories
```

---

## 5. User Interface Design

### 5.1 Error Recovery Workflow

```
┌────────────────────────────────┐
│  Step 1: Paste Error Log       │
│  ┌────────────────────────┐    │
│  │ [Textarea for errors]  │    │
│  └────────────────────────┘    │
│  [Analyze Errors]              │
└────────────────────────────────┘
                ↓
┌────────────────────────────────┐
│  Step 2: Analyzing...          │
│  [Progress Bar]                │
│  "Analyzing with AI..."        │
└────────────────────────────────┘
                ↓
┌────────────────────────────────┐
│  Step 3: Review Repair Plan    │
│  ┌────────────────────────┐    │
│  │ Summary:                │    │
│  │ • 5 errors found        │    │
│  │ • 4 high confidence     │    │
│  │ • 85% success rate      │    │
│  └────────────────────────┘    │
│  ┌────────────────────────┐    │
│  │ Actions List:          │    │
│  │ 1. Fix duplicate [95%] │    │
│  │ 2. Fix pot [88%]       │    │
│  └────────────────────────┘    │
│  [Approve] [Cancel]            │
└────────────────────────────────┘
                ↓
┌────────────────────────────────┐
│  Step 4: Applying Fixes...     │
│  [Execution Log]               │
│  "✓ Fixed duplicate in SG324..." │
│  "✓ Recalculated pot..."       │
└────────────────────────────────┘
                ↓
┌────────────────────────────────┐
│  Step 5: Results               │
│  ┌────────────────────────┐    │
│  │ Success: 4/5 fixed      │    │
│  │ Files regenerated: 3    │    │
│  └────────────────────────┘    │
│  [Download Repaired Files]     │
└────────────────────────────────┘
```

### 5.2 Repair Plan Display

Each action shows:
- Hand ID affected
- Error description
- Suggested fix
- Confidence score (color-coded)
- Auto-fix indicator

**Color Coding**:
- 🟢 Green: High confidence (>80%)
- 🟡 Yellow: Medium confidence (50-80%)
- 🔴 Red: Low confidence (<50%)

---

## 6. Database Schema Updates

### New Tables

```sql
-- Store repair plans
CREATE TABLE repair_plans (
    id TEXT PRIMARY KEY,
    job_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_log TEXT,
    plan_json TEXT,
    status TEXT,  -- 'pending', 'approved', 'executed'
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

-- Store repair actions and results
CREATE TABLE repair_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_plan_id TEXT,
    error_id TEXT,
    action_type TEXT,
    affected_phase TEXT,
    confidence REAL,
    action_params TEXT,  -- JSON
    execution_status TEXT,  -- 'pending', 'success', 'failed'
    execution_result TEXT,  -- JSON
    executed_at TIMESTAMP,
    FOREIGN KEY (repair_plan_id) REFERENCES repair_plans(id)
);

-- Store repaired file versions
CREATE TABLE repaired_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER,
    original_file_id INTEGER,
    repaired_content TEXT,
    repair_plan_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(id),
    FOREIGN KEY (original_file_id) REFERENCES files(id),
    FOREIGN KEY (repair_plan_id) REFERENCES repair_plans(id)
);
```

---

## 7. Implementation Plan

### Phase 1: Core Modules (3-4 hours)
1. Implement `error_parser.py` with regex patterns
2. Implement `error_analyzer.py` with Gemini integration
3. Implement `repair_strategy.py` with confidence scoring
4. Write unit tests for each module

### Phase 2: Repair Executor (2-3 hours)
1. Implement `repair_executor.py` base class
2. Add phase-specific repair methods
3. Integrate with existing pipeline modules
4. Test with sample errors

### Phase 3: API Endpoints (2 hours)
1. Add `/api/fix-errors/{job_id}` endpoint
2. Add `/api/execute-repairs/{job_id}` endpoint
3. Add `/api/download-repaired/{job_id}` endpoint
4. Test with Postman/curl

### Phase 4: Frontend UI (2-3 hours)
1. Add error recovery section to `/app`
2. Implement 5-step workflow
3. Add JavaScript for plan display
4. Test end-to-end flow

### Phase 5: Validation & Testing (2 hours)
1. Integrate PT4 validator
2. Test with real PT4 error logs
3. Verify fixes work in PT4
4. Document edge cases

**Total Estimate**: 11-14 hours

---

## 8. Testing Strategy

### Unit Tests
- Test error parsing with various PT4 formats
- Test Gemini prompt generation
- Test repair action generation
- Test phase-specific repairs

### Integration Tests
- Test full workflow with mock data
- Test with real job data
- Test validation after repairs
- Test error handling

### End-to-End Tests
1. Upload real PT4 error log
2. Review generated plan
3. Execute repairs
4. Download fixed files
5. Import to PT4 successfully

---

## 9. Risk Analysis

### Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Gemini misidentifies root cause | Wrong fix applied | Confidence scoring + user review |
| Repair breaks valid hands | PT4 rejects more | Validate all repairs before saving |
| Infinite repair loops | System hangs | Max retry limit per error |
| Data loss during repair | Lost hand histories | Work on copies, keep originals |

---

## 10. Success Metrics

- **Primary**: % of PT4 errors successfully fixed
- **Secondary**: Average confidence score of fixes
- **Tertiary**: Time saved vs manual fixing

**Target Goals**:
- Fix 85% of duplicate player errors
- Fix 70% of pot calculation errors
- Fix 95% of unmapped ID errors
- Overall success rate: 80%+

---

## 11. Future Enhancements

1. **Machine Learning**: Learn from successful repairs to improve confidence
2. **Batch Processing**: Fix multiple jobs at once
3. **Preemptive Detection**: Detect potential PT4 errors before export
4. **Auto-Retry**: Automatically retry failed repairs with different strategies
5. **Error Prevention**: Modify main pipeline to prevent common errors

---

## Appendix A: Common PT4 Error Types

| Error | Frequency | Root Cause | Fix Strategy |
|-------|-----------|------------|--------------|
| Duplicate player | 40% | Wrong screenshot match | Remove duplicate mapping |
| Invalid pot | 25% | Cash Drop not calculated | Recalculate with fees |
| Unmapped ID | 20% | Missing screenshot | Mark as unresolved |
| Missing blind | 10% | Parser error | Re-parse with correction |
| Invalid stack | 5% | OCR misread | Re-run OCR or manual fix |

---

## Appendix B: Example Repair Scenarios

### Scenario 1: Duplicate Player
```
Error: Duplicate player: TuichAAreko (seat 3) same as seat 2
Root Cause: Screenshot matched to wrong hand
Fix: Remove seat 3 mapping for TuichAAreko
Confidence: 95%
Result: Hand imports successfully
```

### Scenario 2: Invalid Pot
```
Error: Invalid pot size: Expected $45.50, found $44.00
Root Cause: Cash Drop fee not included (1BB on pots >30BB)
Fix: Add $1.50 jackpot fee to pot calculation
Confidence: 88%
Result: Pot validates correctly
```

### Scenario 3: Unmapped ID
```
Error: Unmapped ID: a4c8f2 in file
Root Cause: No screenshot contains this player
Fix: Cannot auto-fix, need screenshot
Confidence: N/A
Result: File remains in _fallado category
```

---

## Document History

- **2025-11-01**: Initial design created
- **Version**: 1.0
- **Status**: Ready for implementation
- **Next Step**: Create worktree and begin Phase 1 implementation