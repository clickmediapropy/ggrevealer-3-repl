#!/usr/bin/env python3
"""
Simple test to verify hand_id normalization is working
"""

from matcher import _normalize_hand_id

# Test cases
test_cases = [
    ("SG3260934198", "3260934198", "Should remove SG prefix"),
    ("3260934198", "3260934198", "Should keep numeric-only ID"),
    ("SG3260947338", "3260947338", "Should remove SG prefix"),
    ("HH1234567890", "1234567890", "Should remove HH prefix"),
    ("1234567890", "1234567890", "Should keep numeric-only ID"),
    ("", "", "Should handle empty string"),
    (None, "", "Should handle None"),
]

print("=" * 80)
print("TESTING HAND ID NORMALIZATION")
print("=" * 80)

all_passed = True

for input_id, expected, description in test_cases:
    result = _normalize_hand_id(input_id) if input_id is not None else _normalize_hand_id("")
    passed = result == expected
    all_passed = all_passed and passed

    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"\n{status} {description}")
    print(f"   Input:    {repr(input_id)}")
    print(f"   Expected: {repr(expected)}")
    print(f"   Got:      {repr(result)}")

print("\n" + "=" * 80)
if all_passed:
    print("✅ ALL TESTS PASSED")
else:
    print("❌ SOME TESTS FAILED")
print("=" * 80)

# Test matching scenario
print("\n" + "=" * 80)
print("TESTING MATCHING SCENARIO")
print("=" * 80)

parser_id = "SG3260934198"  # From hand history
ocr_id = "3260934198"       # From OCR (without prefix)

normalized_parser = _normalize_hand_id(parser_id)
normalized_ocr = _normalize_hand_id(ocr_id)

print(f"\nParser extracts:  {repr(parser_id)}")
print(f"OCR extracts:     {repr(ocr_id)}")
print(f"\nAfter normalization:")
print(f"Parser →          {repr(normalized_parser)}")
print(f"OCR →             {repr(normalized_ocr)}")
print(f"\nMatch result:     {normalized_parser == normalized_ocr}")

if normalized_parser == normalized_ocr:
    print("✅ IDs will match correctly!")
else:
    print("❌ IDs will NOT match")

print("\n" + "=" * 80)
