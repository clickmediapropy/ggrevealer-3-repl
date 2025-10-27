"""
TXT output writer with name replacement and validation
Ensures PokerTracker compatibility with 9 critical validations
"""

import re
from typing import List, Dict
from collections import defaultdict
from models import NameMapping, ValidationResult, ParsedHand


def extract_table_name(raw_text: str) -> str:
    """
    Extract table name from hand history raw text
    
    Format: Table 'TableName' 6-max Seat #1 is the button
    
    Returns:
        Table name or 'Unknown' if not found
    """
    match = re.search(r"Table '([^']+)'", raw_text)
    if match:
        return match.group(1)
    return "Unknown"


def group_hands_by_table(hands: List[ParsedHand]) -> Dict[str, List[ParsedHand]]:
    """
    Group hands by table name
    
    Args:
        hands: List of ParsedHand objects
        
    Returns:
        Dictionary mapping table_name -> list of hands
    """
    tables = defaultdict(list)
    
    for hand in hands:
        table_name = extract_table_name(hand.raw_text)
        tables[table_name].append(hand)
    
    return dict(tables)


def generate_txt_files_by_table(
    hands: List[ParsedHand],
    mappings: List[NameMapping]
) -> Dict[str, str]:
    """
    Generate separate TXT files for each table
    
    Args:
        hands: List of matched hands
        mappings: Name mappings to apply
        
    Returns:
        Dictionary mapping table_name -> final txt content
    """
    # Group hands by table
    tables = group_hands_by_table(hands)
    
    result = {}
    for table_name, table_hands in tables.items():
        # Combine raw texts for this table
        original_txt = '\n\n'.join([hand.raw_text for hand in table_hands])
        
        # Apply name mappings
        final_txt = generate_final_txt(original_txt, mappings)
        
        # Clean table name for filename (remove invalid chars)
        safe_table_name = re.sub(r'[^\w\-_\.]', '_', table_name)
        result[safe_table_name] = final_txt
    
    return result


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
            rf'(Seat \d+: ){anon_escaped}( \(\$[\d.]+ in chips\))',
            rf'\1{real_name}\2',
            output
        )
        
        # 2. Blind posts: "PlayerID: posts small blind $0.1" (CRITICAL - must come before general actions)
        output = re.sub(
            rf'^{anon_escaped}(: posts (?:small blind|big blind|ante) \$[\d.]+)',
            rf'{real_name}\1',
            output,
            flags=re.MULTILINE
        )
        
        # 3. Action lines: "PlayerID: folds"
        output = re.sub(
            rf'^{anon_escaped}(: (?:folds|checks|calls|bets|raises))',
            rf'{real_name}\1',
            output,
            flags=re.MULTILINE
        )
        
        # 4. All-in actions: "PlayerID: raises $10 to $20 and is all-in" (CRITICAL for Spin & Gold)
        output = re.sub(
            rf'^{anon_escaped}(: (?:raises|calls|bets) \$[\d.]+(?: to \$[\d.]+)? and is all-in)',
            rf'{real_name}\1',
            output,
            flags=re.MULTILINE
        )
        
        # 5. Dealt to (no cards): "Dealt to PlayerID"
        output = re.sub(
            rf'(Dealt to ){anon_escaped}(?![\[\w])',
            rf'\1{real_name}',
            output
        )
        
        # 6. Dealt to (with cards): "Dealt to PlayerID [As Kh]"
        output = re.sub(
            rf'(Dealt to ){anon_escaped}( \[)',
            rf'\1{real_name}\2',
            output
        )
        
        # 7. Collected from pot: "PlayerID collected $100"
        output = re.sub(
            rf'^{anon_escaped}( collected)',
            rf'{real_name}\1',
            output,
            flags=re.MULTILINE
        )
        
        # 8. Shows cards: "PlayerID shows [As Kh]"
        output = re.sub(
            rf'^{anon_escaped}( shows \[)',
            rf'{real_name}\1',
            output,
            flags=re.MULTILINE
        )
        
        # 9. Mucks hand: "PlayerID mucks hand"
        output = re.sub(
            rf'^{anon_escaped}( mucks hand)',
            rf'{real_name}\1',
            output,
            flags=re.MULTILINE
        )
        
        # 10. Doesn't show: "PlayerID doesn't show hand"
        output = re.sub(
            rf'^{anon_escaped}( doesn\'t show hand)',
            rf'{real_name}\1',
            output,
            flags=re.MULTILINE
        )
        
        # 11. Summary lines: "Seat 1: PlayerID (button)"
        output = re.sub(
            rf'(Seat \d+: ){anon_escaped}(\s+\()',
            rf'\1{real_name}\2',
            output
        )
        
        # 12. Uncalled bet returned: "Uncalled bet ($10) returned to PlayerID"
        output = re.sub(
            rf'(returned to ){anon_escaped}$',
            rf'\1{real_name}',
            output,
            flags=re.MULTILINE
        )
        
        # 13. EV Cashout: "PlayerID: Chooses to EV Cashout" (GGPoker specific)
        output = re.sub(
            rf'^{anon_escaped}(: Chooses to EV Cashout)',
            rf'{real_name}\1',
            output,
            flags=re.MULTILINE
        )
    
    return output


def validate_output_format(original: str, modified: str) -> ValidationResult:
    """
    Validate output format for PokerTracker compatibility
    
    10 critical validations:
    1. Hero preservation
    2. Line count match
    3. Hand ID unchanged
    4. Timestamp unchanged
    5. No unexpected currency symbols
    6. Summary section preserved
    7. Table info unchanged
    8. Seat count match
    9. Chip format preserved
    10. No unmapped anonymous IDs
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
    
    # 10. No unmapped anonymous IDs remaining (CRITICAL for data integrity)
    # GGPoker anonymous IDs: 6-8 character alphanumeric strings (e.g., 32fa3d21, bf27d3a)
    anon_pattern = r'\b[a-f0-9]{6,8}\b'
    
    remaining_anon = set()
    for match in re.finditer(anon_pattern, modified, re.IGNORECASE):
        anon_id = match.group(0)
        # Verify it appears in player context (not in timestamps/card notation/hand IDs)
        # Check if it appears at start of line (player action) or after "Seat N:"
        if re.search(rf'(?:^{anon_id}:|Seat \d+: {anon_id})', modified, re.MULTILINE):
            remaining_anon.add(anon_id)
    
    if remaining_anon:
        warnings.append(
            f"Possible unmapped anonymous IDs found: {', '.join(sorted(remaining_anon))}. "
            "This will cause PokerTracker import errors!"
        )
    
    # Validation result
    valid = len(errors) == 0
    
    return ValidationResult(
        valid=valid,
        errors=errors,
        warnings=warnings
    )
