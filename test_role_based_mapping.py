"""
Test role-based seat mapping functionality
Tests the new _build_seat_mapping_by_roles() function
"""

import sys
from datetime import datetime
from models import ParsedHand, ScreenshotAnalysis, Seat, BoardCards, PlayerStack
from matcher import _build_seat_mapping_by_roles, _build_seat_mapping

def test_role_based_mapping_complete():
    """Test with all 3 roles available (D, SB, BB)"""
    print("\n=== TEST 1: Complete role mapping (all 3 roles) ===")

    # Create hand with 3 players
    hand = ParsedHand(
        hand_id="SG3260934198",
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
        raw_text="""Poker Hand #SG3260934198: Hold'em No Limit ($0.10/$0.20) - 2025/09/29 15:30:00
Table 'Test' 3-max Seat #3 is the button
Seat 1: e3efcaed (100 in chips)
Seat 2: 5641b4a0 (200 in chips)
Seat 3: Hero (150 in chips)
e3efcaed: posts small blind $0.10
5641b4a0: posts big blind $0.20
"""
    )

    # Create screenshot with role indicators
    screenshot = ScreenshotAnalysis(
        screenshot_id="screenshot_001.png",
        hand_id="3260934198",
        player_names=["TuichAAreko", "Gyodong22", "v1[nn]1"],
        hero_name="TuichAAreko",
        hero_position=1,
        all_player_stacks=[
            PlayerStack(player_name="TuichAAreko", stack=150.0, position=1),  # Hero at visual position 1
            PlayerStack(player_name="Gyodong22", stack=100.0, position=2),     # SB at visual position 2
            PlayerStack(player_name="v1[nn]1", stack=200.0, position=3)        # BB at visual position 3
        ],
        # OCR2 role indicators
        dealer_player="TuichAAreko",      # Hero is dealer
        small_blind_player="Gyodong22",   # Gyodong22 is SB
        big_blind_player="v1[nn]1"        # v1[nn]1 is BB
    )

    # Test role-based mapping
    mapping = _build_seat_mapping_by_roles(screenshot, hand)

    print(f"Mapping result: {mapping}")
    print(f"Expected: Hero → TuichAAreko, e3efcaed → Gyodong22, 5641b4a0 → v1[nn]1")

    # Validate
    assert mapping.get("Hero") == "TuichAAreko", f"Hero should map to TuichAAreko, got {mapping.get('Hero')}"
    assert mapping.get("e3efcaed") == "Gyodong22", f"e3efcaed should map to Gyodong22, got {mapping.get('e3efcaed')}"
    assert mapping.get("5641b4a0") == "v1[nn]1", f"5641b4a0 should map to v1[nn]1, got {mapping.get('5641b4a0')}"
    assert len(mapping) == 3, f"Should have 3 mappings, got {len(mapping)}"

    print("✅ TEST 1 PASSED: All roles mapped correctly")


