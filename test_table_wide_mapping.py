"""
Test table-wide mapping functionality (Task 9)
Tests the new _group_hands_by_table() and _build_table_mapping() functions
"""

import sys
from datetime import datetime
from models import ParsedHand, ScreenshotAnalysis, Seat, BoardCards, PlayerStack
from main import _group_hands_by_table, _build_table_mapping
from logger import get_job_logger


class MockLogger:
    """Mock logger for testing"""
    def debug(self, msg, **kwargs):
        print(f"[DEBUG] {msg}")

    def info(self, msg, **kwargs):
        print(f"[INFO] {msg}")

    def warning(self, msg, **kwargs):
        print(f"[WARNING] {msg}")

    def error(self, msg, **kwargs):
        print(f"[ERROR] {msg}")


def test_group_hands_by_table():
    """Test grouping hands by table name"""
    print("\n=== TEST 1: Group hands by table ===")

    # Create hands from 3 different tables
    hands = [
        ParsedHand(
            hand_id="RC1001",
            timestamp=datetime.now(),
            game_type="Hold'em No Limit",
            stakes="$0.10/$0.20",
            table_format="3-max",
            button_seat=1,
            seats=[
                Seat(seat_number=1, player_id="Hero", stack=100.0, position="BTN"),
                Seat(seat_number=2, player_id="abc123", stack=200.0, position="SB"),
                Seat(seat_number=3, player_id="def456", stack=150.0, position="BB")
            ],
            board_cards=BoardCards(),
            actions=[],
            raw_text="Table 'Cartney' 3-max Seat #1 is the button"
        ),
        ParsedHand(
            hand_id="RC1002",
            timestamp=datetime.now(),
            game_type="Hold'em No Limit",
            stakes="$0.10/$0.20",
            table_format="3-max",
            button_seat=2,
            seats=[
                Seat(seat_number=1, player_id="xyz789", stack=100.0, position="BB"),
                Seat(seat_number=2, player_id="Hero", stack=200.0, position="BTN"),
                Seat(seat_number=3, player_id="ghi012", stack=150.0, position="SB")
            ],
            board_cards=BoardCards(),
            actions=[],
            raw_text="Table 'Cartney' 3-max Seat #2 is the button"
        ),
        ParsedHand(
            hand_id="RC1003",
            timestamp=datetime.now(),
            game_type="Hold'em No Limit",
            stakes="$0.10/$0.20",
            table_format="3-max",
            button_seat=1,
            seats=[
                Seat(seat_number=1, player_id="Hero", stack=100.0, position="BTN"),
                Seat(seat_number=2, player_id="mno345", stack=200.0, position="SB"),
                Seat(seat_number=3, player_id="pqr678", stack=150.0, position="BB")
            ],
            board_cards=BoardCards(),
            actions=[],
            raw_text="Table 'Lennon' 3-max Seat #1 is the button"
        )
    ]

    # Group hands
    table_groups = _group_hands_by_table(hands)

    print(f"Tables found: {list(table_groups.keys())}")
    print(f"Cartney hands: {len(table_groups.get('Cartney', []))}")
    print(f"Lennon hands: {len(table_groups.get('Lennon', []))}")

    # Validate
    assert len(table_groups) == 2, f"Should have 2 tables, got {len(table_groups)}"
    assert 'Cartney' in table_groups, "Should have Cartney table"
    assert 'Lennon' in table_groups, "Should have Lennon table"
    assert len(table_groups['Cartney']) == 2, f"Cartney should have 2 hands, got {len(table_groups['Cartney'])}"
    assert len(table_groups['Lennon']) == 1, f"Lennon should have 1 hand, got {len(table_groups['Lennon'])}"

    print("✅ TEST 1 PASSED: Hands grouped correctly by table")


