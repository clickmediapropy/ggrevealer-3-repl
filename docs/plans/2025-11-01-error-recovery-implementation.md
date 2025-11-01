# PT4 Error Recovery Implementation Plan
**Date**: 2025-11-01
**Branch**: feature/pt4-error-recovery
**Approach**: Test-Driven Development (TDD)

## Implementation Tasks

### Task 1: Error Parser Module
**Time**: 1.5 hours
**Files**: `error_parser.py`, `test_error_parser.py`

#### 1.1 Write Tests First (RED)
```python
# test_error_parser.py
def test_parse_duplicate_player_error():
    """Test parsing duplicate player error from PT4"""
    error_log = "Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247401164) (Line #46)"
    errors = parse_error_log(error_log)

    assert len(errors) == 1
    assert errors[0].hand_id == "SG3247401164"
    assert errors[0].error_type == "duplicate_player"
    assert errors[0].player_name == "TuichAAreko"
    assert errors[0].seats_involved == [2, 3]
    assert errors[0].line_number == 46

def test_parse_invalid_pot_error():
    """Test parsing invalid pot error"""
    error_log = "Error: GG Poker: Invalid pot size: Expected $45.50, found $44.00 (Hand #RC3247401165) (Line #12)"
    errors = parse_error_log(error_log)

    assert len(errors) == 1
    assert errors[0].hand_id == "RC3247401165"
    assert errors[0].error_type == "invalid_pot"
    assert errors[0].expected_pot == 45.50
    assert errors[0].found_pot == 44.00

def test_parse_unmapped_id_error():
    """Test parsing unmapped ID error"""
    error_log = "Error: GG Poker: Unmapped ID: a4c8f2 in file 43746_resolved.txt (Line #25)"
    errors = parse_error_log(error_log)

    assert len(errors) == 1
    assert errors[0].error_type == "unmapped_id"
    assert errors[0].unmapped_id == "a4c8f2"
    assert errors[0].filename == "43746_resolved.txt"

def test_parse_multiple_errors():
    """Test parsing multiple errors from log"""
    error_log = """
    Error: GG Poker: Duplicate player: Player1 (seat 2) the same as in seat 1 (Hand #SG111) (Line #10)
    Error: GG Poker: Invalid pot size: Expected $100, found $98 (Hand #SG112) (Line #20)
    Error: GG Poker: Unmapped ID: abc123 in file test.txt (Line #30)
    """
    errors = parse_error_log(error_log)

    assert len(errors) == 3
    assert errors[0].error_type == "duplicate_player"
    assert errors[1].error_type == "invalid_pot"
    assert errors[2].error_type == "unmapped_id"

def test_map_errors_to_files():
    """Test mapping errors to their source files"""
    # Mock database and file system
    job_id = 1
    errors = [
        PTError(hand_id="SG123", error_type="duplicate_player", ...),
        PTError(hand_id="SG124", error_type="invalid_pot", ...),
        PTError(hand_id="SG125", error_type="unmapped_id", ...),
    ]

    file_mapping = map_errors_to_files(job_id, errors)

    assert "table_12253_resolved.txt" in file_mapping
    assert len(file_mapping["table_12253_resolved.txt"]) == 2
```

#### 1.2 Implement Module (GREEN)
```python
# error_parser.py
import re
from dataclasses import dataclass
from typing import List, Optional, Dict

@dataclass
class PTError:
    hand_id: str
    error_type: str
    line_number: int
    raw_message: str
    # Error-specific fields
    player_name: Optional[str] = None
    seats_involved: Optional[List[int]] = None
    expected_pot: Optional[float] = None
    found_pot: Optional[float] = None
    unmapped_id: Optional[str] = None
    filename: Optional[str] = None

ERROR_PATTERNS = {
    "duplicate_player": {
        "pattern": r"Duplicate player: (\w+).*seat (\d+).*seat (\d+).*Hand #(\w+).*Line #(\d+)",
        "extract": lambda m: {
            "player_name": m.group(1),
            "seats_involved": [int(m.group(2)), int(m.group(3))],
            "hand_id": m.group(4),
            "line_number": int(m.group(5))
        }
    },
    "invalid_pot": {
        "pattern": r"Invalid pot.*Expected \$([0-9.]+).*found \$([0-9.]+).*Hand #(\w+).*Line #(\d+)",
        "extract": lambda m: {
            "expected_pot": float(m.group(1)),
            "found_pot": float(m.group(2)),
            "hand_id": m.group(3),
            "line_number": int(m.group(4))
        }
    },
    "unmapped_id": {
        "pattern": r"Unmapped ID: ([a-f0-9]{6,8}).*file (\w+\.txt).*Line #(\d+)",
        "extract": lambda m: {
            "unmapped_id": m.group(1),
            "filename": m.group(2),
            "line_number": int(m.group(3))
        }
    }
}

def parse_error_log(text: str) -> List[PTError]:
    """Parse PT4 error log into structured error objects"""
    errors = []

    for line in text.split('\n'):
        if "Error:" not in line:
            continue

        for error_type, config in ERROR_PATTERNS.items():
            match = re.search(config["pattern"], line)
            if match:
                extracted = config["extract"](match)
                error = PTError(
                    error_type=error_type,
                    raw_message=line.strip(),
                    **extracted
                )
                errors.append(error)
                break

    return errors
```

