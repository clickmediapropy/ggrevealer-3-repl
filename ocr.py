"""
OCR screenshot analysis using Google Gemini 2.0 Flash Vision API
Optimized for PokerCraft screenshot analysis
"""

import os
import json
from pathlib import Path
from typing import Optional
import google.generativeai as genai
from models import ScreenshotAnalysis, PlayerStack


def ocr_screenshot(image_path: str, screenshot_id: str) -> ScreenshotAnalysis:
    """
    Analyze a poker screenshot using Gemini Vision
    
    Args:
        image_path: Path to the screenshot image
        screenshot_id: Unique identifier for this screenshot
        
    Returns:
        ScreenshotAnalysis with extracted data
    """
    
    # Configure Gemini API
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key or api_key == 'your_gemini_api_key_here':
        print(f"⚠️  GEMINI_API_KEY not configured - returning mock data for {screenshot_id}")
        return _mock_ocr_result(screenshot_id)
    
    genai.configure(api_key=api_key)
    
    try:
        # Upload image
        uploaded_file = genai.upload_file(image_path)
        
        # Create model
        model = genai.GenerativeModel('gemini-2.5-flash-preview-image')
        
        # Optimized 78-line prompt for poker screenshot OCR
        prompt = """You are a specialized OCR system for poker hand screenshots from PokerCraft.

CRITICAL INSTRUCTIONS:
1. Extract ALL visible player names EXACTLY as shown (case-sensitive)
2. Identify the HERO player (usually highlighted or has special indicator)
3. Extract hero's hole cards if visible
4. Extract community cards (flop, turn, river) if visible
5. Extract all player stack sizes
6. Be EXTREMELY careful with character disambiguation:
   - Letter O vs number 0
   - Letter I (uppercase i) vs number 1 vs letter l (lowercase L)
   - Letter S vs number 5
   - Letter Z vs number 2

CARD FORMAT:
- Rank: A, K, Q, J, T, 9, 8, 7, 6, 5, 4, 3, 2
- Suit: s (spades), h (hearts), d (diamonds), c (clubs)
- Example: "As Kh" means Ace of spades, King of hearts

PLAYER NAME RULES:
- Include all alphanumeric characters, underscores, hyphens
- Preserve exact capitalization
- DO NOT include position labels (BTN, SB, BB, etc) in names
- DO NOT include stack amounts in names

OUTPUT FORMAT (JSON):
{
  "hero_name": "PlayerName",
  "hero_position": 1,
  "hero_stack": 1234.56,
  "hero_cards": "As Kh",
  "player_names": ["Player1", "Player2", "Hero"],
  "all_player_stacks": [
    {"player_name": "Player1", "stack": 1000.00, "position": 1},
    {"player_name": "Player2", "stack": 2000.00, "position": 2}
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
1. hero_name MUST be in player_names list
2. All player_names MUST have corresponding entries in all_player_stacks
3. position values: 1-6 for seat numbers
4. Stack values: positive numbers (can have decimals)
5. Cards: exactly 2 characters (rank + suit)
6. confidence: 0-100 (how confident you are in the extraction)
7. Add warnings for any uncertain extractions

If you cannot extract certain data, use null for that field.
If hero is not identifiable, set hero_name to null.
Always return valid JSON.

Analyze this poker screenshot and extract all data:"""

        # Generate response
        response = model.generate_content([prompt, uploaded_file])
        
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
            
            return ScreenshotAnalysis(
                screenshot_id=screenshot_id,
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


def _mock_ocr_result(screenshot_id: str) -> ScreenshotAnalysis:
    """Return mock OCR result when API key is not configured"""
    return ScreenshotAnalysis(
        screenshot_id=screenshot_id,
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
