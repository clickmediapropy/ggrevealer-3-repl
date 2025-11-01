"""
Error Analyzer Module for PT4 Error Recovery System

Uses Gemini AI to analyze PT4 errors with full job context:
- Parsed hands structure
- OCR extraction results
- Current player mappings
- Error details

Determines root cause, affected phase, confidence, and suggested fixes.

Author: Claude Code
Date: 2025-11-01
"""

import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from error_parser import PTError


@dataclass
class ErrorAnalysis:
    """Analysis result for a single PT4 error

    Attributes:
        error_type: Type of error (duplicate_player, invalid_pot, etc.)
        root_cause: Explanation of why the error occurred
        affected_phase: Which pipeline phase failed (parser/matcher/ocr/writer)
        confidence: Confidence in the analysis (0.0-1.0)
        suggested_fix: Human-readable description of the fix
        auto_fixable: Whether system can automatically apply the fix
        fix_code: Machine-readable action code for repair executor
    """
    error_type: str
    root_cause: str
    affected_phase: str  # parser, matcher, ocr, writer
    confidence: float  # 0.0 - 1.0
    suggested_fix: str
    auto_fixable: bool
    fix_code: Optional[str] = None


def build_analysis_prompt(
    errors: Dict[str, List[PTError]],
    parsed_hands: List[Dict],
    ocr_results: List[Dict],
    current_mappings: Dict[str, Dict[str, str]]
) -> str:
    """Build comprehensive Gemini prompt with all job context

    Args:
        errors: Dictionary mapping filename → list of PTError objects
        parsed_hands: List of parsed hand structures from parser
        ocr_results: List of OCR extraction results from screenshots
        current_mappings: Dictionary of current anonymized_id → real_name mappings

    Returns:
        Complete prompt string for Gemini analysis

    Example:
        >>> prompt = build_analysis_prompt(errors, hands, ocr, mappings)
        >>> "CONTEXT:" in prompt
        True
    """
    # Convert errors to serializable format
    errors_dict = {}
    for filename, error_list in errors.items():
        errors_dict[filename] = [
            {
                "hand_id": e.hand_id,
                "error_type": e.error_type,
                "line_number": e.line_number,
                "raw_message": e.raw_message,
                "player_name": e.player_name,
                "seats_involved": e.seats_involved,
                "expected_pot": e.expected_pot,
                "found_pot": e.found_pot,
                "unmapped_id": e.unmapped_id
            }
            for e in error_list
        ]

    prompt = f"""You are analyzing PokerTracker import errors for GGPoker hand histories.

CONTEXT:

**Parsed Hands:**
{json.dumps(parsed_hands, indent=2)}

**OCR Results:**
{json.dumps(ocr_results, indent=2)}

**Current Mappings:**
{json.dumps(current_mappings, indent=2)}

**ERRORS TO ANALYZE:**
{json.dumps(errors_dict, indent=2)}

---

For EACH error, determine:

1. **Root cause**: Why did this error happen? What went wrong in the pipeline?

2. **Affected phase**: Which phase of the pipeline failed?
   - `parser`: Hand history parsing, pot calculation, blind detection
   - `matcher`: Hand-to-screenshot matching
   - `ocr`: OCR extraction of player names from screenshots
   - `writer`: Hand history output generation

3. **Confidence**: How confident are you in this analysis? (0.0-1.0)
   - 0.9-1.0: Very confident, clear evidence
   - 0.7-0.9: Confident, strong indicators
   - 0.5-0.7: Moderately confident, some uncertainty
   - <0.5: Low confidence, need more information

4. **Suggested fix**: What specific action should be taken to fix this error?

5. **Auto-fixable**: Can the system automatically apply this fix? (true/false)
   - `true`: System can execute fix without user intervention
   - `false`: Requires manual intervention (e.g., upload new screenshot)

6. **Fix code**: Machine-readable action code (e.g., "remove_duplicate_mapping", "recalculate_pot", "add_cash_drop_fee")

---

**Output JSON format:**

```json
{{
  "hand_id_1": {{
    "error_type": "duplicate_player",
    "root_cause": "Explanation of why this happened",
    "affected_phase": "matcher",
    "confidence": 0.95,
    "suggested_fix": "Human-readable description",
    "auto_fixable": true,
    "fix_code": "remove_duplicate_mapping"
  }},
  "hand_id_2": {{
    "error_type": "invalid_pot",
    "root_cause": "Cash Drop fee (1BB on pots >30BB) not included",
    "affected_phase": "parser",
    "confidence": 0.88,
    "suggested_fix": "Add jackpot fee to pot calculation",
    "auto_fixable": true,
    "fix_code": "add_cash_drop_fee"
  }}
}}
```

**Common Error Patterns:**

- **Duplicate Player**: Usually caused by screenshot matched to wrong hand (matcher phase)
- **Invalid Pot**: Often Cash Drop fee missing on large pots (parser phase)
- **Unmapped ID**: Missing screenshot or OCR failure (ocr phase)

Return ONLY the JSON object with analyses for each error. No additional text.
"""

    return prompt


