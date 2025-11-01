"""
Error Parser Module for PT4 Error Recovery System

Parses unstructured PokerTracker error logs into structured PTError objects.
Supports multiple error types: duplicate_player, invalid_pot, unmapped_id, etc.

Author: Claude Code
Date: 2025-11-01
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Callable


@dataclass
class PTError:
    """Structured representation of a PokerTracker error

    Attributes:
        hand_id: Hand ID from error (e.g., "SG3247401164")
        error_type: Type of error (duplicate_player, invalid_pot, etc.)
        line_number: Line number in hand history file where error occurred
        raw_message: Original error message from PT4
        player_name: Player name involved (for duplicate_player errors)
        seats_involved: List of seat numbers (for duplicate_player errors)
        expected_pot: Expected pot amount (for invalid_pot errors)
        found_pot: Actual pot amount found (for invalid_pot errors)
        unmapped_id: Unmapped anonymized ID (for unmapped_id errors)
        filename: Source filename (for unmapped_id errors)
    """
    hand_id: str
    error_type: str
    line_number: int
    raw_message: str

    # Optional fields for specific error types
    player_name: Optional[str] = None
    seats_involved: Optional[List[int]] = None
    expected_pot: Optional[float] = None
    found_pot: Optional[float] = None
    unmapped_id: Optional[str] = None
    filename: Optional[str] = None


# Type alias for extraction functions
ExtractFunc = Callable[[re.Match], Dict[str, any]]


# Error pattern configurations
ERROR_PATTERNS: Dict[str, Dict[str, any]] = {
    "duplicate_player": {
        "pattern": r"Duplicate player:\s+(\w+)\s+\(seat\s+(\d+)\).*?seat\s+(\d+).*?Hand\s+#(\w+).*?Line\s+#(\d+)",
        "extract": lambda m: {
            "player_name": m.group(1),
            "seats_involved": [int(m.group(2)), int(m.group(3))],
            "hand_id": m.group(4),
            "line_number": int(m.group(5))
        }
    },
    "invalid_pot": {
        "pattern": r"Invalid pot.*?Expected\s+\$([0-9.]+).*?found\s+\$([0-9.]+).*?Hand\s+#(\w+).*?Line\s+#(\d+)",
        "extract": lambda m: {
            "expected_pot": float(m.group(1)),
            "found_pot": float(m.group(2)),
            "hand_id": m.group(3),
            "line_number": int(m.group(4))
        }
    },
    "unmapped_id": {
        "pattern": r"Unmapped ID:\s+([a-f0-9]{6,8}).*?file\s+([\w_]+\.txt).*?Line\s+#(\d+)",
        "extract": lambda m: {
            "unmapped_id": m.group(1),
            "filename": m.group(2),
            "line_number": int(m.group(3)),
            "hand_id": "UNKNOWN"  # Unmapped ID errors don't always have hand ID
        }
    }
}


def parse_error_log(text: str) -> List[PTError]:
    """Parse PT4 error log text into structured PTError objects

    Supports multiple error types:
    - duplicate_player: Player appears in multiple seats in same hand
    - invalid_pot: Pot calculation mismatch
    - unmapped_id: Anonymized ID not mapped to real player name

    Args:
        text: Raw error log text from PokerTracker

    Returns:
        List of PTError objects, one per error found

    Example:
        >>> log = "Error: GG Poker: Duplicate player: Alice (seat 1) the same as in seat 2 (Hand #SG123) (Line #5)"
        >>> errors = parse_error_log(log)
        >>> errors[0].player_name
        'Alice'
    """
    errors = []

    for line in text.split('\n'):
        line = line.strip()

        # Skip empty lines and lines without "Error:" keyword
        if not line or "Error:" not in line:
            continue

        # Try to match each error type pattern
        for error_type, config in ERROR_PATTERNS.items():
            match = re.search(config["pattern"], line, re.IGNORECASE)
            if match:
                try:
                    # Extract fields using the error type's extraction function
                    extracted = config["extract"](match)

                    # Create PTError object
                    error = PTError(
                        error_type=error_type,
                        raw_message=line,
                        **extracted
                    )
                    errors.append(error)
                    break  # Stop trying patterns after first match

                except (ValueError, IndexError) as e:
                    # Log parsing error but continue processing
                    print(f"Warning: Failed to parse error line: {line}")
                    print(f"  Exception: {e}")
                    continue

    return errors


def map_errors_to_files(
    job_id: int,
    errors: List[PTError],
    db_connection=None
) -> Dict[str, List[PTError]]:
    """Map errors to their source TXT files by searching for hand IDs

    Uses hand_id as an "anchor" to find which output file contains each error.
    For unmapped_id errors, uses the filename field directly.

    Args:
        job_id: Job ID to search within
        errors: List of PTError objects to map
        db_connection: Database connection (optional, for testing can be None)

    Returns:
        Dictionary mapping filename → list of PTError objects

    Example:
        >>> errors = [PTError(hand_id="SG123", ...), PTError(hand_id="SG124", ...)]
        >>> file_mapping = map_errors_to_files(job_id=1, errors=errors, db=db)
        >>> file_mapping
        {"table_12253_resolved.txt": [error1, error2]}
    """
    file_mapping: Dict[str, List[PTError]] = {}

    # If no database connection provided, create stub mapping by filename
    if db_connection is None:
        for error in errors:
            if error.filename:
                # Use filename from error (for unmapped_id errors)
                if error.filename not in file_mapping:
                    file_mapping[error.filename] = []
                file_mapping[error.filename].append(error)
            else:
                # Group by hand ID prefix for now (stub implementation)
                stub_filename = f"hand_{error.hand_id}_file.txt"
                if stub_filename not in file_mapping:
                    file_mapping[stub_filename] = []
                file_mapping[stub_filename].append(error)

        return file_mapping

    # TODO: Implement actual database lookup
    # For each error:
    #   1. Query database for hand_id
    #   2. Find which output file contains that hand
    #   3. Add error to that file's list

    # Stub implementation for now
    return file_mapping


def group_errors_by_type(errors: List[PTError]) -> Dict[str, List[PTError]]:
    """Group errors by their error_type

    Useful for statistics and reporting.

    Args:
        errors: List of PTError objects

    Returns:
        Dictionary mapping error_type → list of PTError objects
    """
    grouped: Dict[str, List[PTError]] = {}

    for error in errors:
        if error.error_type not in grouped:
            grouped[error.error_type] = []
        grouped[error.error_type].append(error)

    return grouped


def get_error_statistics(errors: List[PTError]) -> Dict[str, any]:
    """Calculate statistics about parsed errors

    Args:
        errors: List of PTError objects

    Returns:
        Dictionary with error statistics
    """
    if not errors:
        return {
            "total_errors": 0,
            "by_type": {},
            "unique_hands": 0,
            "unique_files": 0
        }

    by_type = group_errors_by_type(errors)
    unique_hands = len(set(e.hand_id for e in errors if e.hand_id != "UNKNOWN"))
    unique_files = len(set(e.filename for e in errors if e.filename))

    return {
        "total_errors": len(errors),
        "by_type": {k: len(v) for k, v in by_type.items()},
        "unique_hands": unique_hands,
        "unique_files": unique_files
    }


if __name__ == "__main__":
    # Example usage
    sample_log = """
Error: GG Poker: Duplicate player: TuichAAreko (seat 3) the same as in seat 2 (Hand #SG3247401164) (Line #46)
Error: GG Poker: Invalid pot size: Expected $45.50, found $44.00 (Hand #RC3247401165) (Line #12)
Error: GG Poker: Unmapped ID: a4c8f2 in file 43746_resolved.txt (Line #25)
    """

    errors = parse_error_log(sample_log)

    print(f"Parsed {len(errors)} errors:")
    for error in errors:
        print(f"  - {error.error_type}: {error.hand_id}")

    stats = get_error_statistics(errors)
    print(f"\nStatistics: {stats}")
