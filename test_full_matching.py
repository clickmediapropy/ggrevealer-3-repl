#!/usr/bin/env python3
"""
Full matching test using Job 3 files and simulated OCR results
"""

import glob
from parser import GGPokerParser
from models import ScreenshotAnalysis, PlayerStack
from matcher import find_best_matches

# Simulated OCR results (from the problematic screenshots)
ocr_results = [
    {
        "screenshot_id": "2025-10-27_10_59_AM_10_20_#SG3260934198.png",
        "hand_id": "3260934198",  # OCR extracts without SG prefix
        "hero_name": "TuichAAreko",
        "hero_position": 1,
        "hero_stack": 300,
        "hero_cards": "3c 2d",
        "player_names": ["Mnajchu", "Gyluwan", "TuichAAreko"],
        "all_player_stacks": [
            {"player_name": "Mnajchu", "stack": 280, "position": 2},
            {"player_name": "Gyluwan", "stack": 280, "position": 3},
            {"player_name": "TuichAAreko", "stack": 300, "position": 1}
        ],
        "board_cards": {
            "flop1": "8d", "flop2": "Qd", "flop3": "5s",
            "turn": "7c", "river": "Jc"
        }
    },
    {
        "screenshot_id": "2025-10-27_11_16_AM_10_20_#SG3260947338.png",
        "hand_id": "3260947338",  # OCR extracts without SG prefix
        "hero_name": "TuichAAreko",
        "hero_position": 1,
        "hero_stack": 480,
        "hero_cards": "Qs 9c",
        "player_names": ["TuichAAreko", "DennLSDy", "Snowy26"],
        "all_player_stacks": [
            {"player_name": "TuichAAreko", "stack": 480, "position": 1},
            {"player_name": "DennLSDy", "stack": 480, "position": 2},
            {"player_name": "Snowy26", "stack": 500, "position": 3}
        ],
        "board_cards": {
            "flop1": "Ks", "flop2": "Qd", "flop3": "Qh",
            "turn": None, "river": None
        }
    },
    {
        "screenshot_id": "2025-10-27_11_30_AM_10_20_#SG3261002599.png",
        "hand_id": "3261002599",
        "hero_name": "TuichAAreko",
        "hero_position": 2,
        "hero_stack": 0,
        "hero_cards": "Ah Ad",
        "player_names": ["50Zoos", "vdibv", "TuichAAreko"],
        "all_player_stacks": [
            {"player_name": "50Zoos", "stack": 480, "position": 1},
            {"player_name": "vdibv", "stack": 0, "position": 3},
            {"player_name": "TuichAAreko", "stack": 0, "position": 2}
        ],
        "board_cards": {
            "flop1": "8h", "flop2": "Qh", "flop3": "Ts",
            "turn": "5h", "river": "Jd"
        }
    }
]

# Parse TXT files
txt_files = glob.glob('storage/uploads/3/txt/*.txt')
all_hands = []

print("=" * 80)
print("PARSING TXT FILES")
print("=" * 80)

for txt_path in sorted(txt_files):
    filename = txt_path.split('/')[-1]
    print(f"\nParsing: {filename}")

    with open(txt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    hands = GGPokerParser.parse_file(content)
    print(f"  → Found {len(hands)} hands")

    # Check if problematic hand IDs exist
    for hand in hands:
        if hand.hand_id in ['SG3260934198', 'SG3260947338']:
            print(f"  ✅ Found problematic hand: {hand.hand_id}")
            print(f"     Seats: {[(s.seat_number, s.player_id) for s in hand.seats]}")

    all_hands.extend(hands)

print(f"\n✅ Total hands parsed: {len(all_hands)}")

# Convert OCR results to ScreenshotAnalysis objects
screenshots = []

print("\n" + "=" * 80)
print("CREATING SCREENSHOT ANALYSIS OBJECTS")
print("=" * 80)

for ocr_data in ocr_results:
    # Convert player_stacks dicts to PlayerStack objects
    player_stacks = [
        PlayerStack(
            player_name=ps['player_name'],
            stack=ps['stack'],
            position=ps['position']
        )
        for ps in ocr_data.get('all_player_stacks', [])
    ]

    screenshot = ScreenshotAnalysis(
        screenshot_id=ocr_data['screenshot_id'],
        hand_id=ocr_data.get('hand_id'),
        timestamp=None,
        table_name="HH Spin & Gold",
        player_names=ocr_data.get('player_names', []),
        hero_name=ocr_data.get('hero_name'),
        hero_position=ocr_data.get('hero_position'),
        hero_stack=ocr_data.get('hero_stack', 0),
        hero_cards=ocr_data.get('hero_cards'),
        board_cards=ocr_data.get('board_cards', {}),
        all_player_stacks=player_stacks,
        confidence=95,
        warnings=[]
    )

    screenshots.append(screenshot)
    print(f"\n✅ {ocr_data['screenshot_id']}")
    print(f"   Hand ID (OCR): {ocr_data.get('hand_id')}")
    print(f"   Hero: {ocr_data.get('hero_name')} at position {ocr_data.get('hero_position')}")
    print(f"   Players: {', '.join(ocr_data.get('player_names', []))}")

print(f"\n✅ Total screenshots: {len(screenshots)}")

# Run matching
print("\n" + "=" * 80)
print("RUNNING MATCHING ALGORITHM")
print("=" * 80)

matches = find_best_matches(all_hands, screenshots, confidence_threshold=50.0)

# Print results
print("\n" + "=" * 80)
print("MATCHING RESULTS")
print("=" * 80)

print(f"\n✅ Total matches: {len(matches)}")

# Check if the problematic screenshots matched
problematic_hand_ids = ['SG3260934198', 'SG3260947338']
matched_hand_ids = [m.hand_id for m in matches]

print("\n" + "=" * 80)
print("CHECKING PROBLEMATIC HANDS (KEY TEST)")
print("=" * 80)

success_count = 0
for problem_id in problematic_hand_ids:
    if problem_id in matched_hand_ids:
        match = next(m for m in matches if m.hand_id == problem_id)
        print(f"\n✅ {problem_id} MATCHED!")
        print(f"   Screenshot: {match.screenshot_id}")
        print(f"   Confidence: {match.confidence:.1f}")
        print(f"   Method: {list(match.score_breakdown.keys())}")
        print(f"   Mappings: {match.auto_mapping}")
        success_count += 1
    else:
        print(f"\n❌ {problem_id} NOT MATCHED")

print("\n" + "=" * 80)
if success_count == len(problematic_hand_ids):
    print("✅✅✅ SUCCESS! All problematic hands now match! ✅✅✅")
else:
    print(f"⚠️  {success_count}/{len(problematic_hand_ids)} problematic hands matched")
print("=" * 80)