def test_role_based_mapping_partial():
    """Test with only 2 roles available (D and BB, missing SB)"""
    print("\n=== TEST 2: Partial role mapping (2 of 3 roles) ===")

    hand = ParsedHand(
        hand_id="SG1234567890",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=2,
        seats=[
            Seat(seat_number=1, player_id="abc123", stack=100.0, position="BB"),
            Seat(seat_number=2, player_id="Hero", stack=150.0, position="BTN"),
            Seat(seat_number=3, player_id="def456", stack=200.0, position="SB")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="""Poker Hand #SG1234567890: Hold'em No Limit ($0.10/$0.20) - 2025/09/29 15:30:00
Table 'Test' 3-max Seat #2 is the button
Seat 1: abc123 (100 in chips)
Seat 2: Hero (150 in chips)
Seat 3: def456 (200 in chips)
def456: posts small blind $0.10
abc123: posts big blind $0.20
"""
    )

    screenshot = ScreenshotAnalysis(
        screenshot_id="screenshot_002.png",
        hand_id="1234567890",
        player_names=["PlayerA", "PlayerB", "PlayerC"],
        hero_name="PlayerA",
        hero_position=1,
        all_player_stacks=[
            PlayerStack(player_name="PlayerA", stack=150.0, position=1),
            PlayerStack(player_name="PlayerB", stack=100.0, position=2),
            PlayerStack(player_name="PlayerC", stack=200.0, position=3)
        ],
        # OCR2 role indicators - only 2 available
        dealer_player="PlayerA",       # Hero is dealer
        small_blind_player=None,       # SB not detected
        big_blind_player="PlayerB"     # PlayerB is BB
    )

    mapping = _build_seat_mapping_by_roles(screenshot, hand)

    print(f"Mapping result: {mapping}")

    # Should map at least Hero and BB, then fall back for SB
    assert "Hero" in mapping, "Hero should be in mapping"
    assert "abc123" in mapping, "abc123 (BB) should be in mapping"
    assert len(mapping) >= 2, f"Should have at least 2 mappings, got {len(mapping)}"

    print("✅ TEST 2 PASSED: Partial role mapping successful")


def test_role_based_fallback_to_counter_clockwise():
    """Test fallback when no role indicators available"""
    print("\n=== TEST 3: Fallback to visual position (no roles) ===")

    hand = ParsedHand(
        hand_id="SG9876543210",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=1,
        seats=[
            Seat(seat_number=1, player_id="Hero", stack=100.0, position="BTN"),
            Seat(seat_number=2, player_id="xyz789", stack=200.0, position="SB"),
            Seat(seat_number=3, player_id="uvw456", stack=150.0, position="BB")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="""Poker Hand #SG9876543210: Hold'em No Limit ($0.10/$0.20) - 2025/09/29 15:30:00
Table 'Test' 3-max Seat #1 is the button
Seat 1: Hero (100 in chips)
Seat 2: xyz789 (200 in chips)
Seat 3: uvw456 (150 in chips)
xyz789: posts small blind $0.10
uvw456: posts big blind $0.20
"""
    )

    screenshot = ScreenshotAnalysis(
        screenshot_id="screenshot_003.png",
        hand_id="9876543210",
        player_names=["Player1", "Player2", "Player3"],
        hero_name="Player1",
        hero_position=1,
        all_player_stacks=[
            PlayerStack(player_name="Player1", stack=100.0, position=1),
            PlayerStack(player_name="Player2", stack=200.0, position=2),
            PlayerStack(player_name="Player3", stack=150.0, position=3)
        ],
        # OCR2 role indicators - none available
        dealer_player=None,
        small_blind_player=None,
        big_blind_player=None
    )

    mapping = _build_seat_mapping_by_roles(screenshot, hand)

    print(f"Mapping result: {mapping}")

    # Should use visual position fallback
    assert len(mapping) == 3, f"Should have 3 mappings via fallback, got {len(mapping)}"
    assert "Hero" in mapping, "Hero should be mapped via fallback"

    print("✅ TEST 3 PASSED: Fallback to visual position works")


def test_duplicate_name_rejection():
    """Test that duplicate names are rejected"""
    print("\n=== TEST 4: Duplicate name rejection ===")

    hand = ParsedHand(
        hand_id="SG1111111111",
        timestamp=datetime.now(),
        game_type="Hold'em No Limit",
        stakes="$0.10/$0.20",
        table_format="3-max",
        button_seat=1,
        seats=[
            Seat(seat_number=1, player_id="Hero", stack=100.0, position="BTN"),
            Seat(seat_number=2, player_id="player1", stack=200.0, position="SB"),
            Seat(seat_number=3, player_id="player2", stack=150.0, position="BB")
        ],
        board_cards=BoardCards(),
        actions=[],
        raw_text="""Poker Hand #SG1111111111: Hold'em No Limit ($0.10/$0.20) - 2025/09/29 15:30:00
Table 'Test' 3-max Seat #1 is the button
Seat 1: Hero (100 in chips)
Seat 2: player1 (200 in chips)
Seat 3: player2 (150 in chips)
player1: posts small blind $0.10
player2: posts big blind $0.20
"""
    )

    screenshot = ScreenshotAnalysis(
        screenshot_id="screenshot_004.png",
        hand_id="1111111111",
        player_names=["SameName", "SameName", "SameName"],  # All same name (bad match)
        hero_name="SameName",
        hero_position=1,
        all_player_stacks=[
            PlayerStack(player_name="SameName", stack=100.0, position=1),
            PlayerStack(player_name="SameName", stack=200.0, position=2),
            PlayerStack(player_name="SameName", stack=150.0, position=3)
        ],
        dealer_player="SameName",
        small_blind_player="SameName",
        big_blind_player="SameName"
    )

    mapping = _build_seat_mapping_by_roles(screenshot, hand)

    print(f"Mapping result: {mapping}")

    # Should return empty dict due to duplicate names
    assert len(mapping) == 0, f"Should return empty dict for duplicate names, got {len(mapping)} mappings"

    print("✅ TEST 4 PASSED: Duplicate names correctly rejected")


def run_all_tests():
    """Run all test cases"""
    print("=" * 60)
    print("TESTING ROLE-BASED SEAT MAPPING")
    print("=" * 60)

    try:
        test_role_based_mapping_complete()
        test_role_based_mapping_partial()
        test_role_based_fallback_to_counter_clockwise()
        test_duplicate_name_rejection()

        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print("\n" + "=" * 60)
        print(f"❌ TEST FAILED: {e}")
        print("=" * 60)
        return 1

    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
