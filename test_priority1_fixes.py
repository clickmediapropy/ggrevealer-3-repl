"""
Validation script for Priority 1 fixes from Task 10 code review

Tests:
1. Fix #1: Player mapping rate calculation (must be <= 100%)
2. Fix #2: detailed_metrics exposed in /api/status endpoint
3. Fix #3: Hero mapping edge case test added
"""

from models import ParsedHand, Seat, BoardCards
from datetime import datetime
from main import _calculate_detailed_metrics
import json


def test_fix1_mapping_rate_boundary():
    """
    Fix #1: Verify mapping rate never exceeds 100%

    Tests multiple scenarios:
    - All mapped (100%)
    - Partial mapping (50%)
    - Hero + all anonymous mapped (100%, not 150%)
    """
    print("\n" + "="*70)
    print("FIX #1: Player Mapping Rate Calculation")
    print("="*70)

    # Scenario 1: All anonymous IDs mapped (100%)
    print("\n📊 Scenario 1: All anonymous IDs mapped")
    hand1 = ParsedHand(
        hand_id="RC123456",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=1,
        seats=[
            Seat(1, "abc123", 10.0, "BTN"),
            Seat(2, "def456", 10.0, "SB"),
            Seat(3, "Hero", 10.0, "BB")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="Table 'TestTable' 3-max..."
    )

    metrics1 = _calculate_detailed_metrics(
        all_hands=[hand1],
        table_groups={"TestTable": [hand1]},
        table_mappings={"TestTable": {"abc123": "Player1", "def456": "Player2"}},
        ocr1_results={},
        ocr2_results={},
        matched_screenshots={},
        unmatched_screenshots=[]
    )

    print(f"   Total unique: {metrics1['players']['total_unique']}")
    print(f"   Mapped: {metrics1['players']['mapped']}")
    print(f"   Mapping rate: {metrics1['players']['mapping_rate']}%")
    assert metrics1['players']['mapping_rate'] == 100.0, f"Expected 100.0%, got {metrics1['players']['mapping_rate']}%"
    assert metrics1['players']['mapping_rate'] <= 100.0, "Mapping rate exceeds 100%!"
    print("   ✅ PASS: Mapping rate = 100.0%")

    # Scenario 2: Partial mapping (50%)
    print("\n📊 Scenario 2: Partial mapping")
    metrics2 = _calculate_detailed_metrics(
        all_hands=[hand1],
        table_groups={"TestTable": [hand1]},
        table_mappings={"TestTable": {"abc123": "Player1"}},  # Only 1 of 2 mapped
        ocr1_results={},
        ocr2_results={},
        matched_screenshots={},
        unmatched_screenshots=[]
    )

    print(f"   Total unique: {metrics2['players']['total_unique']}")
    print(f"   Mapped: {metrics2['players']['mapped']}")
    print(f"   Mapping rate: {metrics2['players']['mapping_rate']}%")
    assert metrics2['players']['mapping_rate'] == 50.0, f"Expected 50.0%, got {metrics2['players']['mapping_rate']}%"
    assert metrics2['players']['mapping_rate'] <= 100.0, "Mapping rate exceeds 100%!"
    print("   ✅ PASS: Mapping rate = 50.0%")

    # Scenario 3: Hero + all anonymous mapped (THE BUG SCENARIO)
    print("\n📊 Scenario 3: Hero + all anonymous mapped (Bug fix validation)")
    metrics3 = _calculate_detailed_metrics(
        all_hands=[hand1],
        table_groups={"TestTable": [hand1]},
        table_mappings={"TestTable": {"abc123": "Player1", "def456": "Player2", "Hero": "TuichAAreko"}},
        ocr1_results={},
        ocr2_results={},
        matched_screenshots={},
        unmatched_screenshots=[]
    )

    print(f"   Total unique (anonymous only): {metrics3['players']['total_unique']}")
    print(f"   Mapped (anonymous only): {metrics3['players']['mapped']}")
    print(f"   Mapping rate: {metrics3['players']['mapping_rate']}%")
    print(f"   🐛 BUG (before fix): mapping_rate = 150.0% (3 mapped / 2 unique)")
    print(f"   ✅ FIXED: mapping_rate = 100.0% (2 anon mapped / 2 anon unique)")

    assert metrics3['players']['total_unique'] == 2, "Total unique should be 2 (Hero excluded)"
    assert metrics3['players']['mapped'] == 2, f"Mapped should be 2 (Hero excluded), got {metrics3['players']['mapped']}"
    assert metrics3['players']['mapping_rate'] == 100.0, f"Expected 100.0%, got {metrics3['players']['mapping_rate']}% (BUG NOT FIXED!)"
    assert metrics3['players']['mapping_rate'] <= 100.0, "Mapping rate exceeds 100%!"
    print("   ✅ PASS: Mapping rate = 100.0% (not 150.0%)")

    print("\n✅ Fix #1 VALIDATED: All scenarios pass, mapping rate <= 100%")


def test_fix2_api_detailed_metrics():
    """
    Fix #2: Verify detailed_metrics is exposed in /api/status response structure

    Note: This tests the code structure, not the actual API endpoint
    (which would require running the server)
    """
    print("\n" + "="*70)
    print("FIX #2: detailed_metrics Exposed in /api/status")
    print("="*70)

    # Read the main.py file to verify the code change
    with open('/Users/nicodelgadob/ggrevealer-3-repl/main.py', 'r') as f:
        content = f.read()

    # Check for the added lines
    expected_code = "# EXPOSE DETAILED METRICS directly for frontend use"
    if expected_code in content:
        print("\n✅ Code change detected in main.py")
        print(f"   Found: '{expected_code}'")
    else:
        raise AssertionError("Expected code change not found in main.py")

    # Check for the actual implementation
    expected_impl = "response['detailed_metrics'] = result['stats']['detailed_metrics']"
    if expected_impl in content:
        print("✅ Implementation found in main.py")
        print(f"   Found: '{expected_impl}'")
    else:
        raise AssertionError("Expected implementation not found in main.py")

    # Verify the code is in the /api/status endpoint
    status_endpoint_start = content.find("@app.get(\"/api/status/{job_id}\")")
    status_endpoint_end = content.find("@app.get", status_endpoint_start + 10)

    if status_endpoint_end == -1:
        status_endpoint_end = len(content)

    status_endpoint_code = content[status_endpoint_start:status_endpoint_end]

    if expected_impl in status_endpoint_code:
        print("✅ Code is in the correct endpoint (/api/status)")
        print("\n📋 Expected API response structure:")
        print("   {")
        print("     'job_id': ...,")
        print("     'status': ...,")
        print("     'detailed_stats': {...},  # Existing")
        print("     'detailed_metrics': {...},  # NEW - Exposed for frontend")
        print("     'statistics': {...}")
        print("   }")
    else:
        raise AssertionError("Implementation not found in /api/status endpoint")

    print("\n✅ Fix #2 VALIDATED: detailed_metrics exposed in /api/status")


def test_fix3_hero_test_exists():
    """
    Fix #3: Verify the new test_hero_mapping_rate() test exists and is called
    """
    print("\n" + "="*70)
    print("FIX #3: Hero Mapping Edge Case Test Added")
    print("="*70)

    # Read test_metrics.py
    with open('/Users/nicodelgadob/ggrevealer-3-repl/test_metrics.py', 'r') as f:
        content = f.read()

    # Check for test function
    if "def test_hero_mapping_rate():" in content:
        print("\n✅ New test function found: test_hero_mapping_rate()")
    else:
        raise AssertionError("test_hero_mapping_rate() function not found")

    # Check for test documentation
    if "This validates the fix for the Hero mapping edge case bug" in content:
        print("✅ Test documentation found")
    else:
        raise AssertionError("Test documentation not found")

    # Check that it's called in main
    if "test_hero_mapping_rate()" in content:
        print("✅ Test is called in __main__ block")
    else:
        raise AssertionError("test_hero_mapping_rate() not called in __main__")

    # Check for critical assertions
    critical_assertions = [
        "assert metrics['players']['mapping_rate'] == 100.0",
        "assert metrics['players']['mapping_rate'] <= 100.0",
        "assert metrics['players']['mapped'] == 2"
    ]

    for assertion in critical_assertions:
        if assertion in content:
            print(f"✅ Critical assertion found: {assertion}")
        else:
            raise AssertionError(f"Critical assertion not found: {assertion}")

    # Run the test to make sure it passes
    print("\n📊 Running test_hero_mapping_rate() from test_metrics.py...")
    from test_metrics import test_hero_mapping_rate
    test_hero_mapping_rate()

    print("\n✅ Fix #3 VALIDATED: Hero mapping test exists and passes")


def test_fix3_original_test_updated():
    """
    Verify that test_full_mapping() was updated to reflect the fix
    """
    print("\n" + "="*70)
    print("BONUS: Original test_full_mapping() Updated")
    print("="*70)

    with open('/Users/nicodelgadob/ggrevealer-3-repl/test_metrics.py', 'r') as f:
        content = f.read()

    # Check that the old bug assertion is gone
    if "assert metrics['players']['mapped'] == 3" in content:
        raise AssertionError("Old bug assertion still present (mapped == 3)")

    if "assert metrics['players']['mapping_rate'] == 150.0" in content:
        raise AssertionError("Old bug assertion still present (mapping_rate == 150.0)")

    # Check for updated assertions
    if "assert metrics['players']['mapped'] == 2  # Changed from 3 to 2" in content:
        print("\n✅ Updated assertion: mapped == 2 (was 3)")
    else:
        raise AssertionError("Updated 'mapped' assertion not found")

    if "assert metrics['players']['mapping_rate'] == 100.0  # Changed from 150.0 to 100.0" in content:
        print("✅ Updated assertion: mapping_rate == 100.0 (was 150.0)")
    else:
        raise AssertionError("Updated 'mapping_rate' assertion not found")

    print("\n✅ BONUS VALIDATED: Original test updated correctly")


def run_all_validations():
    """Run all validation tests"""
    print("\n" + "="*70)
    print("🔍 PRIORITY 1 FIXES VALIDATION SUITE")
    print("="*70)
    print("\nValidating fixes from Task 10 code review:")
    print("  1. Fix #1: Player mapping rate <= 100%")
    print("  2. Fix #2: detailed_metrics exposed in /api/status")
    print("  3. Fix #3: Hero mapping edge case test")

    try:
        test_fix1_mapping_rate_boundary()
        test_fix2_api_detailed_metrics()
        test_fix3_hero_test_exists()
        test_fix3_original_test_updated()

        print("\n" + "="*70)
        print("✅ ALL PRIORITY 1 FIXES VALIDATED SUCCESSFULLY")
        print("="*70)
        print("\n📋 Summary:")
        print("  ✅ Fix #1: Player mapping rate corrected (now <= 100%)")
        print("  ✅ Fix #2: detailed_metrics exposed in /api/status endpoint")
        print("  ✅ Fix #3: Hero mapping edge case test added and passing")
        print("  ✅ Bonus: Original test_full_mapping() updated")
        print("\n🎉 All fixes implemented and validated correctly!")

    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        raise
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        raise


if __name__ == "__main__":
    run_all_validations()
