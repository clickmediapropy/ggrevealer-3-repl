"""
Integration test - Verifies all modules work together end-to-end
"""

import asyncio
from unittest.mock import Mock, AsyncMock, patch
import json

# Import all modules
from error_parser import parse_error_log, map_errors_to_files
from error_analyzer import analyze_errors_with_gemini
from repair_strategy import generate_repair_plan
from repair_executor import RepairExecutor


async def test_complete_workflow():
    """
    Test complete error recovery workflow from error log to execution
    """
    print("\n" + "="*60)
    print("INTEGRATION TEST: Complete Error Recovery Workflow")
    print("="*60)

    # Step 1: Parse PT4 Error Log
    print("\n[Step 1] Parsing PT4 error log...")
    error_log = """
    Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247401164) (Line #46)
    Error: GG Poker: Invalid pot size: Expected $45.50, found $44.00 (Hand #RC3247401165) (Line #12)
    """

    errors = parse_error_log(error_log)
    print(f"✅ Parsed {len(errors)} errors")
    assert len(errors) == 2
    assert errors[0].error_type == "duplicate_player"
    assert errors[1].error_type == "invalid_pot"

    # Step 2: Map errors to files (mock database)
    print("\n[Step 2] Mapping errors to files...")
    errors_by_file = map_errors_to_files(job_id=1, errors=errors, db_connection=None)
    print(f"✅ Mapped to {len(errors_by_file)} files")

    # Step 3: Analyze with Gemini (mocked)
    print("\n[Step 3] Analyzing errors with Gemini AI...")

    mock_db = Mock()
    mock_db.get_job.return_value = {"id": 1}
    mock_db.get_parsed_hands.return_value = [
        {"hand_id": "SG3247401164", "players": {2: "abc123", 3: "def456"}},
        {"hand_id": "RC3247401165", "total_pot": 44.0}
    ]
    mock_db.get_ocr_results.return_value = [
        {"screenshot_id": "s1.png", "players": ["TuichAAreko", "Bob"]}
    ]
    mock_db.get_mappings.return_value = {
        "SG3247401164": {"abc123": "TuichAAreko", "def456": "TuichAAreko"}
    }

    gemini_response = {
        "SG3247401164": {
            "error_type": "duplicate_player",
            "root_cause": "Duplicate player mapping: TuichAAreko in seat 2 AND 3",
            "affected_phase": "matcher",
            "confidence": 0.95,
            "suggested_fix": "Remove seat 3 mapping for TuichAAreko",
            "auto_fixable": True,
            "fix_code": "remove_duplicate_mapping"
        },
        "RC3247401165": {
            "error_type": "invalid_pot",
            "root_cause": "Cash Drop fee (1BB on pots >30BB) not included",
            "affected_phase": "parser",
            "confidence": 0.88,
            "suggested_fix": "Add $1.50 jackpot fee to pot",
            "auto_fixable": True,
            "fix_code": "add_cash_drop_fee"
        }
    }

    with patch('error_analyzer.genai') as mock_genai, \
         patch('error_analyzer.os.getenv') as mock_getenv:

        mock_getenv.return_value = "fake_api_key"
        mock_model = AsyncMock()
        mock_response = Mock()
        mock_response.text = json.dumps(gemini_response)
        mock_model.generate_content_async.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model

        analyses = await analyze_errors_with_gemini(
            job_id=1,
            errors=errors_by_file,
            db_connection=mock_db
        )

        print(f"✅ Analyzed {len(analyses)} errors")
        assert len(analyses) == 2
        assert analyses["SG3247401164"].confidence == 0.95
        assert analyses["RC3247401165"].confidence == 0.88

    # Step 4: Generate Repair Plan
    print("\n[Step 4] Generating repair plan...")

    repair_plan = generate_repair_plan(
        job_id=1,
        errors=errors_by_file,
        analyses=analyses
    )

    print(f"✅ Generated plan with {repair_plan.total_errors} actions")
    print(f"   - High confidence: {repair_plan.high_confidence_fixes}")
    print(f"   - Medium confidence: {repair_plan.medium_confidence_fixes}")
    print(f"   - Low confidence: {repair_plan.low_confidence_fixes}")
    print(f"   - Estimated success: {repair_plan.estimated_success_rate:.2%}")

    assert repair_plan.total_errors == 2
    assert repair_plan.high_confidence_fixes == 2
    assert repair_plan.estimated_success_rate > 0.9

    # Verify topological sorting (parser before matcher)
    assert repair_plan.execution_order[0].affected_phase == "parser"
    assert repair_plan.execution_order[1].affected_phase == "matcher"

    # Step 5: Execute Repair Plan
    print("\n[Step 5] Executing repair plan...")

    executor = RepairExecutor(db=mock_db, api_key="fake_key")

    results = await executor.execute_repair_plan(
        job_id=1,
        repair_plan=repair_plan,
        user_approved=True
    )

    print(f"✅ Executed {results['total_executed']} actions")
    print(f"   - Success: {results['success_count']}")
    print(f"   - Failed: {results['failed_count']}")
    print(f"   - Success rate: {results['success_rate']:.2%}")

    assert results['total_executed'] == 2
    assert results['success_count'] == 2
    assert results['failed_count'] == 0
    assert results['success_rate'] == 1.0

    print("\n" + "="*60)
    print("✅ INTEGRATION TEST PASSED - ALL MODULES WORK TOGETHER!")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_complete_workflow())
