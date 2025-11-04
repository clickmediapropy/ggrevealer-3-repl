import pytest
from pt4_parser import parse_pt4_import_log, PT4ParsedResult

def test_parse_pt4_log_with_errors():
    """Test parsing PT4 log with failed files"""
    log = """06:58:32 pm: Importing files from disk...
06:58:32 pm: Import file: /Users/nicodelgadob/Downloads/resolved_hands_35 (1)/46798_resolved.txt
06:58:32 pm: Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247438352) (Line #5)
06:58:32 pm: Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247438203) (Line #32)
06:58:32 pm:         + Complete (0 hands, 0 summaries, 2 errors, 0 duplicates)
06:58:32 pm: Import file: /Users/nicodelgadob/Downloads/resolved_hands_35 (1)/43746_resolved.txt
06:58:32 pm:         + Complete (9 hands, 0 summaries, 0 errors, 0 duplicates)
06:58:32 pm: Import complete. 9 hands in 2 files were imported. (2 errors, 0 duplicates)"""

    result = parse_pt4_import_log(log)

    assert result is not None
    assert result.total_files == 2
    assert result.total_hands_imported == 9
    assert result.total_errors == 2
    assert len(result.failed_files) == 1

    failed_file = result.failed_files[0]
    assert failed_file['filename'] == '46798_resolved.txt'
    assert failed_file['table_number'] == 46798
    assert failed_file['error_count'] == 2
    assert len(failed_file['errors']) == 2

def test_parse_pt4_log_no_errors():
    """Test parsing PT4 log with no errors"""
    log = """06:58:32 pm: Importing files from disk...
06:58:32 pm: Import file: /path/43746_resolved.txt
06:58:32 pm:         + Complete (9 hands, 0 summaries, 0 errors, 0 duplicates)
06:58:32 pm: Import complete. 9 hands in 1 file were imported. (0 errors, 0 duplicates)"""

    result = parse_pt4_import_log(log)

    assert result is not None
    assert result.total_files == 1
    assert result.total_errors == 0
    assert len(result.failed_files) == 0

def test_extract_table_number_from_filename():
    """Test extracting table number from filename"""
    from pt4_parser import extract_table_number

    assert extract_table_number("46798_resolved.txt") == 46798
    assert extract_table_number("12345_fallado.txt") == 12345
    assert extract_table_number("/path/to/54321_resolved.txt") == 54321
    assert extract_table_number("invalid.txt") is None
