#!/usr/bin/env python3
"""Quick test to verify the new Gemini model works"""

import asyncio
import os
from pathlib import Path
from ocr import ocr_screenshot

async def test_model():
    # Use first available screenshot
    test_image = "storage/uploads/7/screenshots/2025-10-27_10_59_AM_10_20_#SG3260934198.png"

    if not os.path.exists(test_image):
        print("❌ Test image not found")
        return

    print(f"🔍 Testing OCR with new model: gemini-2-5-flash-image-preview")
    print(f"📸 Image: {test_image}")
    print("⏳ Processing...")

    try:
        result = await ocr_screenshot(test_image, "test_1")

        print(f"\n✅ SUCCESS! Model returned a response.")
        print(f"\n📊 Extracted data:")
        print(f"  - Screenshot ID: {result.screenshot_id}")
        print(f"  - Hand ID: {result.hand_id or 'N/A'}")
        print(f"  - Timestamp: {result.timestamp or 'N/A'}")
        print(f"  - Hero Name: {result.hero_name or 'N/A'}")
        print(f"  - Hero Position: {result.hero_position or 'N/A'}")
        print(f"  - Hero Cards: {result.hero_cards or 'N/A'}")
        print(f"  - Confidence: {result.confidence}")
        print(f"  - Warnings: {len(result.warnings)}")

        if result.all_player_stacks:
            print(f"\n👥 Players ({len(result.all_player_stacks)}):")
            for player in result.all_player_stacks:
                print(f"  - {player.player_name} (Pos {player.position}): ${player.stack}")

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_model())