def parse_gemini_response(response_text: str) -> Dict[str, ErrorAnalysis]:
    """Parse Gemini's JSON response into ErrorAnalysis objects

    Args:
        response_text: Raw JSON text from Gemini API

    Returns:
        Dictionary mapping hand_id → ErrorAnalysis object

    Raises:
        ValueError: If response is not valid JSON
        KeyError: If required fields are missing

    Example:
        >>> response = '{"SG123": {"root_cause": "...", ...}}'
        >>> analyses = parse_gemini_response(response)
        >>> "SG123" in analyses
        True
    """
    try:
        # Extract JSON from response (handle markdown code blocks)
        json_text = response_text.strip()

        # Remove markdown code block markers if present
        if json_text.startswith("```json"):
            json_text = json_text.replace("```json", "").replace("```", "").strip()
        elif json_text.startswith("```"):
            json_text = json_text.replace("```", "").strip()

        data = json.loads(json_text)

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON response from Gemini: {e}")

    analyses = {}

    for hand_id, analysis_dict in data.items():
        # Validate required fields
        required_fields = [
            "error_type", "root_cause", "affected_phase",
            "confidence", "suggested_fix", "auto_fixable"
        ]

        for field in required_fields:
            if field not in analysis_dict:
                raise KeyError(f"Missing required field '{field}' for hand {hand_id}")

        # Create ErrorAnalysis object
        analysis = ErrorAnalysis(
            error_type=analysis_dict["error_type"],
            root_cause=analysis_dict["root_cause"],
            affected_phase=analysis_dict["affected_phase"],
            confidence=float(analysis_dict["confidence"]),
            suggested_fix=analysis_dict["suggested_fix"],
            auto_fixable=bool(analysis_dict["auto_fixable"]),
            fix_code=analysis_dict.get("fix_code")
        )

        analyses[hand_id] = analysis

    return analyses


async def analyze_errors_with_gemini(
    job_id: int,
    errors: Dict[str, List[PTError]],
    db_connection
) -> Dict[str, ErrorAnalysis]:
    """Use Gemini AI to analyze PT4 errors with full job context

    Loads all relevant job data (parsed hands, OCR results, mappings) and
    sends to Gemini for analysis. Returns structured ErrorAnalysis objects
    with root cause, affected phase, confidence, and suggested fixes.

    Args:
        job_id: Job ID to analyze
        errors: Dictionary mapping filename → list of PTError objects
        db_connection: Database connection for loading job context

    Returns:
        Dictionary mapping hand_id → ErrorAnalysis object

    Raises:
        Exception: If Gemini API call fails

    Example:
        >>> errors = {"file1.txt": [PTError(...)]}
        >>> analyses = await analyze_errors_with_gemini(1, errors, db)
        >>> analyses["SG123"].confidence
        0.95
    """
    # Load job context from database
    job_data = db_connection.get_job(job_id)
    parsed_hands = db_connection.get_parsed_hands(job_id)
    ocr_results = db_connection.get_ocr_results(job_id)
    current_mappings = db_connection.get_mappings(job_id)

    # Build comprehensive prompt
    prompt = build_analysis_prompt(
        errors=errors,
        parsed_hands=parsed_hands,
        ocr_results=ocr_results,
        current_mappings=current_mappings
    )

    # Configure Gemini API
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    genai.configure(api_key=api_key)

    # Call Gemini API
    model = genai.GenerativeModel('gemini-2.5-flash')

    try:
        response = await model.generate_content_async(prompt)
        response_text = response.text

    except Exception as e:
        raise Exception(f"Gemini API error: {e}")

    # Parse response into ErrorAnalysis objects
    analyses = parse_gemini_response(response_text)

    return analyses


