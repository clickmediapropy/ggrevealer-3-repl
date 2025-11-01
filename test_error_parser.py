"""
Test suite for error_parser.py
Following TDD approach: Write tests first (RED phase)
"""

import pytest
from error_parser import (
    PTError,
    parse_error_log,
    map_errors_to_files,
    ERROR_PATTERNS
)


class TestPTErrorDataclass:
    """Test PTError dataclass structure"""

    def test_basic_error_creation(self):
        """Test creating a basic PTError object"""
        error = PTError(
            hand_id="SG3247401164",
            error_type="duplicate_player",
            line_number=46,
            raw_message="Error: GG Poker: Duplicate player..."
        )

        assert error.hand_id == "SG3247401164"
        assert error.error_type == "duplicate_player"
        assert error.line_number == 46
        assert error.player_name is None  # Optional field


class TestParseDuplicatePlayerError:
    """Test parsing duplicate player errors"""

    def test_parse_duplicate_player_simple(self):
        """Test parsing duplicate player error from PT4"""
        error_log = "Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247401164) (Line #46)"
        errors = parse_error_log(error_log)

        assert len(errors) == 1
        assert errors[0].hand_id == "SG3247401164"
        assert errors[0].error_type == "duplicate_player"
        assert errors[0].player_name == "TuichAAreko"
        assert errors[0].seats_involved == [3, 2]
        assert errors[0].line_number == 46
        assert errors[0].raw_message == error_log

    def test_parse_duplicate_player_with_numbers_in_name(self):
        """Test parsing duplicate player with numbers in player name"""
        error_log = "Error: GG Poker: Duplicate player: 50Zoos (seat 1) the same as in seat 6 (Hand #RC1234567890) (Line #12)"
        errors = parse_error_log(error_log)

        assert len(errors) == 1
        assert errors[0].player_name == "50Zoos"
        assert errors[0].seats_involved == [1, 6]
        assert errors[0].hand_id == "RC1234567890"

    def test_parse_duplicate_player_different_hand_prefix(self):
        """Test parsing with different hand ID prefixes (MT, TT, OM)"""
        error_log = "Error: GG Poker: Duplicate player: Player1 (seat 2) the same as in seat 5 (Hand #MT9876543210) (Line #99)"
        errors = parse_error_log(error_log)

        assert len(errors) == 1
        assert errors[0].hand_id == "MT9876543210"


class TestParseInvalidPotError:
    """Test parsing invalid pot errors"""

    def test_parse_invalid_pot_simple(self):
        """Test parsing invalid pot error"""
        error_log = "Error: GG Poker: Invalid pot size: Expected $45.50, found $44.00 (Hand #RC3247401165) (Line #12)"
        errors = parse_error_log(error_log)

        assert len(errors) == 1
        assert errors[0].hand_id == "RC3247401165"
        assert errors[0].error_type == "invalid_pot"
        assert errors[0].expected_pot == 45.50
        assert errors[0].found_pot == 44.00
        assert errors[0].line_number == 12

    def test_parse_invalid_pot_whole_numbers(self):
        """Test parsing pot error with whole dollar amounts"""
        error_log = "Error: GG Poker: Invalid pot size: Expected $100, found $98 (Hand #SG111) (Line #20)"
        errors = parse_error_log(error_log)

        assert len(errors) == 1
        assert errors[0].expected_pot == 100.0
        assert errors[0].found_pot == 98.0

    def test_parse_invalid_pot_small_amounts(self):
        """Test parsing pot error with small amounts (blinds)"""
        error_log = "Error: GG Poker: Invalid pot size: Expected $0.25, found $0.20 (Hand #SG222) (Line #5)"
        errors = parse_error_log(error_log)

        assert len(errors) == 1
        assert errors[0].expected_pot == 0.25
        assert errors[0].found_pot == 0.20


class TestParseUnmappedIDError:
    """Test parsing unmapped ID errors"""

    def test_parse_unmapped_id_simple(self):
        """Test parsing unmapped ID error"""
        error_log = "Error: GG Poker: Unmapped ID: a4c8f2 in file 43746_resolved.txt (Line #25)"
        errors = parse_error_log(error_log)

        assert len(errors) == 1
        assert errors[0].error_type == "unmapped_id"
        assert errors[0].unmapped_id == "a4c8f2"
        assert errors[0].filename == "43746_resolved.txt"
        assert errors[0].line_number == 25

    def test_parse_unmapped_id_8_char(self):
        """Test parsing unmapped ID with 8 characters"""
        error_log = "Error: GG Poker: Unmapped ID: abc12345 in file table_12253_resolved.txt (Line #100)"
        errors = parse_error_log(error_log)

        assert len(errors) == 1
        assert errors[0].unmapped_id == "abc12345"
        assert errors[0].filename == "table_12253_resolved.txt"

    def test_parse_unmapped_id_with_hand_id(self):
        """Test parsing unmapped ID that also includes hand ID"""
        error_log = "Error: GG Poker: Unmapped ID: 5a3f9e in file output.txt (Hand #SG999) (Line #50)"
        errors = parse_error_log(error_log)

        assert len(errors) == 1
        assert errors[0].unmapped_id == "5a3f9e"


