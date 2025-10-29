"""
Test script to verify the new seat mapping logic with visual position calculation (clockwise)
"""

from models import ParsedHand, Seat, BoardCards, ScreenshotAnalysis, PlayerStack
from matcher import _build_seat_mapping
from datetime import datetime

# Simulate Hand #SG3261001347 from Job 3
# Table '12253', Button: Seat #3
test_hand = ParsedHand(
    hand_id="SG3261001347",
    timestamp=datetime.now(),
    game_type="Spin&Gold",
    stakes="$0.03/$0.06",
    table_format="3-max",
    button_seat=3,
    seats=[
        Seat(seat_number=1, player_id="e3efcaed", stack=500.0, position="SB"),
        Seat(seat_number=2, player_id="5641b4a0", stack=500.0, position="BB"),
        Seat(seat_number=3, player_id="Hero", stack=500.0, position="BTN"),
    ],
    board_cards=BoardCards(),
    actions=[],
    raw_text="Test hand",
    hero_cards="6d 4d"
)

# Simulate screenshot OCR result
# PokerCraft shows Hero at position 1 (visual), then players clockwise (Seat 3→2→1)
test_screenshot = ScreenshotAnalysis(
    screenshot_id="2025-10-27_11_27_AM_10_20_#SG3261001347.png",
    hand_id="3261001347",
    table_name="12253",
    player_names=["TuichAAreko", "v1[nn]1", "Gyodong22"],
    hero_name="TuichAAreko",
    hero_position=1,
    hero_stack=500.0,
    hero_cards="6d 4d",
    all_player_stacks=[
        PlayerStack(player_name="TuichAAreko", stack=500.0, position=1),  # Visual pos 1 = Hero = Seat 3
        PlayerStack(player_name="v1[nn]1", stack=500.0, position=2),       # Visual pos 2 = Seat 2 (clockwise from 3: 3→2)
        PlayerStack(player_name="Gyodong22", stack=500.0, position=3),     # Visual pos 3 = Seat 1 (clockwise from 2: 3→2→1)
    ],
    confidence=98
)

print("=" * 80)
print("TESTING NEW SEAT MAPPING LOGIC (Counter-clockwise from Hero)")
print("=" * 80)

print("\n📋 INPUT DATA:")
print(f"Hand ID: {test_hand.hand_id}")
print(f"Button Seat: #{test_hand.button_seat}")
print("\nHand Seats:")
for seat in test_hand.seats:
    print(f"  Seat {seat.seat_number}: {seat.player_id} ({seat.position})")

print("\nScreenshot Players (Visual Positions):")
for ps in test_screenshot.all_player_stacks:
    print(f"  Position {ps.position}: {ps.player_name}")

print("\n" + "=" * 80)
print("EXPECTED MAPPINGS:")
print("=" * 80)
print("  Hero (Seat 3) → TuichAAreko ✅")
print("  5641b4a0 (Seat 2, BB) → v1[nn]1 ✅")
print("  e3efcaed (Seat 1, SB) → Gyodong22 ✅")

print("\n" + "=" * 80)
print("ACTUAL MAPPING RESULT:")
print("=" * 80)

# Run the mapping function
mapping = _build_seat_mapping(test_hand, test_screenshot)

print("\n📊 MAPPING RESULT:")
if mapping:
    for anon_id, real_name in mapping.items():
        print(f"  {anon_id} → {real_name}")

    # Verify expected mappings
    print("\n✅ VERIFICATION:")
    success = True
    expected = {
        "Hero": "TuichAAreko",
        "5641b4a0": "v1[nn]1",
        "e3efcaed": "Gyodong22"
    }

    for anon_id, expected_name in expected.items():
        actual_name = mapping.get(anon_id)
        if actual_name == expected_name:
            print(f"  ✅ {anon_id} → {expected_name} (CORRECT)")
        else:
            print(f"  ❌ {anon_id} → {actual_name} (EXPECTED: {expected_name})")
            success = False

    if success and len(mapping) == 3:
        print("\n🎉 SUCCESS! All 3 players mapped correctly!")
    else:
        print("\n⚠️  PARTIAL SUCCESS or ERROR")
else:
    print("  ❌ ERROR: Mapping returned empty dict")

print("\n" + "=" * 80)