def get_analysis_statistics(analyses: Dict[str, ErrorAnalysis]) -> Dict[str, Any]:
    """Calculate statistics about error analyses

    Args:
        analyses: Dictionary of hand_id → ErrorAnalysis

    Returns:
        Dictionary with analysis statistics

    Example:
        >>> stats = get_analysis_statistics(analyses)
        >>> stats["high_confidence_count"]
        4
    """
    if not analyses:
        return {
            "total_analyses": 0,
            "avg_confidence": 0.0,
            "high_confidence_count": 0,
            "medium_confidence_count": 0,
            "low_confidence_count": 0,
            "auto_fixable_count": 0,
            "by_phase": {},
            "by_error_type": {}
        }

    confidences = [a.confidence for a in analyses.values()]
    avg_confidence = sum(confidences) / len(confidences)

    high_confidence = sum(1 for a in analyses.values() if a.confidence > 0.8)
    medium_confidence = sum(1 for a in analyses.values() if 0.5 <= a.confidence <= 0.8)
    low_confidence = sum(1 for a in analyses.values() if a.confidence < 0.5)

    auto_fixable = sum(1 for a in analyses.values() if a.auto_fixable)

    # Group by phase
    by_phase = {}
    for analysis in analyses.values():
        phase = analysis.affected_phase
        if phase not in by_phase:
            by_phase[phase] = 0
        by_phase[phase] += 1

    # Group by error type
    by_error_type = {}
    for analysis in analyses.values():
        error_type = analysis.error_type
        if error_type not in by_error_type:
            by_error_type[error_type] = 0
        by_error_type[error_type] += 1

    return {
        "total_analyses": len(analyses),
        "avg_confidence": avg_confidence,
        "high_confidence_count": high_confidence,
        "medium_confidence_count": medium_confidence,
        "low_confidence_count": low_confidence,
        "auto_fixable_count": auto_fixable,
        "by_phase": by_phase,
        "by_error_type": by_error_type
    }


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def main():
        # Mock database
        class MockDB:
            def get_job(self, job_id):
                return {"id": job_id, "status": "completed"}

            def get_parsed_hands(self, job_id):
                return [{"hand_id": "SG123", "players": {1: "abc123", 2: "def456"}}]

            def get_ocr_results(self, job_id):
                return [{"screenshot_id": "s1.png", "players": ["Alice", "Bob"]}]

            def get_mappings(self, job_id):
                return {"SG123": {"abc123": "Alice", "def456": "Alice"}}

        errors = {
            "file1.txt": [
                PTError(
                    hand_id="SG123",
                    error_type="duplicate_player",
                    line_number=5,
                    raw_message="Error: Duplicate player...",
                    player_name="Alice",
                    seats_involved=[1, 2]
                )
            ]
        }

        db = MockDB()
        analyses = await analyze_errors_with_gemini(1, errors, db)

        print(f"Analyzed {len(analyses)} errors:")
        for hand_id, analysis in analyses.items():
            print(f"  {hand_id}: {analysis.affected_phase} (confidence: {analysis.confidence:.2f})")

    # Run example
    # asyncio.run(main())
    print("error_analyzer.py loaded successfully")
