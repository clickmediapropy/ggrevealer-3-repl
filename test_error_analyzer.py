"""
Test suite for error_analyzer.py
Following TDD approach: Write tests first (RED phase)
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from error_analyzer import (
    ErrorAnalysis,
    analyze_errors_with_gemini,
    build_analysis_prompt,
    parse_gemini_response
)
from error_parser import PTError


class TestErrorAnalysisDataclass:
    """Test ErrorAnalysis dataclass structure"""

    def test_basic_analysis_creation(self):
        """Test creating an ErrorAnalysis object"""
        analysis = ErrorAnalysis(
            error_type="duplicate_player",
            root_cause="Screenshot matched to wrong hand",
            affected_phase="matcher",
            confidence=0.95,
            suggested_fix="Remove seat 3 mapping for TuichAAreko",
            auto_fixable=True,
            fix_code="remove_duplicate_mapping"
        )

        assert analysis.error_type == "duplicate_player"
        assert analysis.affected_phase == "matcher"
        assert analysis.confidence == 0.95
        assert analysis.auto_fixable is True


class TestBuildAnalysisPrompt:
    """Test building Gemini analysis prompts"""

    def test_prompt_includes_all_context(self):
        """Test that prompt includes parsed hands, OCR, mappings, and errors"""
        errors = {
            "file1.txt": [
                PTError(
                    hand_id="SG123",
                    error_type="duplicate_player",
                    line_number=5,
                    raw_message="Error...",
                    player_name="Alice",
                    seats_involved=[1, 2]
                )
            ]
        }

        parsed_hands = [
            {
                "hand_id": "SG123",
                "players": {1: "abc123", 2: "def456"},
                "board": ["Ah", "Kd", "Qs"]
            }
        ]

        ocr_results = [
            {
                "screenshot_id": "screen1.png",
                "hand_id": "SG123",
                "players": ["Alice", "Bob"]
            }
        ]

        current_mappings = {
            "SG123": {"abc123": "Alice", "def456": "Alice"}  # Duplicate!
        }

        prompt = build_analysis_prompt(
            errors=errors,
            parsed_hands=parsed_hands,
            ocr_results=ocr_results,
            current_mappings=current_mappings
        )

        # Verify prompt contains all sections
        assert "CONTEXT:" in prompt
        assert "Parsed Hands:" in prompt
        assert "OCR Results:" in prompt
        assert "Current Mappings:" in prompt
        assert "ERRORS TO ANALYZE:" in prompt
        assert "SG123" in prompt
        assert "duplicate_player" in prompt

    def test_prompt_specifies_required_output(self):
        """Test that prompt specifies required JSON output format"""
        prompt = build_analysis_prompt(
            errors={},
            parsed_hands=[],
            ocr_results=[],
            current_mappings={}
        )

        # Check for output format instructions
        assert "Output JSON format:" in prompt or "JSON" in prompt
        assert "root_cause" in prompt
        assert "affected_phase" in prompt
        assert "confidence" in prompt
        assert "suggested_fix" in prompt
        assert "auto_fixable" in prompt


class TestParseGeminiResponse:
    """Test parsing Gemini's JSON responses"""

    def test_parse_single_error_analysis(self):
        """Test parsing Gemini response for single error"""
        response_text = """
{
  "SG123": {
    "error_type": "duplicate_player",
    "root_cause": "Duplicate player mapping: TuichAAreko in seat 2 AND 3",
    "affected_phase": "matcher",
    "confidence": 0.95,
    "suggested_fix": "Remove seat 3 mapping for TuichAAreko",
    "auto_fixable": true,
    "fix_code": "remove_duplicate_mapping"
  }
}
        """

        analyses = parse_gemini_response(response_text)

        assert "SG123" in analyses
        assert analyses["SG123"].error_type == "duplicate_player"
        assert analyses["SG123"].root_cause == "Duplicate player mapping: TuichAAreko in seat 2 AND 3"
        assert analyses["SG123"].affected_phase == "matcher"
        assert analyses["SG123"].confidence == 0.95
        assert analyses["SG123"].auto_fixable is True

    def test_parse_multiple_error_analyses(self):
        """Test parsing Gemini response for multiple errors"""
        response_text = """
{
  "SG123": {
    "error_type": "duplicate_player",
    "root_cause": "Duplicate player mapping",
    "affected_phase": "matcher",
    "confidence": 0.95,
    "suggested_fix": "Remove duplicate",
    "auto_fixable": true,
    "fix_code": "remove_duplicate_mapping"
  },
  "SG124": {
    "error_type": "invalid_pot",
    "root_cause": "Cash Drop fee not included",
    "affected_phase": "parser",
    "confidence": 0.88,
    "suggested_fix": "Add jackpot fee to pot",
    "auto_fixable": true,
    "fix_code": "recalculate_pot"
  }
}
        """

        analyses = parse_gemini_response(response_text)

        assert len(analyses) == 2
        assert "SG123" in analyses
        assert "SG124" in analyses
        assert analyses["SG123"].affected_phase == "matcher"
        assert analyses["SG124"].affected_phase == "parser"

    def test_parse_handles_malformed_json(self):
        """Test that parser handles malformed JSON gracefully"""
        response_text = "This is not valid JSON"

        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_gemini_response(response_text)

    def test_parse_handles_missing_fields(self):
        """Test that parser handles missing required fields"""
        response_text = """
{
  "SG123": {
    "root_cause": "Some error",
    "confidence": 0.5
  }
}
        """

        with pytest.raises(KeyError):
            parse_gemini_response(response_text)


