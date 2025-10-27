"""
TXT output writer with name replacement and validation
Ensures PokerTracker compatibility with 9 critical validations
"""

import re
from typing import List
from models import NameMapping, ValidationResult


def generate_final_txt(original_txt: str, mappings: List[NameMapping]) -> str:
    """
    Generate final TXT with resolved player names
    
    Args:
        original_txt: Original hand history text
        mappings: List of name mappings to apply
        
    Returns:
        Modified text with real names
    """
    output = original_txt
    
    # Apply mappings in specific order to avoid conflicts
    # Order matters: most specific patterns first
    
    for mapping in mappings:
        anon_id = mapping.anonymized_identifier
        real_name = mapping.resolved_name
        
        # CRITICAL: Never replace "Hero"
        if anon_id.lower() == 'hero':
            continue
        
        # Escape special regex characters
        anon_escaped = re.escape(anon_id)
        
        # 7 regex patterns for replacement (in order)
        
        # 1. Seat lines: "Seat 1: PlayerID ($100 in chips)"
        output = re.sub(
            rf'(Seat \d+: ){anon_escaped}( \(\$?[\d.]+)',
            rf'\1{real_name}\2',
            output
        )
        
        # 2. Action lines: "PlayerID: folds"
        output = re.sub(
            rf'^{anon_escaped}(: (?:folds|checks|calls|bets|raises))',
            rf'{real_name}\1',
            output,
            flags=re.MULTILINE
        )
        
        # 3. Dealt to (no cards): "Dealt to PlayerID"
        output = re.sub(
            rf'(Dealt to ){anon_escaped}(?![[\w])',
            rf'\1{real_name}',
            output
        )
        
        # 4. Dealt to (with cards): "Dealt to PlayerID [As Kh]"
        output = re.sub(
            rf'(Dealt to ){anon_escaped}( \[)',
            rf'\1{real_name}\2',
            output
        )
        
        # 5. Collected from pot: "PlayerID collected $100"
        output = re.sub(
            rf'^{anon_escaped}( collected)',
            rf'{real_name}\1',
            output,
            flags=re.MULTILINE
        )
        
        # 6. Shows cards: "PlayerID shows [As Kh]"
        output = re.sub(
            rf'^{anon_escaped}( shows \[)',
            rf'{real_name}\1',
            output,
            flags=re.MULTILINE
        )
        
        # 7. Summary lines: "Seat 1: PlayerID (button)"
        output = re.sub(
            rf'(Seat \d+: ){anon_escaped}(\s+\()',
            rf'\1{real_name}\2',
            output
        )
        
        # 8. Uncalled bet returned: "Uncalled bet ($10) returned to PlayerID"
        output = re.sub(
            rf'(returned to ){anon_escaped}$',
            rf'\1{real_name}',
            output,
            flags=re.MULTILINE
        )
    
    return output


def validate_output_format(original: str, modified: str) -> ValidationResult:
    """
    Validate output format for PokerTracker compatibility
    
    9 critical validations:
    1. Hero preservation
    2. Line count match
    3. Hand ID unchanged
    4. Timestamp unchanged
    5. No unexpected currency symbols
    6. Summary section preserved
    7. Table info unchanged
    8. Seat count match
    9. Chip format preserved
    """
    errors = []
    warnings = []
    
    # 1. Hero preservation - CRITICAL
    original_hero_count = original.count('Hero')
    modified_hero_count = modified.count('Hero')
    
    if original_hero_count != modified_hero_count:
        errors.append(
            f"Hero count mismatch: original={original_hero_count}, modified={modified_hero_count}. "
            "Hero MUST NEVER be replaced!"
        )
    
    # 2. Line count match
    original_lines = len(original.split('\n'))
    modified_lines = len(modified.split('\n'))
    
    if abs(original_lines - modified_lines) > 2:  # Allow 2 line variance
        warnings.append(
            f"Line count changed: {original_lines} -> {modified_lines}"
        )
    
    # 3. Hand ID unchanged
    original_hand_id = re.search(r'Poker Hand #(\S+):', original)
    modified_hand_id = re.search(r'Poker Hand #(\S+):', modified)
    
    if original_hand_id and modified_hand_id:
        if original_hand_id.group(1) != modified_hand_id.group(1):
            errors.append("Hand ID was modified!")
    
    # 4. Timestamp unchanged
    original_ts = re.search(r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}', original)
    modified_ts = re.search(r'\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}', modified)
    
    if original_ts and modified_ts:
        if original_ts.group(0) != modified_ts.group(0):
            errors.append("Timestamp was modified!")
    
    # 5. No unexpected currency symbols
    if '$$$' in modified or '$$' in modified.replace('$$$', ''):
        warnings.append("Double currency symbols detected")
    
    # 6. Summary section preserved
    if '*** SUMMARY ***' in original and '*** SUMMARY ***' not in modified:
        errors.append("Summary section missing!")
    
    # 7. Table info unchanged
    original_table = re.search(r"Table '([^']+)'", original)
    modified_table = re.search(r"Table '([^']+)'", modified)
    
    if original_table and modified_table:
        if original_table.group(1) != modified_table.group(1):
            warnings.append("Table name was modified")
    
    # 8. Seat count match
    original_seats = len(re.findall(r'^Seat \d+:', original, re.MULTILINE))
    modified_seats = len(re.findall(r'^Seat \d+:', modified, re.MULTILINE))
    
    if original_seats != modified_seats:
        errors.append(f"Seat count mismatch: {original_seats} -> {modified_seats}")
    
    # 9. Chip format preserved
    original_chips = re.findall(r'\$[\d.]+', original)
    modified_chips = re.findall(r'\$[\d.]+', modified)
    
    if len(original_chips) != len(modified_chips):
        warnings.append(
            f"Chip value count changed: {len(original_chips)} -> {len(modified_chips)}"
        )
    
    # Validation result
    valid = len(errors) == 0
    
    return ValidationResult(
        valid=valid,
        errors=errors,
        warnings=warnings
    )