#### 1.3 Refactor & Optimize (REFACTOR)
- Add more error types
- Improve regex performance
- Add error grouping by type

---

### Task 2: Error Analyzer Module
**Time**: 2 hours
**Files**: `error_analyzer.py`, `test_error_analyzer.py`

#### 2.1 Write Tests First (RED)
```python
# test_error_analyzer.py
import pytest
from unittest.mock import Mock, patch

async def test_analyze_duplicate_player_error():
    """Test analyzing duplicate player error with Gemini"""
    job_id = 1
    errors = {
        "table_12253.txt": [
            PTError(
                hand_id="SG123",
                error_type="duplicate_player",
                player_name="TuichAAreko",
                seats_involved=[2, 3]
            )
        ]
    }

    with patch('error_analyzer.gemini_client') as mock_gemini:
        mock_gemini.analyze.return_value = {
            "SG123": {
                "root_cause": "Screenshot matched to wrong hand",
                "affected_phase": "matcher",
                "confidence": 0.95,
                "suggested_fix": "Remove seat 3 mapping for TuichAAreko",
                "auto_fixable": True
            }
        }

        analyses = await analyze_errors_with_gemini(job_id, errors)

        assert "SG123" in analyses
        assert analyses["SG123"].affected_phase == "matcher"
        assert analyses["SG123"].confidence == 0.95
        assert analyses["SG123"].auto_fixable == True

async def test_analyze_invalid_pot_error():
    """Test analyzing invalid pot error"""
    # Test Cash Drop detection
    # Test rake calculation issues
    pass

async def test_gemini_prompt_structure():
    """Test that Gemini prompt includes all required context"""
    # Verify prompt includes:
    # - Parsed hands
    # - OCR results
    # - Current mappings
    # - Error details
    pass
```

#### 2.2 Implement Module (GREEN)
```python
# error_analyzer.py
import json
from dataclasses import dataclass
from typing import Dict, List, Optional
import google.generativeai as genai

@dataclass
class ErrorAnalysis:
    error_type: str
    root_cause: str
    affected_phase: str  # parser, matcher, ocr, writer
    confidence: float  # 0.0 - 1.0
    suggested_fix: str
    auto_fixable: bool
    fix_code: Optional[str] = None

async def analyze_errors_with_gemini(
    job_id: int,
    errors: Dict[str, List[PTError]],
    db_connection
) -> Dict[str, ErrorAnalysis]:
    """Use Gemini to analyze PT4 errors with full job context"""

    # Load job context
    job_data = db_connection.get_job(job_id)
    parsed_hands = db_connection.get_parsed_hands(job_id)
    ocr_results = db_connection.get_ocr_results(job_id)
    current_mappings = db_connection.get_mappings(job_id)

    # Build Gemini prompt
    prompt = build_analysis_prompt(
        errors=errors,
        parsed_hands=parsed_hands,
        ocr_results=ocr_results,
        current_mappings=current_mappings
    )

    # Call Gemini
    model = genai.GenerativeModel('gemini-2.5-flash')
    response = await model.generate_content_async(prompt)

    # Parse response
    analyses = parse_gemini_response(response.text)

    return analyses

def build_analysis_prompt(errors, parsed_hands, ocr_results, current_mappings):
    """Build comprehensive Gemini prompt with all context"""
    return f"""
You are analyzing PokerTracker import errors for GGPoker hand histories.

CONTEXT:
- Parsed Hands: {json.dumps(parsed_hands, indent=2)}
- OCR Results: {json.dumps(ocr_results, indent=2)}
- Current Mappings: {json.dumps(current_mappings, indent=2)}

ERRORS TO ANALYZE:
{json.dumps(errors, indent=2)}

For EACH error, determine:
1. Root cause (why did this happen?)
2. Which phase failed (parser/matcher/ocr/writer)
3. How to fix it (specific action)
4. Confidence level (0.0-1.0)
5. Can system auto-fix? (true/false)

Output JSON format:
{{
  "hand_id": {{
    "root_cause": "explanation",
    "affected_phase": "matcher",
    "confidence": 0.95,
    "suggested_fix": "Remove seat 3 mapping",
    "auto_fixable": true,
    "fix_code": "specific_action_code"
  }}
}}
"""
```

