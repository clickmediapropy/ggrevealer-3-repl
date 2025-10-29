"""
Test comprehensive metrics calculation with edge cases
"""

from models import ParsedHand, Seat, BoardCards, Action
from datetime import datetime
from main import _calculate_detailed_metrics


def test_empty_data():
    """Test with empty data (edge case: no hands, no screenshots)"""
    print("\n=== Test 1: Empty Data ===")

    metrics = _calculate_detailed_metrics(
        all_hands=[],
        table_groups={},
        table_mappings={},
        ocr1_results={},
        ocr2_results={},
        matched_screenshots={},
        unmatched_screenshots=[]
    )

    print("Hands metrics:", metrics['hands'])
    print("Players metrics:", metrics['players'])
    print("Tables metrics:", metrics['tables'])
    print("Screenshots metrics:", metrics['screenshots'])
    print("Mappings metrics:", metrics['mappings'])

    # Verify no division by zero errors
    assert metrics['hands']['coverage_percentage'] == 0
    assert metrics['players']['mapping_rate'] == 0
    assert metrics['tables']['resolution_rate'] == 0
    assert metrics['screenshots']['ocr1_success_rate'] == 0

    print("✅ Test 1 passed: No division by zero errors")


def test_single_hand_no_mappings():
    """Test with single hand and no mappings"""
    print("\n=== Test 2: Single Hand, No Mappings ===")

    # Create a simple hand
    hand = ParsedHand(
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

    table_groups = {"TestTable": [hand]}
    table_mappings = {"TestTable": {}}  # No mappings

    metrics = _calculate_detailed_metrics(
        all_hands=[hand],
        table_groups=table_groups,
        table_mappings=table_mappings,
        ocr1_results={},
        ocr2_results={},
        matched_screenshots={},
        unmatched_screenshots=[]
    )

    print("Hands metrics:", metrics['hands'])
    print("Players metrics:", metrics['players'])

    assert metrics['hands']['total'] == 1
    assert metrics['hands']['no_mappings'] == 1
    assert metrics['hands']['fully_mapped'] == 0
    assert metrics['players']['total_unique'] == 2  # abc123, def456 (Hero excluded)
    assert metrics['players']['mapped'] == 0

    print("✅ Test 2 passed: Single hand with no mappings")


def test_full_mapping():
    """Test with complete mappings"""
    print("\n=== Test 3: Full Mapping ===")

    # Create hands
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

    hand2 = ParsedHand(
        hand_id="RC123457",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=2,
        seats=[
            Seat(1, "abc123", 10.0, "SB"),
            Seat(2, "def456", 10.0, "BB"),
            Seat(3, "Hero", 10.0, "BTN")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="Table 'TestTable' 3-max..."
    )

    table_groups = {"TestTable": [hand1, hand2]}
    table_mappings = {
        "TestTable": {
            "abc123": "Player1",
            "def456": "Player2",
            "Hero": "TuichAAreko"
        }
    }

    # Simulate OCR results
    ocr1_results = {
        "screenshot1.png": (True, "RC123456", None),
        "screenshot2.png": (False, None, "OCR failed")
    }

    ocr2_results = {
        "screenshot1.png": (True, {
            'players': ['Player1', 'Player2', 'TuichAAreko'],
            'dealer_player': 'Player1',
            'small_blind_player': 'Player2',
            'big_blind_player': 'TuichAAreko'
        }, None)
    }

    matched_screenshots = {
        "screenshot1.png": hand1
    }

    unmatched_screenshots = [
        ("screenshot2.png", "OCR failed")
    ]

    metrics = _calculate_detailed_metrics(
        all_hands=[hand1, hand2],
        table_groups=table_groups,
        table_mappings=table_mappings,
        ocr1_results=ocr1_results,
        ocr2_results=ocr2_results,
        matched_screenshots=matched_screenshots,
        unmatched_screenshots=unmatched_screenshots
    )

    print("Hands metrics:", metrics['hands'])
    print("Players metrics:", metrics['players'])
    print("Tables metrics:", metrics['tables'])
    print("Screenshots metrics:", metrics['screenshots'])
    print("Mappings metrics:", metrics['mappings'])

    assert metrics['hands']['total'] == 2
    assert metrics['hands']['fully_mapped'] == 2
    assert metrics['hands']['coverage_percentage'] == 100.0
    assert metrics['players']['total_unique'] == 2  # abc123, def456 (Hero excluded from unique count)
    # Note: 'mapped' now only counts anonymous IDs (Hero excluded) - FIXED
    assert metrics['players']['mapped'] == 2  # Changed from 3 to 2 (Hero excluded)
    # mapping_rate should be 100% (2 mapped / 2 total) - FIXED from 150%
    assert metrics['players']['mapping_rate'] == 100.0  # Changed from 150.0 to 100.0
    assert metrics['tables']['fully_resolved'] == 1
    assert metrics['tables']['resolution_rate'] == 100.0
    assert metrics['screenshots']['total'] == 2
    assert metrics['screenshots']['ocr1_success'] == 1
    assert metrics['screenshots']['ocr1_failure'] == 1
    assert metrics['screenshots']['matched'] == 1
    assert metrics['screenshots']['discarded'] == 1
    assert metrics['mappings']['total'] == 3  # abc123, def456, Hero
    assert metrics['mappings']['role_based'] == 3  # screenshot1 had role indicators

    print("✅ Test 3 passed: Full mapping scenario")


def test_partial_mapping():
    """Test with partial mappings (some players unmapped)"""
    print("\n=== Test 4: Partial Mapping ===")

    hand = ParsedHand(
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

    table_groups = {"TestTable": [hand]}
    table_mappings = {
        "TestTable": {
            "abc123": "Player1"
            # def456 not mapped
        }
    }

    metrics = _calculate_detailed_metrics(
        all_hands=[hand],
        table_groups=table_groups,
        table_mappings=table_mappings,
        ocr1_results={},
        ocr2_results={},
        matched_screenshots={},
        unmatched_screenshots=[]
    )

    print("Hands metrics:", metrics['hands'])
    print("Players metrics:", metrics['players'])
    print("Tables metrics:", metrics['tables'])

    assert metrics['hands']['total'] == 1
    assert metrics['hands']['partially_mapped'] == 1
    assert metrics['players']['total_unique'] == 2
    assert metrics['players']['mapped'] == 1
    assert metrics['players']['unmapped'] == 1
    assert metrics['players']['mapping_rate'] == 50.0
    assert metrics['tables']['partially_resolved'] == 1  # 50% coverage

    print("✅ Test 4 passed: Partial mapping scenario")


def test_multiple_tables():
    """Test with multiple tables (some resolved, some failed)"""
    print("\n=== Test 5: Multiple Tables ===")

    # Table 1: Fully resolved
    hand1 = ParsedHand(
        hand_id="RC123456",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=1,
        seats=[
            Seat(1, "abc123", 10.0, "BTN"),
            Seat(2, "Hero", 10.0, "SB")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="Table 'Table1' 3-max..."
    )

    # Table 2: Failed (no mappings)
    hand2 = ParsedHand(
        hand_id="RC123457",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=1,
        seats=[
            Seat(1, "xyz789", 10.0, "BTN"),
            Seat(2, "Hero", 10.0, "SB")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="Table 'Table2' 3-max..."
    )

    table_groups = {
        "Table1": [hand1],
        "Table2": [hand2]
    }

    table_mappings = {
        "Table1": {"abc123": "Player1"},
        "Table2": {}  # No mappings
    }

    metrics = _calculate_detailed_metrics(
        all_hands=[hand1, hand2],
        table_groups=table_groups,
        table_mappings=table_mappings,
        ocr1_results={},
        ocr2_results={},
        matched_screenshots={},
        unmatched_screenshots=[]
    )

    print("Tables metrics:", metrics['tables'])

    assert metrics['tables']['total'] == 2
    assert metrics['tables']['fully_resolved'] == 1  # Table1
    assert metrics['tables']['failed'] == 1  # Table2 (0% coverage)
    assert metrics['tables']['resolution_rate'] == 50.0

    print("✅ Test 5 passed: Multiple tables scenario")


def test_hero_mapping_rate():
    """
    Test that mapping rate doesn't exceed 100% when Hero is mapped.
    This validates the fix for the Hero mapping edge case bug.

    Scenario: Hand with Hero + 2 anonymous IDs, all 3 mapped
    Expected: mapping_rate = 100% (2 anon mapped / 2 anon total)
    Bug (before fix): mapping_rate = 150% (3 total mapped / 2 anon total)
    """
    print("\n=== Test 6: Hero Mapping Rate Edge Case ===")

    # Create hand with Hero + 2 anonymous players
    hand = ParsedHand(
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

    table_groups = {"TestTable": [hand]}

    # All 3 players mapped (Hero + 2 anonymous)
    table_mappings = {
        "TestTable": {
            "abc123": "Player1",
            "def456": "Player2",
            "Hero": "TuichAAreko"
        }
    }

    metrics = _calculate_detailed_metrics(
        all_hands=[hand],
        table_groups=table_groups,
        table_mappings=table_mappings,
        ocr1_results={},
        ocr2_results={},
        matched_screenshots={},
        unmatched_screenshots=[]
    )

    print("Players metrics:", metrics['players'])

    # Validate: Hero excluded from total_unique count
    assert metrics['players']['total_unique'] == 2, \
        f"Expected 2 unique anonymous IDs, got {metrics['players']['total_unique']}"

    # Validate: mapped should only count anonymous IDs (not Hero)
    assert metrics['players']['mapped'] == 2, \
        f"Expected 2 mapped anonymous IDs (Hero excluded), got {metrics['players']['mapped']}"

    # Validate: unmapped should be 0 (all anonymous IDs are mapped)
    assert metrics['players']['unmapped'] == 0, \
        f"Expected 0 unmapped IDs, got {metrics['players']['unmapped']}"

    # CRITICAL: Mapping rate must be <= 100%
    assert metrics['players']['mapping_rate'] == 100.0, \
        f"Expected mapping_rate = 100.0%, got {metrics['players']['mapping_rate']}%"

    # Additional validation: mapping_rate should never exceed 100%
    assert metrics['players']['mapping_rate'] <= 100.0, \
        f"CRITICAL BUG: mapping_rate exceeds 100% ({metrics['players']['mapping_rate']}%)"

    print("✅ Test 6 passed: Hero mapping rate stays at 100% (not 150%)")


if __name__ == "__main__":
    print("Testing comprehensive metrics calculation...")

    test_empty_data()
    test_single_hand_no_mappings()
    test_full_mapping()
    test_partial_mapping()
    test_multiple_tables()
    test_hero_mapping_rate()

    print("\n" + "="*50)
    print("✅ All tests passed!")
    print("="*50)