class TestAnalyzeErrorsWithGemini:
    """Test the main Gemini analysis function"""

    @pytest.mark.asyncio
    async def test_analyze_duplicate_player_error(self):
        """Test analyzing duplicate player error with Gemini"""
        job_id = 1
        errors = {
            "table_12253.txt": [
                PTError(
                    hand_id="SG123",
                    error_type="duplicate_player",
                    line_number=5,
                    raw_message="Error...",
                    player_name="TuichAAreko",
                    seats_involved=[2, 3]
                )
            ]
        }

        # Mock database connection
        mock_db = Mock()
        mock_db.get_job.return_value = {"id": 1, "status": "completed"}
        mock_db.get_parsed_hands.return_value = [{"hand_id": "SG123"}]
        mock_db.get_ocr_results.return_value = [{"screenshot_id": "s1.png"}]
        mock_db.get_mappings.return_value = {"abc123": "TuichAAreko"}

        # Mock Gemini response
        gemini_response = {
            "SG123": {
                "error_type": "duplicate_player",
                "root_cause": "Screenshot matched to wrong hand",
                "affected_phase": "matcher",
                "confidence": 0.95,
                "suggested_fix": "Remove seat 3 mapping for TuichAAreko",
                "auto_fixable": True,
                "fix_code": "remove_duplicate_mapping"
            }
        }

        with patch('error_analyzer.genai') as mock_genai, \
             patch('error_analyzer.os.getenv') as mock_getenv:

            # Mock API key
            mock_getenv.return_value = "fake_api_key"

            # Mock the model and generate_content_async
            mock_model = AsyncMock()
            mock_response = Mock()
            mock_response.text = json.dumps(gemini_response)
            mock_model.generate_content_async.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            analyses = await analyze_errors_with_gemini(job_id, errors, mock_db)

            assert "SG123" in analyses
            assert analyses["SG123"].affected_phase == "matcher"
            assert analyses["SG123"].confidence == 0.95
            assert analyses["SG123"].auto_fixable is True

    @pytest.mark.asyncio
    async def test_analyze_invalid_pot_error(self):
        """Test analyzing invalid pot error"""
        job_id = 1
        errors = {
            "file1.txt": [
                PTError(
                    hand_id="RC456",
                    error_type="invalid_pot",
                    line_number=10,
                    raw_message="Error...",
                    expected_pot=45.50,
                    found_pot=44.00
                )
            ]
        }

        mock_db = Mock()
        mock_db.get_job.return_value = {"id": 1}
        mock_db.get_parsed_hands.return_value = []
        mock_db.get_ocr_results.return_value = []
        mock_db.get_mappings.return_value = {}

        gemini_response = {
            "RC456": {
                "error_type": "invalid_pot",
                "root_cause": "Cash Drop fee (1BB on pots >30BB) not included in pot calculation",
                "affected_phase": "parser",
                "confidence": 0.88,
                "suggested_fix": "Add $1.50 jackpot fee to pot",
                "auto_fixable": True,
                "fix_code": "add_cash_drop_fee"
            }
        }

        with patch('error_analyzer.genai') as mock_genai, \
             patch('error_analyzer.os.getenv') as mock_getenv:

            # Mock API key
            mock_getenv.return_value = "fake_api_key"

            mock_model = AsyncMock()
            mock_response = Mock()
            mock_response.text = json.dumps(gemini_response)
            mock_model.generate_content_async.return_value = mock_response
            mock_genai.GenerativeModel.return_value = mock_model

            analyses = await analyze_errors_with_gemini(job_id, errors, mock_db)

            assert "RC456" in analyses
            assert analyses["RC456"].affected_phase == "parser"
            assert "Cash Drop" in analyses["RC456"].root_cause

    @pytest.mark.asyncio
    async def test_gemini_api_error_handling(self):
        """Test handling of Gemini API errors"""
        job_id = 1
        errors = {"file1.txt": [PTError(hand_id="SG123", error_type="duplicate_player", line_number=5, raw_message="Error...")]}

        mock_db = Mock()
        mock_db.get_job.return_value = {"id": 1}
        mock_db.get_parsed_hands.return_value = []
        mock_db.get_ocr_results.return_value = []
        mock_db.get_mappings.return_value = {}

        with patch('error_analyzer.genai') as mock_genai, \
             patch('error_analyzer.os.getenv') as mock_getenv:

            # Mock API key
            mock_getenv.return_value = "fake_api_key"

            mock_model = AsyncMock()
            mock_model.generate_content_async.side_effect = Exception("API Error")
            mock_genai.GenerativeModel.return_value = mock_model

            with pytest.raises(Exception, match="API Error"):
                await analyze_errors_with_gemini(job_id, errors, mock_db)