---

### Task 3: Repair Strategy Module
**Time**: 1.5 hours
**Files**: `repair_strategy.py`, `test_repair_strategy.py`

#### 3.1 Write Tests First (RED)
```python
# test_repair_strategy.py
def test_generate_repair_plan():
    """Test generating repair plan from analyses"""
    analyses = {
        "SG123": ErrorAnalysis(
            error_type="duplicate_player",
            root_cause="Wrong match",
            affected_phase="matcher",
            confidence=0.95,
            suggested_fix="Remove seat 3",
            auto_fixable=True
        ),
        "SG124": ErrorAnalysis(
            error_type="invalid_pot",
            root_cause="Cash Drop",
            affected_phase="parser",
            confidence=0.88,
            suggested_fix="Add jackpot fee",
            auto_fixable=True
        )
    }

    plan = generate_repair_plan(job_id=1, analyses=analyses)

    assert len(plan.actions) == 2
    assert plan.high_confidence_fixes == 2
    assert plan.estimated_success_rate > 0.9

def test_topological_sort_dependencies():
    """Test that dependent actions are ordered correctly"""
    # Parser fixes must come before writer fixes
    # Matcher fixes must come before writer fixes
    pass

def test_confidence_thresholds():
    """Test confidence categorization"""
    # > 0.8 = high
    # 0.5-0.8 = medium
    # < 0.5 = low
    pass
```

#### 3.2 Implement Module (GREEN)
```python
# repair_strategy.py
from dataclasses import dataclass
from typing import List, Dict, Any
from collections import defaultdict, deque

@dataclass
class RepairAction:
    error_id: str
    action_type: str
    affected_phase: str
    confidence: float
    auto_executable: bool
    action_params: Dict[str, Any]
    gemini_suggested: str

@dataclass
class RepairPlan:
    actions: List[RepairAction]
    execution_order: List[RepairAction]
    total_errors: int
    high_confidence_fixes: int
    medium_confidence_fixes: int
    low_confidence_fixes: int
    estimated_success_rate: float

def generate_repair_plan(
    job_id: int,
    errors: Dict[str, List[PTError]],
    analyses: Dict[str, ErrorAnalysis]
) -> RepairPlan:
    """Generate executable repair plan with topological ordering"""

    actions = []

    # Convert analyses to RepairActions
    for hand_id, analysis in analyses.items():
        action = RepairAction(
            error_id=hand_id,
            action_type=determine_action_type(analysis),
            affected_phase=analysis.affected_phase,
            confidence=analysis.confidence,
            auto_executable=analysis.auto_fixable,
            action_params=build_action_params(analysis),
            gemini_suggested=analysis.suggested_fix
        )
        actions.append(action)

    # Sort by dependencies
    execution_order = topological_sort(actions)

    # Calculate confidence metrics
    high = sum(1 for a in actions if a.confidence > 0.8)
    medium = sum(1 for a in actions if 0.5 <= a.confidence <= 0.8)
    low = sum(1 for a in actions if a.confidence < 0.5)

    # Estimate success rate
    success_rate = sum(a.confidence for a in actions) / len(actions) if actions else 0

    return RepairPlan(
        actions=actions,
        execution_order=execution_order,
        total_errors=len(actions),
        high_confidence_fixes=high,
        medium_confidence_fixes=medium,
        low_confidence_fixes=low,
        estimated_success_rate=success_rate
    )

def topological_sort(actions: List[RepairAction]) -> List[RepairAction]:
    """Order actions by dependencies (parser → matcher → writer)"""
    # Phase priority order
    phase_priority = {
        "parser": 0,
        "ocr": 1,
        "matcher": 2,
        "writer": 3
    }

    return sorted(actions, key=lambda a: (
        phase_priority.get(a.affected_phase, 99),
        -a.confidence  # Higher confidence first within same phase
    ))
```

---

### Task 4: Repair Executor Module
**Time**: 2.5 hours
**Files**: `repair_executor.py`, `test_repair_executor.py`

#### 4.1 Write Tests First (RED)
```python
# test_repair_executor.py
async def test_execute_repair_plan():
    """Test executing a complete repair plan"""
    plan = RepairPlan(
        actions=[
            RepairAction(
                error_id="SG123",
                action_type="remove_duplicate_mapping",
                affected_phase="matcher",
                confidence=0.95,
                auto_executable=True,
                action_params={"seat": 3, "player": "TuichAAreko"}
            )
        ],
        execution_order=[...],
        total_errors=1,
        high_confidence_fixes=1,
        ...
    )

    executor = RepairExecutor(db=mock_db)
    results = await executor.execute_repair_plan(
        job_id=1,
        repair_plan=plan,
        user_approved=True
    )

    assert results["success_rate"] == 1.0
    assert len(results["executed_actions"]) == 1
    assert len(results["failed_actions"]) == 0
    assert len(results["modified_files"]) == 1

async def test_repair_matching_phase():
    """Test repairing matcher phase errors"""
    # Test removing duplicate mappings
    # Test rematching with constraints
    pass

async def test_repair_writer_phase():
    """Test repairing writer phase errors"""
    # Test regenerating TXT with fixed mappings
    pass

async def test_repair_parser_phase():
    """Test repairing parser phase errors"""
    # Test recalculating pots
    # Test fixing blinds
    pass
```

