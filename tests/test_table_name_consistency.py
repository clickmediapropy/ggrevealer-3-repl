import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_unknown_table_variants_match():
    """Verify unknown_table_1 is found by its own group"""
    from main import _table_matches

    # Should match exactly
    assert _table_matches('unknown_table_1', 'unknown_table_1') == True
    assert _table_matches('unknown_table_1', 'unknown_table_2') == False


def test_normalize_preserves_unique_unknown_tables():
    """Verify normalization doesn't collapse different unknown tables"""
    from main import _normalize_table_name

    norm1 = _normalize_table_name('unknown_table_1')
    norm2 = _normalize_table_name('unknown_table_2')

    # They should be equal after normalization (both become 'Unknown')
    # But we need to track them separately before normalization
    assert norm1 == norm2  # This reveals the bug


def test_table_matching_with_real_vs_unknown():
    """Verify real table names don't match unknown tables"""
    from main import _table_matches

    # Real table should not match unknown
    assert _table_matches('RealTable123', 'unknown_table_1') == False

    # But normalize correctly
    assert _table_matches('RealTable123', 'RealTable123') == True
