#!/usr/bin/env python3
"""
Test script to verify matching improvements using Job 3 data
Uses existing OCR results from debug file to avoid re-running OCR
"""

import json
from parser import GGPokerParser
from models import ScreenshotAnalysis, BoardCards
from matcher import find_best_matches

# Load debug file
with open('/Users/nicodelgadob/ggrevealer-3-repl/ggrevealer_debug_job_3_1761627011591.json', 'r') as f:
    debug_data = json.load(f)

# Extract OCR results
ocr_results = debug_data['screenshots']['results']

# Parse TXT files
txt_files = debug_data['files']['txt_files']
all_hands = []

print("=" * 80)
print("PARSING TXT FILES")
print("=" * 80)

for txt_file in txt_files:
    file_path = txt_file['file_path']
    print(f"\nParsing: {txt_file['filename']}")

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    hands = GGPokerParser.parse_file(content)
    print(f"  → Found {len(hands)} hands")
    all_hands.extend(hands)

print(f"\n✅ Total hands parsed: {len(all_hands)}")

# Convert OCR results to ScreenshotAnalysis objects
screenshots = []

print("\n" + "=" * 80)
print("LOADING OCR RESULTS")
print("=" * 80)

for ocr_result in ocr_results:
    if not ocr_result['ocr_success']:
        continue

    ocr_data = ocr_result['ocr_data']

    # Convert board_cards dict to BoardCards object
    board_cards_dict = ocr_data.get('board_cards', {})

    screenshot = ScreenshotAnalysis(
        screenshot_id=ocr_data['screenshot_id'],
        hand_id=ocr_data.get('hand_id'),
        timestamp=ocr_data.get('timestamp'),
        table_name=ocr_data.get('table_name'),
        player_names=ocr_data.get('player_names', []),
        hero_name=ocr_data.get('hero_name'),
        hero_position=ocr_data.get('hero_position'),
        hero_stack=ocr_data.get('hero_stack', 0),
        hero_cards=ocr_data.get('hero_cards'),
        board_cards=board_cards_dict,
        all_player_stacks=ocr_data.get('all_player_stacks', []),
        confidence=ocr_data.get('confidence', 0),
        warnings=ocr_data.get('warnings', [])
    )

    screenshots.append(screenshot)
    print(f"\n✅ {ocr_result['screenshot_filename']}")
    print(f"   Hand ID: {ocr_data.get('hand_id')}")
    print(f"   Players: {', '.join(ocr_data.get('player_names', []))}")

print(f"\n✅ Total screenshots loaded: {len(screenshots)}")

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

# Group matches by type
hand_id_matches = [m for m in matches if 'hand_id_match' in m.score_breakdown]
filename_matches = [m for m in matches if 'filename_match' in m.score_breakdown]
fallback_matches = [m for m in matches if 'hand_id_match' not in m.score_breakdown and 'filename_match' not in m.score_breakdown]

print(f"   - Hand ID matches: {len(hand_id_matches)}")
print(f"   - Filename matches: {len(filename_matches)}")
print(f"   - Fallback matches: {len(fallback_matches)}")

# Check if the problematic screenshots matched
problematic_hand_ids = ['SG3260934198', 'SG3260947338']
matched_hand_ids = [m.hand_id for m in matches]

print("\n" + "=" * 80)
print("CHECKING PROBLEMATIC HANDS")
print("=" * 80)

for problem_id in problematic_hand_ids:
    if problem_id in matched_hand_ids:
        match = next(m for m in matches if m.hand_id == problem_id)
        print(f"\n✅ {problem_id} MATCHED!")
        print(f"   Screenshot: {match.screenshot_id}")
        print(f"   Confidence: {match.confidence:.1f}")
        print(f"   Score breakdown: {match.score_breakdown}")
        print(f"   Mappings: {match.auto_mapping}")
    else:
        print(f"\n❌ {problem_id} NOT MATCHED")

# Print unmapped players
print("\n" + "=" * 80)
print("ANALYZING COVERAGE")
print("=" * 80)

matched_hand_ids_set = set(matched_hand_ids)
unmatched_hands = [h for h in all_hands if h.hand_id not in matched_hand_ids_set]

print(f"\nUnmatched hands: {len(unmatched_hands)} of {len(all_hands)}")

# Get unique anonymized IDs from unmatched hands
unmapped_ids = set()
for hand in unmatched_hands:
    for seat in hand.seats:
        if seat.player_id != 'Hero':
            unmapped_ids.add(seat.player_id)

print(f"Unique unmapped player IDs: {len(unmapped_ids)}")
print(f"IDs: {', '.join(sorted(unmapped_ids))}")

print("\n" + "=" * 80)
print("TEST COMPLETE")
print("=" * 80)
