#!/usr/bin/env python3
"""Test OCR fix for Hero position detection"""

import asyncio
import os
from dotenv import load_dotenv
from ocr import ocr_screenshot
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

async def test_screenshot():
    screenshot_path = Path("storage/uploads/7/screenshots/2025-10-27_10_55_AM_10_20_#SG3260931612.png")

    print(f"Testing OCR on: {screenshot_path.name}")
    print("=" * 80)

    result = await ocr_screenshot(str(screenshot_path), screenshot_path.name)

    print(f"\n✅ OCR Result:")
    print(f"   Hand ID: {result.hand_id}")
    print(f"   Hero Name: {result.hero_name}")
    print(f"   Hero Position: {result.hero_position}")
    print(f"   Player Names: {result.player_names}")
    print(f"\n   All Player Stacks:")
    for ps in result.all_player_stacks:
        print(f"      Position {ps.position}: {ps.player_name} (${ps.stack})")

    print(f"\n   Confidence: {result.confidence}")
    if result.warnings:
        print(f"   Warnings: {result.warnings}")

    # Verify the fix
    print("\n" + "=" * 80)
    print("VERIFICATION:")
    if result.hero_position == 1:
        print("✅ Hero position is 1 (correct!)")
    else:
        print(f"❌ Hero position is {result.hero_position} (should be 1)")

    if result.hero_name:
        print(f"✅ Hero name identified: {result.hero_name}")
    else:
        print("❌ Hero name is null")

    if len(result.all_player_stacks) == 3:
        print(f"✅ All 3 players extracted (expected: TuichAAreko, Buchmacher!, djjlb)")
    else:
        print(f"❌ Only {len(result.all_player_stacks)} players extracted (expected 3)")

    # Check if all expected names are present
    expected_names = {"TuichAAreko", "Buchmacher!", "djjlb"}
    extracted_names = {ps.player_name for ps in result.all_player_stacks}

    if expected_names == extracted_names:
        print(f"✅ All expected player names extracted!")
    else:
        print(f"⚠️  Player name mismatch:")
        print(f"   Expected: {expected_names}")
        print(f"   Extracted: {extracted_names}")
        print(f"   Missing: {expected_names - extracted_names}")
        print(f"   Extra: {extracted_names - expected_names}")

if __name__ == "__main__":
    asyncio.run(test_screenshot())
