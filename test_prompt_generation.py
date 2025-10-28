#!/usr/bin/env python3
"""Test the improved prompt generation function"""

import sys
import os
import json
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Import the functions we need
from main import _analyze_debug_data, _generate_fallback_prompt, _validate_generated_prompt

def test_prompt_generation():
    """Test prompt generation with a real debug JSON file"""

    # Find the most recent debug JSON file
    debug_dir = Path("storage/debug")
    if not debug_dir.exists():
        print("❌ Debug directory not found")
        return

    debug_files = list(debug_dir.glob("debug_job_*.json"))
    if not debug_files:
        print("❌ No debug JSON files found")
        return

    # Use the most recent one
    latest_debug = max(debug_files, key=lambda p: p.stat().st_mtime)
    print(f"📂 Using debug file: {latest_debug}")
    print()

    # Step 1: Analyze the debug data
    print("🔍 Step 1: Analyzing debug data...")
    detailed_analysis = _analyze_debug_data(str(latest_debug))

    print(f"  ✅ Found {len(detailed_analysis.get('unmapped_players', []))} unmapped players")
    print(f"  ✅ Found {len(detailed_analysis.get('patterns_detected', []))} patterns")
    print(f"  ✅ Found {len(detailed_analysis.get('priority_issues', []))} priority issues")
    print(f"  ✅ Found {len(detailed_analysis.get('validation_errors', []))} validation errors")
    print(f"  ✅ Found {len(detailed_analysis.get('screenshot_failures', []))} screenshot failures")
    print()

    # Step 2: Generate fallback prompt
    print("📝 Step 2: Generating fallback prompt...")

    # Build minimal context (like the API endpoint does)
    with open(latest_debug, 'r') as f:
        debug_data = json.load(f)

    context = {
        "job_id": debug_data['job']['id'],
        "status": debug_data['job']['status'],
        "error_message": debug_data['job'].get('error_message'),
        "statistics": debug_data['result']['stats'] if debug_data.get('result') else {},
        "calculated_metrics": {
            "match_rate_percent": 0,
            "ocr_success_rate_percent": 0,
            "screenshot_success_rate_percent": 0
        },
        "debug_json_path": str(latest_debug),
        "debug_json_filename": latest_debug.name
    }

    prompt = _generate_fallback_prompt(context, detailed_analysis)
    print(f"  ✅ Generated prompt ({len(prompt)} characters)")
    print()

    # Step 3: Validate the prompt
    print("✅ Step 3: Validating prompt quality...")
    validation = _validate_generated_prompt(prompt, detailed_analysis, str(latest_debug))

    print(f"  Quality Score: {validation['quality_score']}/100")
    print(f"  Valid: {validation['valid']}")

    if validation['issues']:
        print(f"  Issues found:")
        for issue in validation['issues']:
            print(f"    ⚠️  {issue}")
    else:
        print(f"  ✅ No issues found!")
    print()

    # Step 4: Show prompt preview
    print("📄 Step 4: Prompt Preview (first 1000 chars):")
    print("=" * 80)
    print(prompt[:1000])
    print("..." if len(prompt) > 1000 else "")
    print("=" * 80)
    print()

    # Step 5: Save full prompt to file
    output_file = Path("test_generated_prompt.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(prompt)

    print(f"💾 Full prompt saved to: {output_file}")
    print()

    # Summary
    print("=" * 80)
    print("SUMMARY:")
    print(f"  Debug File: {latest_debug.name}")
    print(f"  Job ID: {context['job_id']}")
    print(f"  Prompt Length: {len(prompt)} chars")
    print(f"  Quality Score: {validation['quality_score']}/100")
    print(f"  Valid: {'✅ YES' if validation['valid'] else '❌ NO'}")
    print("=" * 80)

if __name__ == "__main__":
    test_prompt_generation()
