#!/usr/bin/env python3
"""Test prompt generation specifically for Job 7 (which has known issues)"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from main import _analyze_debug_data, _generate_fallback_prompt, _validate_generated_prompt

def test_job7():
    """Test with Job 7 which has unmapped players"""

    debug_file = Path("storage/debug/debug_job_7_20251028_055101.json")

    if not debug_file.exists():
        print(f"❌ Debug file not found: {debug_file}")
        return

    print(f"📂 Testing with: {debug_file}")
    print()

    # Analyze
    print("🔍 Analyzing Job 7 debug data...")
    detailed_analysis = _analyze_debug_data(str(debug_file))

    print(f"  Unmapped players: {len(detailed_analysis.get('unmapped_players', []))}")
    if detailed_analysis.get('unmapped_players'):
        for i, player in enumerate(detailed_analysis['unmapped_players'][:5], 1):
            print(f"    {i}. ID: {player.get('player_id')} | Table: {player.get('table')}")

    print(f"  Patterns detected: {len(detailed_analysis.get('patterns_detected', []))}")
    if detailed_analysis.get('patterns_detected'):
        for pattern in detailed_analysis['patterns_detected']:
            print(f"    - {pattern['pattern']}: {pattern.get('description', 'N/A')[:60]}...")

    print(f"  Priority issues: {len(detailed_analysis.get('priority_issues', []))}")
    if detailed_analysis.get('priority_issues'):
        for i, issue in enumerate(detailed_analysis['priority_issues'][:3], 1):
            print(f"    {i}. [{issue.get('severity')}] {issue.get('problem', 'N/A')[:60]}...")

    print()

    # Build context
    with open(debug_file, 'r') as f:
        debug_data = json.load(f)

    context = {
        "job_id": 7,
        "status": debug_data['job']['status'],
        "error_message": debug_data['job'].get('error_message'),
        "statistics": debug_data['result']['stats'] if debug_data.get('result') else {},
        "calculated_metrics": {
            "match_rate_percent": 0.6,  # Job 7 had low match rate
            "ocr_success_rate_percent": 95,
            "screenshot_success_rate_percent": 95
        },
        "debug_json_path": str(debug_file),
        "debug_json_filename": debug_file.name,
        "problem_indicators": ["LOW_MATCH_RATE"]
    }

    # Generate prompt
    print("📝 Generating prompt for Job 7...")
    prompt = _generate_fallback_prompt(context, detailed_analysis)
    print(f"  Generated {len(prompt)} characters")
    print()

    # Validate
    print("✅ Validating prompt...")
    validation = _validate_generated_prompt(prompt, detailed_analysis, str(debug_file))
    print(f"  Quality Score: {validation['quality_score']}/100")
    print(f"  Valid: {'✅ YES' if validation['valid'] else '❌ NO'}")

    if validation['issues']:
        print(f"  Issues:")
        for issue in validation['issues']:
            print(f"    ⚠️  {issue}")
    print()

    # Show key sections
    print("=" * 80)
    print("KEY SECTIONS IN GENERATED PROMPT:")
    print("=" * 80)

    # Check for unmapped players section
    if "### Jugadores Sin Mapear" in prompt:
        start = prompt.find("### Jugadores Sin Mapear")
        end = prompt.find("\n\n###", start + 1)
        if end == -1:
            end = start + 500
        print(prompt[start:end])
        print()

    # Check for patterns section
    if "### Patrones Detectados" in prompt:
        start = prompt.find("### Patrones Detectados")
        end = prompt.find("\n\n###", start + 1)
        if end == -1:
            end = start + 500
        print(prompt[start:end])
        print()

    # Check for priority issues section
    if "### Issues Priorizados" in prompt:
        start = prompt.find("### Issues Priorizados")
        end = prompt.find("\n\n##", start + 1)
        if end == -1:
            end = start + 500
        print(prompt[start:end])
        print()

    print("=" * 80)

    # Save
    output_file = Path("test_job7_generated_prompt.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(prompt)

    print(f"💾 Full prompt saved to: {output_file}")
    print()

    print("SUMMARY:")
    print(f"  Job 7 has {len(detailed_analysis.get('unmapped_players', []))} unmapped players")
    print(f"  Generated prompt is {len(prompt)} chars with quality score {validation['quality_score']}/100")
    print(f"  Prompt is {'✅ VALID' if validation['valid'] else '❌ INVALID'}")

if __name__ == "__main__":
    test_job7()