def test_build_table_mapping_single_screenshot():
    """Test building table mapping with one screenshot"""
    print("\n=== TEST 2: Build table mapping with 1 screenshot ===")

    # Create 2 hands from same table
    hand1 = ParsedHand(
        hand_id="RC2001",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=3,
        seats=[
            Seat(seat_number=1, player_id="e3efcaed", stack=100.0, position="SB"),
            Seat(seat_number=2, player_id="5641b4a0", stack=200.0, position="BB"),
            Seat(seat_number=3, player_id="Hero", stack=150.0, position="BTN")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="""Poker Hand #RC2001: Hold'em No Limit ($0.10/$0.20) - 2025/09/29 15:30:00
Table 'TestTable' 3-max Seat #3 is the button
Seat 1: e3efcaed (100 in chips)
Seat 2: 5641b4a0 (200 in chips)
Seat 3: Hero (150 in chips)
e3efcaed: posts small blind $0.10
5641b4a0: posts big blind $0.20
"""
    )

    hand2 = ParsedHand(
        hand_id="RC2002",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=1,
        seats=[
            Seat(seat_number=1, player_id="5641b4a0", stack=190.0, position="BTN"),
            Seat(seat_number=2, player_id="Hero", stack=160.0, position="SB"),
            Seat(seat_number=3, player_id="e3efcaed", stack=95.0, position="BB")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="""Poker Hand #RC2002: Hold'em No Limit ($0.10/$0.20) - 2025/09/29 15:31:00
Table 'TestTable' 3-max Seat #1 is the button
Seat 1: 5641b4a0 (190 in chips)
Seat 2: Hero (160 in chips)
Seat 3: e3efcaed (95 in chips)
Hero: posts small blind $0.10
e3efcaed: posts big blind $0.20
"""
    )

    # Create matched screenshot for hand1
    matched_screenshots = {
        "screenshot_001.png": hand1
    }

    # Create OCR2 results with role indicators
    ocr2_results = {
        "screenshot_001.png": (
            True,  # success
            {
                'hand_id': 'RC2001',
                'dealer_player': 'TuichAAreko',  # Hero at Button
                'small_blind_player': 'Gyodong22',  # SB
                'big_blind_player': 'v1[nn]1',  # BB
                'players': [
                    {'name': 'TuichAAreko', 'stack': 150.0, 'position': 1},
                    {'name': 'Gyodong22', 'stack': 100.0, 'position': 2},
                    {'name': 'v1[nn]1', 'stack': 200.0, 'position': 3}
                ]
            },
            None  # error
        )
    }

    # Build table mapping
    logger = MockLogger()
    mapping = _build_table_mapping(
        table_name='TestTable',
        hands=[hand1, hand2],
        matched_screenshots=matched_screenshots,
        ocr2_results=ocr2_results,
        logger=logger
    )

    print(f"\nMapping result: {mapping}")
    print(f"Expected: Hero → TuichAAreko, e3efcaed → Gyodong22, 5641b4a0 → v1[nn]1")

    # Validate - all 3 players should be mapped from the single screenshot
    assert 'Hero' in mapping, "Hero should be in mapping"
    assert 'e3efcaed' in mapping, "e3efcaed should be in mapping"
    assert '5641b4a0' in mapping, "5641b4a0 should be in mapping"
    assert mapping['Hero'] == 'TuichAAreko', f"Hero should map to TuichAAreko, got {mapping['Hero']}"
    assert mapping['e3efcaed'] == 'Gyodong22', f"e3efcaed should map to Gyodong22, got {mapping['e3efcaed']}"
    assert mapping['5641b4a0'] == 'v1[nn]1', f"5641b4a0 should map to v1[nn]1, got {mapping['5641b4a0']}"

    print("✅ TEST 2 PASSED: Single screenshot mapped all 3 players for both hands")


def test_build_table_mapping_multiple_screenshots():
    """Test building table mapping with multiple screenshots (aggregation)"""
    print("\n=== TEST 3: Build table mapping with 2 screenshots (aggregation) ===")

    # Create 3 hands from same table with different player combinations
    hand1 = ParsedHand(
        hand_id="RC3001",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=3,
        seats=[
            Seat(seat_number=1, player_id="player1", stack=100.0, position="SB"),
            Seat(seat_number=2, player_id="player2", stack=200.0, position="BB"),
            Seat(seat_number=3, player_id="Hero", stack=150.0, position="BTN")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="""Table 'AggTable' 3-max Seat #3 is the button
player1: posts small blind $0.10
player2: posts big blind $0.20
"""
    )

    hand2 = ParsedHand(
        hand_id="RC3002",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=1,
        seats=[
            Seat(seat_number=1, player_id="player2", stack=190.0, position="BTN"),
            Seat(seat_number=2, player_id="Hero", stack=160.0, position="SB"),
            Seat(seat_number=3, player_id="player3", stack=95.0, position="BB")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="""Table 'AggTable' 3-max Seat #1 is the button
Hero: posts small blind $0.10
player3: posts big blind $0.20
"""
    )

    hand3 = ParsedHand(
        hand_id="RC3003",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=2,
        seats=[
            Seat(seat_number=1, player_id="player4", stack=100.0, position="BB"),
            Seat(seat_number=2, player_id="player3", stack=200.0, position="BTN"),
            Seat(seat_number=3, player_id="Hero", stack=150.0, position="SB")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="""Table 'AggTable' 3-max Seat #2 is the button
Hero: posts small blind $0.10
player4: posts big blind $0.20
"""
    )

    # Create matched screenshots for hand1 and hand2
    matched_screenshots = {
        "screenshot_A.png": hand1,
        "screenshot_B.png": hand2
    }

    # OCR2 results for both screenshots
    ocr2_results = {
        "screenshot_A.png": (
            True,
            {
                'hand_id': 'RC3001',
                'dealer_player': 'RealHero',
                'small_blind_player': 'Alice',
                'big_blind_player': 'Bob',
                'players': [
                    {'name': 'RealHero', 'stack': 150.0, 'position': 1},
                    {'name': 'Alice', 'stack': 100.0, 'position': 2},
                    {'name': 'Bob', 'stack': 200.0, 'position': 3}
                ]
            },
            None
        ),
        "screenshot_B.png": (
            True,
            {
                'hand_id': 'RC3002',
                'dealer_player': 'Bob',
                'small_blind_player': 'RealHero',
                'big_blind_player': 'Charlie',
                'players': [
                    {'name': 'Bob', 'stack': 190.0, 'position': 1},
                    {'name': 'RealHero', 'stack': 160.0, 'position': 2},
                    {'name': 'Charlie', 'stack': 95.0, 'position': 3}
                ]
            },
            None
        )
    }

    # Build table mapping
    logger = MockLogger()
    mapping = _build_table_mapping(
        table_name='AggTable',
        hands=[hand1, hand2, hand3],
        matched_screenshots=matched_screenshots,
        ocr2_results=ocr2_results,
        logger=logger
    )

    print(f"\nMapping result: {mapping}")
    print(f"Unique players in hands: Hero, player1, player2, player3, player4 (5 total)")
    print(f"Screenshots covered: player1, player2, player3, Hero (4 total)")
    print(f"Expected mappings: 4 (player4 should be unmapped)")

    # Validate aggregation
    assert 'Hero' in mapping, "Hero should be in mapping"
    assert 'player1' in mapping, "player1 should be in mapping (from screenshot A)"
    assert 'player2' in mapping, "player2 should be in mapping (from both screenshots)"
    assert 'player3' in mapping, "player3 should be in mapping (from screenshot B)"
    assert 'player4' not in mapping, "player4 should NOT be in mapping (no screenshot)"

    assert mapping['Hero'] == 'RealHero', f"Hero should map to RealHero, got {mapping['Hero']}"
    assert mapping['player1'] == 'Alice', f"player1 should map to Alice, got {mapping['player1']}"
    assert mapping['player2'] == 'Bob', f"player2 should map to Bob, got {mapping['player2']}"
    assert mapping['player3'] == 'Charlie', f"player3 should map to Charlie, got {mapping['player3']}"

    print("✅ TEST 3 PASSED: Multiple screenshots aggregated correctly, unmapped player detected")


def test_build_table_mapping_no_screenshots():
    """Test building table mapping with no screenshots (edge case)"""
    print("\n=== TEST 4: Build table mapping with NO screenshots ===")

    hand = ParsedHand(
        hand_id="RC4001",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=1,
        seats=[
            Seat(seat_number=1, player_id="Hero", stack=100.0, position="BTN"),
            Seat(seat_number=2, player_id="abc123", stack=200.0, position="SB"),
            Seat(seat_number=3, player_id="def456", stack=150.0, position="BB")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="Table 'NoScreenshots' 3-max Seat #1 is the button"
    )

    # No matched screenshots
    matched_screenshots = {}
    ocr2_results = {}

    logger = MockLogger()
    mapping = _build_table_mapping(
        table_name='NoScreenshots',
        hands=[hand],
        matched_screenshots=matched_screenshots,
        ocr2_results=ocr2_results,
        logger=logger
    )

    print(f"\nMapping result: {mapping}")
    print(f"Expected: Empty mapping (no screenshots)")

    # Validate
    assert len(mapping) == 0, f"Mapping should be empty, got {len(mapping)} entries"

    print("✅ TEST 4 PASSED: No screenshots results in empty mapping")


if __name__ == "__main__":
    print("=" * 80)
    print("TABLE-WIDE MAPPING TESTS (Task 9)")
    print("=" * 80)

    try:
        test_group_hands_by_table()
        test_build_table_mapping_single_screenshot()
        test_build_table_mapping_multiple_screenshots()
        test_build_table_mapping_no_screenshots()

        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED")
        print("=" * 80)

    except AssertionError as e:
        print("\n" + "=" * 80)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 80)
        sys.exit(1)
    except Exception as e:
        print("\n" + "=" * 80)
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 80)
        sys.exit(1)