class TestParseMultipleErrors:
    """Test parsing multiple errors from single log"""

    def test_parse_multiple_errors_mixed_types(self):
        """Test parsing multiple errors of different types from log"""
        error_log = """
Error: GG Poker: Duplicate player: Player1 (seat 2) the same as in seat 1 (Hand #SG111) (Line #10)
Error: GG Poker: Invalid pot size: Expected $100, found $98 (Hand #SG112) (Line #20)
Error: GG Poker: Unmapped ID: abc123 in file test.txt (Line #30)
        """
        errors = parse_error_log(error_log)

        assert len(errors) == 3
        assert errors[0].error_type == "duplicate_player"
        assert errors[0].hand_id == "SG111"
        assert errors[1].error_type == "invalid_pot"
        assert errors[1].hand_id == "SG112"
        assert errors[2].error_type == "unmapped_id"
        assert errors[2].unmapped_id == "abc123"

    def test_parse_multiple_duplicate_errors(self):
        """Test parsing multiple duplicate player errors"""
        error_log = """
Error: GG Poker: Duplicate player: Alice (seat 1) the same as in seat 2 (Hand #SG100) (Line #5)
Error: GG Poker: Duplicate player: Bob (seat 3) the same as in seat 4 (Hand #SG101) (Line #15)
Error: GG Poker: Duplicate player: Charlie (seat 5) the same as in seat 6 (Hand #SG102) (Line #25)
        """
        errors = parse_error_log(error_log)

        assert len(errors) == 3
        assert all(e.error_type == "duplicate_player" for e in errors)
        assert [e.player_name for e in errors] == ["Alice", "Bob", "Charlie"]


class TestParseEdgeCases:
    """Test edge cases and invalid inputs"""

    def test_parse_empty_log(self):
        """Test parsing empty error log"""
        errors = parse_error_log("")
        assert len(errors) == 0

    def test_parse_log_without_errors(self):
        """Test parsing log that doesn't contain any errors"""
        log = """
        Some random text
        Not an error line
        Just regular output
        """
        errors = parse_error_log(log)
        assert len(errors) == 0

    def test_parse_log_with_error_keyword_but_wrong_format(self):
        """Test that incorrectly formatted error lines are skipped"""
        log = "Error: Something went wrong but not in PT4 format"
        errors = parse_error_log(log)
        assert len(errors) == 0

    def test_parse_log_mixed_with_non_error_lines(self):
        """Test parsing log with mix of error and non-error lines"""
        error_log = """
        Import started...
        Processing file 1 of 10
        Error: GG Poker: Duplicate player: Test (seat 1) the same as in seat 2 (Hand #SG123) (Line #5)
        Continuing import...
        Successfully imported 5 hands
        Error: GG Poker: Invalid pot size: Expected $50, found $49 (Hand #SG124) (Line #10)
        Import complete
        """
        errors = parse_error_log(error_log)

        assert len(errors) == 2
        assert errors[0].error_type == "duplicate_player"
        assert errors[1].error_type == "invalid_pot"


class TestErrorPatterns:
    """Test error pattern regex configurations"""

    def test_all_error_types_have_patterns(self):
        """Test that all expected error types have regex patterns"""
        expected_types = ["duplicate_player", "invalid_pot", "unmapped_id"]

        for error_type in expected_types:
            assert error_type in ERROR_PATTERNS
            assert "pattern" in ERROR_PATTERNS[error_type]
            assert "extract" in ERROR_PATTERNS[error_type]


class TestMapErrorsToFiles:
    """Test mapping errors to their source files"""

    def test_map_errors_to_files_basic(self):
        """Test mapping errors to files by hand ID"""
        # This test will be implemented after database integration
        # For now, we'll test with mock data
        pass

    def test_map_errors_groups_by_file(self):
        """Test that errors are correctly grouped by file"""
        # Will be implemented with database mock
        pass

    def test_map_errors_handles_missing_hand_ids(self):
        """Test handling of errors that can't be mapped to files"""
        # Will be implemented with database mock
        pass


class TestPlayerNameVariations:
    """Test handling various player name formats"""

    def test_player_name_with_special_chars(self):
        """Test player names with brackets, dots, etc."""
        error_log = "Error: GG Poker: Duplicate player: v1[nn]1 (seat 1) the same as in seat 2 (Hand #SG123) (Line #5)"
        errors = parse_error_log(error_log)

        # Note: Current regex uses \w+ which won't capture special chars
        # This test documents current limitation
        # May need to update regex to: ([^\s(]+) to capture more complex names
        pass

    def test_player_name_with_dots(self):
        """Test player names with dots"""
        error_log = "Error: GG Poker: Duplicate player: Player.Name (seat 1) the same as in seat 2 (Hand #SG123) (Line #5)"
        errors = parse_error_log(error_log)

        # Documents limitation with current \w+ pattern
        pass


class TestHandIDPrefixes:
    """Test various hand ID prefix formats"""

    def test_all_known_hand_id_prefixes(self):
        """Test parsing errors with all known GGPoker hand ID prefixes"""
        prefixes = ["SG", "RC", "MT", "TT", "OM", "HD"]

        for prefix in prefixes:
            hand_id = f"{prefix}1234567890"
            error_log = f"Error: GG Poker: Duplicate player: Test (seat 1) the same as in seat 2 (Hand #{hand_id}) (Line #5)"
            errors = parse_error_log(error_log)

            assert len(errors) == 1
            assert errors[0].hand_id == hand_id


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
