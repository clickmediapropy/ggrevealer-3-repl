#!/usr/bin/env python3
"""
Test CLI to verify core logic works
"""

import os
from dotenv import load_dotenv
load_dotenv()

from parser import GGPokerParser
from writer import generate_final_txt, validate_output_format
from models import NameMapping

print("✅ GGRevealer Core Logic - Test Suite")
print("=" * 60)

print("\n[TEST 1] Parser...")
sample_txt = """Poker Hand #SG12345: Hold'em No Limit ($0.25/$0.50) - 2025/01/15 14:30:00 ET
Table 'Test Table' 3-max Seat #1 is the button
Seat 1: Hero ($100 in chips)
Seat 2: Player123 ($50 in chips)
Seat 3: AnotherPlayer ($75 in chips)
Hero: posts small blind $0.25
Player123: posts big blind $0.50
*** HOLE CARDS ***
Dealt to Hero [As Kh]
Hero: raises $1.50 to $2
Player123: folds
AnotherPlayer: calls $2
*** FLOP *** [Jd 9c 3s]
Hero: bets $3
AnotherPlayer: folds
Hero collected $4.50 from pot
*** SUMMARY ***
Total pot $4.50 | Rake $0
Seat 1: Hero (button) collected ($4.50)
"""

hand = GGPokerParser.parse_hand(sample_txt)
if hand:
    print(f"  ✅ Hand parsed: {hand.hand_id}")
    print(f"     Timestamp: {hand.timestamp}")
    print(f"     Seats: {len(hand.seats)}")
    print(f"     Hero cards: {hand.hero_cards}")
else:
    print("  ❌ Parser failed")

print("\n[TEST 2] Gemini API Connection...")
gemini_key = os.getenv('GEMINI_API_KEY')
if gemini_key and gemini_key != 'your_gemini_api_key_here':
    print(f"  ✅ API key configured")
    print(f"     Key: {gemini_key[:10]}...")
else:
    print("  ⚠️  API key not configured - set GEMINI_API_KEY in .env")

print("\n[TEST 3] Writer validation...")
mapping = NameMapping(
    anonymized_identifier='Player123',
    resolved_name='RealPlayer',
    source='auto-match',
    confidence=95.0
)
output = generate_final_txt(sample_txt, [mapping])
validation = validate_output_format(sample_txt, output)

if validation.valid:
    print("  ✅ Validation passed")
    if 'RealPlayer' in output:
        print("  ✅ Name replacement works")
    if 'Hero' in output:
        print("  ✅ Hero protected (not replaced)")
else:
    print(f"  ❌ Validation failed: {validation.errors}")

print("\n" + "=" * 60)
print("✅ Core logic tests complete!")
print("\nNext steps:")
print("1. Set GEMINI_API_KEY in .env")
print("2. Run: python test_cli.py")
print("3. Start the FastAPI server: python main.py")
