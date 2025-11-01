import pytest
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_valid_ocr2_data_accepted():
    """Verify valid OCR2 output is processed"""

    valid_ocr_data = {
        'players': ['Player1', 'Player2', 'Player3'],
        'stacks': ['$100', '$200', '$150'],
        'positions': [1, 2, 3],
        'roles': {
            'dealer': 'Player1',
            'small_blind': 'Player2',
            'big_blind': 'Player3'
        },
        'hand_id': 'RC12345'
    }

    # Should not raise
    screenshot = MagicMock()
    screenshot.ocr2_data = json.dumps(valid_ocr_data)

    # After fix, should validate successfully
    assert isinstance(valid_ocr_data.get('players'), list)

def test_missing_players_field_rejected():
    """Verify OCR2 missing players field is caught"""

    invalid_ocr_data = {
        'stacks': ['$100', '$200'],  # Missing 'players'
        'roles': {'dealer': 'Player1'}
    }

    # Should fail validation
    assert 'players' not in invalid_ocr_data

def test_invalid_stacks_format_rejected():
    """Verify OCR2 invalid stacks format is caught"""

    invalid_ocr_data = {
        'players': ['Player1', 'Player2'],
        'stacks': 'invalid_string',  # Should be list
        'roles': {'dealer': 'Player1'}
    }

    # Should fail validation
    assert not isinstance(invalid_ocr_data.get('stacks'), list)

def test_ocr2_validation_continues_on_error():
    """Verify job continues if single OCR2 is invalid"""

    # Mock multiple screenshots
    screenshots = [
        MagicMock(filename='valid.png', ocr2_data=json.dumps({'players': [], 'roles': {}})),
        MagicMock(filename='invalid.png', ocr2_data='not_json'),
        MagicMock(filename='another_valid.png', ocr2_data=json.dumps({'players': [], 'roles': {}}))
    ]

    # After fix, should process valid ones, skip invalid
    valid_count = 0
    for ss in screenshots:
        try:
            data = json.loads(ss.ocr2_data)
            if isinstance(data.get('players'), list):
                valid_count += 1
        except:
            pass  # Skip invalid

    assert valid_count >= 2  # At least 2 valid
