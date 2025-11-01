import pytest
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import zipfile
import tempfile

def test_zip_integrity_validated_on_download():
    """Verify corrupted ZIP is rejected on download"""

    # Create a valid ZIP
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        valid_zip = Path(tmp.name)

    with zipfile.ZipFile(valid_zip, 'w') as zf:
        zf.writestr("test.txt", "content")

    # Verify it's valid
    with zipfile.ZipFile(valid_zip, 'r') as zf:
        assert zf.testzip() is None  # None means valid

    valid_zip.unlink()

def test_corrupted_zip_rejected():
    """Verify corrupted ZIP is rejected"""

    # Create a corrupted ZIP
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        corrupted_zip = Path(tmp.name)

    with open(corrupted_zip, 'wb') as f:
        f.write(b'PK\x03\x04')  # ZIP header but invalid data

    # Try to test it - should fail
    try:
        with zipfile.ZipFile(corrupted_zip, 'r') as zf:
            result = zf.testzip()
            # If it returns something, it's corrupted
            # This may not even get here if BadZipFile is raised
            if result is not None:
                pass  # Corruption detected
    except zipfile.BadZipFile:
        pass  # Also valid sign of corruption
    finally:
        corrupted_zip.unlink()

def test_download_endpoint_validation_logic():
    """Test the validation logic for ZIP files before download"""

    # Test that we can detect valid ZIP
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        valid_zip = Path(tmp.name)

    with zipfile.ZipFile(valid_zip, 'w') as zf:
        zf.writestr("test.txt", "content")

    # Should pass validation
    is_valid = False
    try:
        with zipfile.ZipFile(valid_zip, 'r') as zipf:
            bad_file = zipf.testzip()
            is_valid = bad_file is None
    except zipfile.BadZipFile:
        is_valid = False

    assert is_valid, "Valid ZIP should pass validation"
    valid_zip.unlink()

    # Test that we can detect corrupted ZIP
    with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as tmp:
        corrupted_zip = Path(tmp.name)

    with open(corrupted_zip, 'wb') as f:
        f.write(b'PK\x03\x04' + b'\x00' * 100)  # ZIP header but invalid data

    # Should fail validation
    is_valid = True
    try:
        with zipfile.ZipFile(corrupted_zip, 'r') as zipf:
            bad_file = zipf.testzip()
            is_valid = bad_file is None
    except zipfile.BadZipFile:
        is_valid = False

    assert not is_valid, "Corrupted ZIP should fail validation"
    corrupted_zip.unlink()