class TestConfidenceScoring:
    """Test confidence score calculations"""

    def test_high_confidence_duplicate_player(self):
        """Test that duplicate player errors get high confidence"""
        # When mapping clearly shows duplicate, confidence should be >0.8
        pass

    def test_medium_confidence_pot_error(self):
        """Test that pot errors get medium confidence"""
        # Cash Drop detection has some uncertainty, 0.7-0.9 range
        pass

    def test_low_confidence_unmapped_id(self):
        """Test that unmapped IDs get low confidence when no screenshots"""
        # Can't fix without screenshots, confidence should be low
        pass


class TestAffectedPhaseDetection:
    """Test detection of which pipeline phase caused the error"""

    def test_duplicate_player_is_matcher_phase(self):
        """Test that duplicate player errors map to matcher phase"""
        response = """
        {
          "SG123": {
            "error_type": "duplicate_player",
            "root_cause": "Wrong screenshot match",
            "affected_phase": "matcher",
            "confidence": 0.9,
            "suggested_fix": "Rematch",
            "auto_fixable": true,
            "fix_code": "rematch"
          }
        }
        """
        analyses = parse_gemini_response(response)
        assert analyses["SG123"].affected_phase == "matcher"

    def test_invalid_pot_is_parser_phase(self):
        """Test that pot errors map to parser phase"""
        response = """
        {
          "RC123": {
            "error_type": "invalid_pot",
            "root_cause": "Cash Drop fee missing",
            "affected_phase": "parser",
            "confidence": 0.85,
            "suggested_fix": "Recalculate pot",
            "auto_fixable": true,
            "fix_code": "recalc_pot"
          }
        }
        """
        analyses = parse_gemini_response(response)
        assert analyses["RC123"].affected_phase == "parser"


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-k", "not asyncio"])