#### 4.2 Implement Module (GREEN)
[Implementation similar to design doc]

---

### Task 5: API Endpoints
**Time**: 2 hours
**Files**: `main.py` (modifications)

#### 5.1 Write API Tests First (RED)
```python
# test_api_error_recovery.py
def test_fix_errors_endpoint():
    """Test /api/fix-errors/{job_id} endpoint"""
    response = client.post(
        "/api/fix-errors/1",
        json={"error_log": "Error: Duplicate player..."}
    )

    assert response.status_code == 200
    assert "repair_plan" in response.json()
    assert response.json()["status"] == "plan_ready"

def test_execute_repairs_endpoint():
    """Test /api/execute-repairs/{job_id} endpoint"""
    # First create a plan
    # Then execute it
    pass

def test_download_repaired_endpoint():
    """Test downloading repaired files"""
    pass
```

#### 5.2 Implement Endpoints (GREEN)
[Add to main.py as designed]

---

### Task 6: Frontend UI
**Time**: 2.5 hours
**Files**: `templates/index.html`, `static/js/app.js`

#### 6.1 UI Components
- Error log textarea
- Analysis progress bar
- Repair plan display (with confidence colors)
- Execution log
- Results summary

#### 6.2 JavaScript Functions
```javascript
// app.js additions
async function analyzeErrorsWithJobId(jobId) {
    const errorLog = document.getElementById('errorLogTextarea').value;

    const response = await fetch(`/api/fix-errors/${jobId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({error_log: errorLog})
    });

    const result = await response.json();
    displayRepairPlan(result.repair_plan);
}

function displayRepairPlan(repairPlan) {
    // Display plan with confidence colors
    // Show summary statistics
    // List individual actions
}

async function executeRepairPlan(jobId) {
    // Execute approved plan
    // Show progress
    // Display results
}
```

---

### Task 7: Integration Testing
**Time**: 1.5 hours
**Files**: `test_integration_error_recovery.py`

#### 7.1 End-to-End Test
```python
def test_complete_error_recovery_flow():
    """Test complete flow from error upload to download"""
    # 1. Create a job with known issues
    # 2. Upload error log
    # 3. Get repair plan
    # 4. Execute repairs
    # 5. Validate fixed files
    # 6. Download and verify
    pass
```

---

## Execution Order

1. **Core Modules First** (Tasks 1-4)
   - Build foundation with TDD
   - Each module independently testable

2. **API Integration** (Task 5)
   - Wire modules to HTTP endpoints
   - Test with Postman/curl

3. **Frontend** (Task 6)
   - Add UI last (backend complete)
   - Manual testing with browser

4. **Integration Testing** (Task 7)
   - Full system validation
   - Real PT4 error logs

---

## Success Criteria

- [ ] All unit tests pass (30+ tests)
- [ ] Can parse 5 different PT4 error types
- [ ] Gemini analyzes with >80% confidence average
- [ ] Repairs fix >85% of duplicate player errors
- [ ] Repairs fix >70% of pot errors
- [ ] UI shows clear repair plan with confidence
- [ ] Fixed files pass PT4 validator
- [ ] Fixed files import to PT4 successfully

---

## Risk Mitigation

1. **Test Coverage**: Minimum 80% code coverage
2. **Error Handling**: Every function has try/catch
3. **Rollback**: Keep original files untouched
4. **Validation**: Check every repair with PT4 validator
5. **User Control**: Nothing auto-executes without approval

---

## Timeline

**Total Estimate**: 13.5 hours

| Task | Time | Running Total |
|------|------|---------------|
| Task 1: Error Parser | 1.5h | 1.5h |
| Task 2: Error Analyzer | 2.0h | 3.5h |
| Task 3: Repair Strategy | 1.5h | 5.0h |
| Task 4: Repair Executor | 2.5h | 7.5h |
| Task 5: API Endpoints | 2.0h | 9.5h |
| Task 6: Frontend UI | 2.5h | 12.0h |
| Task 7: Integration Testing | 1.5h | 13.5h |

---

## Next Step

Begin with Task 1: Error Parser Module using TDD approach.