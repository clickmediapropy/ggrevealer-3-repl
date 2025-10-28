"""
OCR screenshot analysis using Google Gemini 2.0 Flash Vision API
Optimized for PokerCraft screenshot analysis
"""

import os
import json
import asyncio
from pathlib import Path
from typing import Optional
import google.generativeai as genai
from models import ScreenshotAnalysis, PlayerStack


async def ocr_screenshot(image_path: str, screenshot_id: str, semaphore: Optional[asyncio.Semaphore] = None) -> ScreenshotAnalysis:
    """
    Analyze a poker screenshot using Gemini Vision
    
    Args:
        image_path: Path to the screenshot image
        screenshot_id: Unique identifier for this screenshot
        semaphore: Optional semaphore to limit concurrent requests
        
    Returns:
        ScreenshotAnalysis with extracted data
    """
    
    # Use semaphore if provided to limit concurrent requests
    async def _process():
        # Configure Gemini API
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key or api_key == 'your_gemini_api_key_here':
            print(f"⚠️  GEMINI_API_KEY not configured - returning mock data for {screenshot_id}")
            return _mock_ocr_result(screenshot_id)
        
        genai.configure(api_key=api_key)
        
        try:
            # Upload image (async)
            uploaded_file = await asyncio.to_thread(genai.upload_file, image_path)
            
            # Create model (Gemini 2.5 Flash Image Preview - optimal for vision tasks)
            model = genai.GenerativeModel('gemini-2-5-flash-image-preview')
            
            # Optimized prompt for poker screenshot OCR with Hand ID extraction
            prompt = """You are a specialized OCR system for poker hand screenshots from PokerCraft.

CRITICAL INSTRUCTIONS:
1. Extract the HAND ID number (usually at top of screenshot, format: #XXXXXXXXXX where X are digits)
2. Extract ALL visible player names EXACTLY as shown (case-sensitive)
3. Identify the HERO player (usually highlighted or has special indicator)
4. Extract hero's hole cards if visible
5. Extract community cards (flop, turn, river) if visible
6. Extract all player stack sizes
7. Be EXTREMELY careful with character disambiguation:
   - Letter O vs number 0
   - Letter I (uppercase i) vs number 1 vs letter l (lowercase L)
   - Letter S vs number 5
   - Letter Z vs number 2

HAND ID EXTRACTION:
- Look for "Hand #" or "#" followed by 10-12 digits at the top of the screenshot
- Extract ONLY the numeric portion (no "#" symbol)
- This is the MOST IMPORTANT field for matching accuracy
- Example: If you see "Hand #1234567890" extract "1234567890"

HERO IDENTIFICATION (CRITICAL):
- In PokerCraft screenshots, the HERO is ALWAYS at the BOTTOM CENTER position
- Hero position is ALWAYS 1 (this is a fixed layout convention)
- Hero may appear in different ways:
  1. Regular seat with name and stack (most common)
  2. WIN popup overlay at bottom center (shows name, cards, and stack)
  3. LOSE/FOLD popup overlay at bottom center
- If you see a WIN/LOSE popup at bottom center, extract that player's name as hero_name
- Even if Hero appears only in a popup, they MUST be included in all_player_stacks with position 1
- Hero position is ALWAYS 1 - do not set it to null

PLAYER POSITION RULES (3-max tables):
- Position 1: Bottom center (ALWAYS HERO)
- Position 2: Left side
- Position 3: Right side
- Extract ALL visible player names at ALL positions
- Include Hero in all_player_stacks even if they only appear in a popup

CARD FORMAT:
- Rank: A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2
- Suit: s (spades), h (hearts), d (diamonds), c (clubs)
- Example: "As Kh" means Ace of spades, King of hearts

PLAYER NAME RULES:
- Include all alphanumeric characters, underscores, hyphens, special characters (!, [], etc)
- Preserve exact capitalization
- DO NOT include position labels (BTN, SB, BB, etc) in names
- DO NOT include stack amounts in names

OUTPUT FORMAT (JSON):
{
  "hand_id": "1234567890",
  "hero_name": "PlayerName",
  "hero_position": 1,
  "hero_stack": 1234.56,
  "hero_cards": "As Kh",
  "player_names": ["HeroName", "Player2", "Player3"],
  "all_player_stacks": [
    {"player_name": "HeroName", "stack": 1234.56, "position": 1},
    {"player_name": "Player2", "stack": 2000.00, "position": 2},
    {"player_name": "Player3", "stack": 3000.00, "position": 3}
  ],
  "board_cards": {
    "flop1": "Ks",
    "flop2": "Qd",
    "flop3": "Jh",
    "turn": "9c",
    "river": "3s"
  },
  "table_name": "TableName",
  "confidence": 95,
  "warnings": []
}

VALIDATION RULES:
1. hand_id: 10-12 digit number (CRITICAL for matching)
2. hero_name MUST be in player_names list
3. hero_position is ALWAYS 1 (bottom center position)
4. Hero MUST appear in all_player_stacks with position 1
5. All player_names MUST have corresponding entries in all_player_stacks
6. position values: 1-3 for 3-max tables (1=bottom, 2=left, 3=right)
7. Stack values: positive numbers (can have decimals)
8. Cards: exactly 2 characters (rank + suit)
9. confidence: 0-100 (how confident you are in the extraction)
10. Add warnings for any uncertain extractions

If you cannot extract certain data, use null for that field EXCEPT:
- hero_position should ALWAYS be 1 (never null)
- If hand_id is not visible, set it to null (this will significantly reduce matching accuracy)
- If hero name cannot be identified, set hero_name to null BUT still set hero_position to 1
Always return valid JSON.

Analyze this poker screenshot and extract all data:"""

            # Generate response (async)
            response = await asyncio.to_thread(model.generate_content, [prompt, uploaded_file])
            
            # Parse JSON response
            try:
                # Extract JSON from response
                response_text = response.text.strip()
                
                # Remove markdown code blocks if present
                if response_text.startswith('```'):
                    response_text = response_text.split('```')[1]
                    if response_text.startswith('json'):
                        response_text = response_text[4:]
                    response_text = response_text.strip()
                
                data = json.loads(response_text)
                
                # Build PlayerStack objects
                player_stacks = []
                for ps_data in data.get('all_player_stacks', []):
                    player_stacks.append(PlayerStack(
                        player_name=ps_data['player_name'],
                        stack=float(ps_data['stack']),
                        position=int(ps_data['position'])
                    ))
                
                # Normalize hand_id (strip whitespace, ensure string format)
                raw_hand_id = data.get('hand_id')
                normalized_hand_id = None
                if raw_hand_id:
                    normalized_hand_id = str(raw_hand_id).strip()
                
                return ScreenshotAnalysis(
                    screenshot_id=screenshot_id,
                    hand_id=normalized_hand_id,
                    table_name=data.get('table_name'),
                    player_names=data.get('player_names', []),
                    hero_name=data.get('hero_name'),
                    hero_position=data.get('hero_position'),
                    hero_stack=data.get('hero_stack'),
                    hero_cards=data.get('hero_cards'),
                    board_cards=data.get('board_cards', {}),
                    all_player_stacks=player_stacks,
                    confidence=data.get('confidence', 0),
                    warnings=data.get('warnings', [])
                )
                
            except json.JSONDecodeError as e:
                print(f"❌ Failed to parse Gemini JSON response: {e}")
                print(f"Raw response: {response.text[:500]}")
                return ScreenshotAnalysis(
                    screenshot_id=screenshot_id,
                    confidence=0,
                    warnings=[f"JSON parse error: {str(e)}"]
                )
    
        except Exception as e:
            print(f"❌ OCR error for {screenshot_id}: {e}")
            return ScreenshotAnalysis(
                screenshot_id=screenshot_id,
                confidence=0,
                warnings=[f"OCR error: {str(e)}"]
            )
    
    # Execute with or without semaphore
    if semaphore:
        async with semaphore:
            return await _process()
    else:
        return await _process()


def _mock_ocr_result(screenshot_id: str) -> ScreenshotAnalysis:
    """Return mock OCR result when API key is not configured"""
    return ScreenshotAnalysis(
        screenshot_id=screenshot_id,
        hand_id="1234567890",
        table_name="MockTable",
        player_names=["MockPlayer1", "MockPlayer2", "Hero"],
        hero_name="Hero",
        hero_position=1,
        hero_stack=100.0,
        hero_cards="As Kh",
        board_cards={"flop1": "Qs", "flop2": "Jd", "flop3": "Th"},
        all_player_stacks=[
            PlayerStack(player_name="MockPlayer1", stack=50.0, position=2),
            PlayerStack(player_name="MockPlayer2", stack=75.0, position=3),
            PlayerStack(player_name="Hero", stack=100.0, position=1)
        ],
        confidence=0,
        warnings=["MOCK DATA - GEMINI_API_KEY not configured"]
    )
