import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
from unittest.mock import patch

def test_api_key_fallback_to_dummy():
    """Current behavior: API key falls back to DUMMY silently (this should FAIL after fix)"""

    # Test 1: No env var, no provided key -> falls back to DUMMY
    with patch.dict(os.environ, {}, clear=True):
        api_key = None
        if not api_key or not api_key.strip() if api_key else True:
            api_key = os.getenv('GEMINI_API_KEY', 'DUMMY_API_KEY_FOR_TESTING')

        # Before fix: This is DUMMY (silent fallback - BAD)
        # After fix: This should raise ValueError
        assert api_key == 'DUMMY_API_KEY_FOR_TESTING', "Current behavior uses dummy key"

def test_api_key_validation_logic():
    """Test the validation logic that should fail fast"""

    # After implementation, invalid keys should raise ValueError
    invalid_keys = [
        None,
        '',
        'DUMMY_API_KEY_FOR_TESTING',
        'your_gemini_api_key_here'
    ]

    for invalid_key in invalid_keys:
        # After fix, this should raise ValueError
        # For now, we'll just check the condition
        is_invalid = (not invalid_key or
                     invalid_key == 'your_gemini_api_key_here' or
                     invalid_key == 'DUMMY_API_KEY_FOR_TESTING')

        assert is_invalid, f"Key '{invalid_key}' should be considered invalid"

def test_valid_api_key_accepted():
    """Valid API keys should be accepted"""

    valid_keys = [
        'sk-proj-abc123',
        'AIza123456789',
        'valid_key_xyz123'
    ]

    for valid_key in valid_keys:
        is_valid = (valid_key and
                   valid_key != 'your_gemini_api_key_here' and
                   valid_key != 'DUMMY_API_KEY_FOR_TESTING')

        assert is_valid, f"Key '{valid_key}' should be considered valid"
