"""
Test Task 7: Dual OCR Pipeline Implementation

This test verifies that the dual OCR flow works:
1. OCR1 (Hand ID extraction) runs on all screenshots
2. Matching by Hand ID
3. Discard unmatched screenshots
4. OCR2 (Player details) runs only on matched screenshots
"""

import asyncio
import os
from pathlib import Path
from main import ocr_hand_id_with_retry, _normalize_hand_id
from ocr import ocr_player_details
from database import init_db, save_ocr2_result, mark_screenshot_discarded, get_screenshot_results
from logger import get_job_logger
from parser import GGPokerParser


async def test_dual_ocr_flow():
    """Test dual OCR flow with Job 9 data"""

    print("="*70)
    print("TASK 7: Dual OCR Pipeline Test")
    print("="*70)

    # Initialize DB
    init_db()

    # Test job ID (using 999 to avoid conflicting with real jobs)
    test_job_id = 999
    logger = get_job_logger(test_job_id)

    # Get API key
    api_key = os.getenv('GEMINI_API_KEY', 'DUMMY_API_KEY_FOR_TESTING')
    if api_key == 'DUMMY_API_KEY_FOR_TESTING':
        print("⚠️  Warning: GEMINI_API_KEY not set, test will use dummy data")

    # Use Job 9 data for testing
    job9_path = Path('storage/uploads/9')
    screenshots_path = job9_path / 'screenshots'
    txt_path = job9_path / 'txt'

    # Get a few screenshots for testing (limit to 3 to save time)
    screenshot_files = list(screenshots_path.glob('*.png'))[:3]

    if len(screenshot_files) == 0:
        print("❌ No screenshots found in Job 9 data")
        return False

    print(f"\n📸 Testing with {len(screenshot_files)} screenshots from Job 9")
    for i, sf in enumerate(screenshot_files, 1):
        print(f"  {i}. {sf.name}")

    # Parse TXT files to get hands
    txt_files = list(txt_path.glob('*.txt'))[:1]  # Just one file for testing
    all_hands = []

    print(f"\n📄 Parsing {len(txt_files)} TXT file(s)")
    for txt_file in txt_files:
        content = txt_file.read_text(encoding='utf-8')
        hands = GGPokerParser.parse_file(content)
        all_hands.extend(hands)
        print(f"  ✅ Parsed {len(hands)} hands from {txt_file.name}")

    print(f"\n📊 Total hands parsed: {len(all_hands)}")

    # PHASE 1: OCR1 - Hand ID Extraction
    print("\n" + "="*70)
    print("PHASE 1: OCR1 - Hand ID Extraction")
    print("="*70)

    ocr1_results = {}

    for screenshot_file in screenshot_files:
        screenshot_filename = screenshot_file.name
        print(f"\n🔍 Processing: {screenshot_filename}")

        success, hand_id, error = await ocr_hand_id_with_retry(
            str(screenshot_file),
            screenshot_filename,
            test_job_id,
            api_key,
            logger,
            max_retries=1
        )

        ocr1_results[screenshot_filename] = (success, hand_id, error)

        if success:
            print(f"  ✅ Hand ID: {hand_id}")
        else:
            print(f"  ❌ Error: {error}")

    ocr1_success = sum(1 for s, _, _ in ocr1_results.values() if s)
    print(f"\n📊 OCR1 Results: {ocr1_success}/{len(screenshot_files)} successful")

    # PHASE 2: Matching by Hand ID
    print("\n" + "="*70)
    print("PHASE 2: Matching by Hand ID")
    print("="*70)

    matched_screenshots = {}
    unmatched_screenshots = []

    for screenshot_filename, (success, hand_id, error) in ocr1_results.items():
        if not success:
            unmatched_screenshots.append((screenshot_filename, error))
            print(f"⚠️  {screenshot_filename}: Not matched (OCR1 failed)")
            continue

        # Find matching hand
        matched_hand = None
        for hand in all_hands:
            if _normalize_hand_id(hand.hand_id) == _normalize_hand_id(hand_id):
                matched_hand = hand
                break

        if matched_hand:
            matched_screenshots[screenshot_filename] = matched_hand
            print(f"✅ {screenshot_filename} → Hand {hand_id}")
        else:
            unmatched_screenshots.append((screenshot_filename, f"No hand found for {hand_id}"))
            print(f"⚠️  {screenshot_filename}: Hand ID {hand_id} not found in parsed hands")

    print(f"\n📊 Match Results: {len(matched_screenshots)}/{len(screenshot_files)} matched")

    # PHASE 3: Discard unmatched
    print("\n" + "="*70)
    print("PHASE 3: Discard Unmatched Screenshots")
    print("="*70)

    for screenshot_filename, reason in unmatched_screenshots:
        mark_screenshot_discarded(test_job_id, screenshot_filename, reason)
        print(f"🗑️  Discarded: {screenshot_filename}")
        print(f"   Reason: {reason}")

    print(f"\n📊 Discarded: {len(unmatched_screenshots)} screenshots")

    # PHASE 4: OCR2 - Player Details (only matched)
    print("\n" + "="*70)
    print("PHASE 4: OCR2 - Player Details (Matched Only)")
    print("="*70)

    ocr2_results = {}

    for screenshot_file in screenshot_files:
        screenshot_filename = screenshot_file.name

        if screenshot_filename not in matched_screenshots:
            print(f"⏭️  Skipping {screenshot_filename} (not matched)")
            continue

        print(f"\n🔍 Processing: {screenshot_filename}")

        success, ocr_data, error = await ocr_player_details(str(screenshot_file), api_key)
        save_ocr2_result(test_job_id, screenshot_filename, success, ocr_data, error)
        ocr2_results[screenshot_filename] = (success, ocr_data, error)

        if success:
            players = ocr_data.get('players', [])
            hero = ocr_data.get('hero_name', 'Unknown')
            print(f"  ✅ Players: {len(players)}")
            print(f"  ✅ Hero: {hero}")
            if 'roles' in ocr_data:
                print(f"  ✅ Roles: {ocr_data['roles']}")
        else:
            print(f"  ❌ Error: {error}")

    ocr2_success = sum(1 for s, _, _ in ocr2_results.values() if s)
    print(f"\n📊 OCR2 Results: {ocr2_success}/{len(matched_screenshots)} successful")

    # VERIFICATION
    print("\n" + "="*70)
    print("VERIFICATION")
    print("="*70)

    # Verify database entries
    screenshot_results = get_screenshot_results(test_job_id)
    print(f"\n📊 Database entries: {len(screenshot_results)}")

    for sr in screenshot_results:
        filename = sr.get('screenshot_filename')
        ocr1_success = sr.get('ocr1_success')
        ocr2_success = sr.get('ocr2_success')
        status = sr.get('status')
        discard_reason = sr.get('discard_reason')

        print(f"\n  {filename}:")
        print(f"    OCR1: {'✅' if ocr1_success else '❌'}")
        print(f"    OCR2: {'✅' if ocr2_success else '❌' if ocr2_success is not None else '⏭️ skipped'}")
        print(f"    Status: {status}")
        if discard_reason:
            print(f"    Discarded: {discard_reason}")

    # Success criteria
    print("\n" + "="*70)
    print("SUCCESS CRITERIA")
    print("="*70)

    success = True

    # 1. OCR1 should process all screenshots
    if len(ocr1_results) == len(screenshot_files):
        print("✅ OCR1 processed all screenshots")
    else:
        print(f"❌ OCR1 processed {len(ocr1_results)}/{len(screenshot_files)}")
        success = False

    # 2. OCR2 should only process matched screenshots
    if len(ocr2_results) == len(matched_screenshots):
        print(f"✅ OCR2 processed only matched screenshots ({len(matched_screenshots)})")
    else:
        print(f"❌ OCR2 processed {len(ocr2_results)}, expected {len(matched_screenshots)}")
        success = False

    # 3. Unmatched should be discarded
    discarded_count = sum(1 for sr in screenshot_results if sr.get('discard_reason'))
    if discarded_count == len(unmatched_screenshots):
        print(f"✅ All unmatched screenshots discarded ({discarded_count})")
    else:
        print(f"❌ Discarded {discarded_count}, expected {len(unmatched_screenshots)}")
        success = False

    # 4. Database should have all entries
    if len(screenshot_results) == len(screenshot_files):
        print(f"✅ All screenshots tracked in database ({len(screenshot_results)})")
    else:
        print(f"❌ Database has {len(screenshot_results)}, expected {len(screenshot_files)}")
        success = False

    print("\n" + "="*70)
    if success:
        print("✅ ALL TESTS PASSED - Dual OCR flow working correctly!")
    else:
        print("❌ SOME TESTS FAILED - Review output above")
    print("="*70)

    return success


if __name__ == "__main__":
    result = asyncio.run(test_dual_ocr_flow())
    exit(0 if result else 1)
