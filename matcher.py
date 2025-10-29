"""
Intelligent matching algorithm for pairing hand histories with screenshots
Uses 100-point scoring system with multiple criteria
"""

from typing import List, Optional, Dict
from datetime import timedelta
from models import ParsedHand, ScreenshotAnalysis, HandMatch


def _normalize_hand_id(hand_id: str) -> str:
    """
    Normalize hand_id by removing common prefixes (SG, HH, etc.)
    This ensures OCR-extracted IDs match parser-extracted IDs

    Examples:
        "SG3260934198" -> "3260934198"
        "3260934198" -> "3260934198"
        "HH1234567890" -> "1234567890"
    """
    if not hand_id:
        return ""

    # Remove common GGPoker hand ID prefixes
    prefixes = ['SG', 'HH', 'MT', 'TT']
    for prefix in prefixes:
        if hand_id.startswith(prefix):
            return hand_id[len(prefix):]

    return hand_id


def validate_match_quality(hand: ParsedHand, screenshot: ScreenshotAnalysis) -> tuple[bool, str]:
    """
    Validate that a hand and screenshot actually match before accepting the pairing.
    This prevents incorrect matches that would result in failed mappings.
    
    Validation checks:
    1. Number of players must match
    2. Hero stack must be similar (±25% tolerance)
    3. Player stacks must generally align (allows for antes/blinds posted)
    
    Returns:
        (is_valid, reason) - True if match is valid, False with reason otherwise
    """
    # Check 1: Verify player count matches
    hand_player_count = len(hand.seats)
    screenshot_player_count = len(screenshot.all_player_stacks)
    
    if hand_player_count != screenshot_player_count:
        return False, f"Player count mismatch: hand has {hand_player_count}, screenshot has {screenshot_player_count}"
    
    # Check 2: Verify Hero stack is similar
    hero_seat = next((s for s in hand.seats if s.player_id == 'Hero'), None)
    if not hero_seat:
        return False, "No Hero found in hand"
    
    hero_hand_stack = hero_seat.stack
    hero_screenshot_stack = screenshot.hero_stack
    
    if hero_screenshot_stack and hero_hand_stack > 0:
        # Allow 25% tolerance for stacks (accounts for blinds/antes posted)
        stack_diff_ratio = abs(hero_hand_stack - hero_screenshot_stack) / hero_hand_stack
        if stack_diff_ratio > 0.25:
            return False, f"Hero stack mismatch: hand has ${hero_hand_stack}, screenshot has ${hero_screenshot_stack} ({stack_diff_ratio*100:.1f}% diff)"
    
    # Check 3: Verify general stack alignment (at least 50% of stacks should be close)
    # This is a softer check since stacks change rapidly in poker
    matching_stacks = 0
    total_comparisons = 0
    
    for hand_seat in hand.seats:
        # Find corresponding player in screenshot (we don't know mapping yet, so just check if ANY stack is close)
        for ss_player in screenshot.all_player_stacks:
            if hand_seat.stack > 0 and ss_player.stack > 0:
                diff_ratio = abs(hand_seat.stack - ss_player.stack) / hand_seat.stack
                if diff_ratio <= 0.30:  # 30% tolerance
                    matching_stacks += 1
                    break
        total_comparisons += 1
    
    if total_comparisons > 0:
        match_ratio = matching_stacks / total_comparisons
        if match_ratio < 0.5:  # At least 50% should match
            return False, f"Stack alignment too low: only {matching_stacks}/{total_comparisons} players have similar stacks"
    
    return True, "Valid match"


def find_best_matches(
    hands: List[ParsedHand],
    screenshots: List[ScreenshotAnalysis],
    confidence_threshold: float = 70.0
) -> List[HandMatch]:
    """
    Find best matches between hands and screenshots using Hand ID as primary key

    MATCHING STRATEGY (enhanced with validation):
    1. PRIMARY: Direct Hand ID match from OCR (100 points) - most accurate
    2. FALLBACK: Multi-criteria scoring system (max 100 points) - for legacy screenshots
    
    VALIDATION GATES (prevents incorrect matches):
    - Player count must match (hand seats vs screenshot players)
    - Hero stack must be similar (±25% tolerance)
    - General stack alignment (≥50% of stacks within ±30%)

    Args:
        hands: List of parsed hands
        screenshots: List of OCR analyzed screenshots
        confidence_threshold: Minimum confidence score (0-100, default: 70.0)

    Returns:
        List of HandMatch objects above threshold and passing validation
    """
    matches = []
    matched_screenshots = set()  # Track used screenshots to prevent duplicates

    for hand in hands:
        matched = False

        # STRATEGY 1: Try Hand ID matching first (PRIMARY - 99.9% accuracy)
        for screenshot in screenshots:
            if screenshot.screenshot_id in matched_screenshots:
                continue  # Skip already matched screenshots

            # Check if screenshot has extracted Hand ID from OCR
            # Normalize both IDs to handle prefix differences (OCR omits "SG", parser includes it)
            normalized_screenshot_id = _normalize_hand_id(screenshot.hand_id) if screenshot.hand_id else None
            normalized_hand_id = _normalize_hand_id(hand.hand_id)

            if normalized_screenshot_id and normalized_screenshot_id == normalized_hand_id:
                # Validate match quality before accepting
                is_valid, reason = validate_match_quality(hand, screenshot)
                if not is_valid:
                    print(f"❌ Hand ID match rejected: {hand.hand_id} ↔ {screenshot.screenshot_id} ({reason})")
                    continue  # Try next screenshot
                
                score = 100.0
                breakdown = {"hand_id_match": 100.0}
                mapping = _build_seat_mapping(hand, screenshot)
                
                # Reject match if mapping is empty (indicates validation failure)
                if not mapping:
                    print(f"❌ Hand ID match rejected: {hand.hand_id} ↔ {screenshot.screenshot_id} (mapping validation failed)")
                    continue  # Try next screenshot
                
                matches.append(HandMatch(
                    hand_id=hand.hand_id,
                    screenshot_id=screenshot.screenshot_id,
                    confidence=score,
                    score_breakdown=breakdown,
                    auto_mapping=mapping
                ))
                matched_screenshots.add(screenshot.screenshot_id)
                matched = True
                print(f"✅ Hand ID match: {hand.hand_id} ↔ {screenshot.screenshot_id}")
                break
            
            # Legacy: Check for hand ID in filename (backward compatibility)
            if hand.hand_id in screenshot.screenshot_id:
                # Validate match quality before accepting
                is_valid, reason = validate_match_quality(hand, screenshot)
                if not is_valid:
                    print(f"❌ Filename match rejected: {hand.hand_id} ↔ {screenshot.screenshot_id} ({reason})")
                    continue  # Try next screenshot
                
                score = 100.0
                breakdown = {"filename_match": 100.0}
                mapping = _build_seat_mapping(hand, screenshot)
                
                # Reject match if mapping is empty (indicates validation failure)
                if not mapping:
                    print(f"❌ Filename match rejected: {hand.hand_id} ↔ {screenshot.screenshot_id} (mapping validation failed)")
                    continue  # Try next screenshot
                
                matches.append(HandMatch(
                    hand_id=hand.hand_id,
                    screenshot_id=screenshot.screenshot_id,
                    confidence=score,
                    score_breakdown=breakdown,
                    auto_mapping=mapping
                ))
                matched_screenshots.add(screenshot.screenshot_id)
                matched = True
                print(f"✅ Filename match: {hand.hand_id} ↔ {screenshot.screenshot_id}")
                break
        
        # STRATEGY 2: Fallback to multi-criteria scoring (for screenshots without Hand ID)
        if not matched:
            best_match = None
            best_score = 0.0
            best_breakdown = {}
            best_mapping = None
            
            for screenshot in screenshots:
                if screenshot.screenshot_id in matched_screenshots:
                    continue  # Skip already matched screenshots
                
                # Calculate match score using cards, position, board, etc.
                score, breakdown = _calculate_match_score(hand, screenshot)
                
                if score > best_score:
                    # Validate match quality FIRST (prevents bad matches from even being considered)
                    is_valid, reason = validate_match_quality(hand, screenshot)
                    if not is_valid:
                        print(f"❌ Fallback candidate rejected: {hand.hand_id} ↔ {screenshot.screenshot_id} ({reason}, score: {score:.1f})")
                        continue
                    
                    # Build mapping and validate BEFORE accepting as best candidate
                    mapping = _build_seat_mapping(hand, screenshot)
                    
                    # Only accept if mapping is valid (not empty)
                    if mapping:
                        best_score = score
                        best_breakdown = breakdown
                        best_match = screenshot
                        best_mapping = mapping
                    else:
                        # Log rejected candidate
                        print(f"❌ Fallback candidate rejected: {hand.hand_id} ↔ {screenshot.screenshot_id} (mapping validation failed, score: {score:.1f})")
            
            # Add best match if above threshold
            if best_match and best_score >= confidence_threshold:
                matches.append(HandMatch(
                    hand_id=hand.hand_id,
                    screenshot_id=best_match.screenshot_id,
                    confidence=best_score,
                    score_breakdown=best_breakdown,
                    auto_mapping=best_mapping
                ))
                matched_screenshots.add(best_match.screenshot_id)
                print(f"⚠️  Fallback match: {hand.hand_id} ↔ {best_match.screenshot_id} (score: {best_score:.1f})")
    
    print(f"\n📊 Matching Summary: {len(matches)} matches found from {len(hands)} hands")
    hand_id_matches = sum(1 for m in matches if 'hand_id_match' in m.score_breakdown)
    filename_matches = sum(1 for m in matches if 'filename_match' in m.score_breakdown)
    fallback_matches = len(matches) - hand_id_matches - filename_matches
    print(f"   - Hand ID matches (OCR): {hand_id_matches}")
    print(f"   - Filename matches: {filename_matches}")
    print(f"   - Fallback matches: {fallback_matches}")
    
    return matches


def _calculate_match_score(hand: ParsedHand, screenshot: ScreenshotAnalysis) -> tuple[float, Dict[str, float]]:
    """
    Calculate match score using 100-point system:
    - Timestamp: 20pts (±5min = 20pts, ±10min = 10pts)
    - Hero cards: 40pts (exact match)
    - Hero position: 15pts
    - Board cards: 30pts (flop 10 + turn 10 + river 10)
    - Stack size: 5pts (±20%)
    - Player names: 10pts (2pts per player match)
    """
    score = 0.0
    breakdown = {}
    
    # 1. Timestamp matching (20 points)
    # Note: Screenshots don't have timestamps in current implementation
    # This would require timestamp extraction from screenshots
    timestamp_score = 0.0
    breakdown['timestamp'] = timestamp_score
    
    # 2. Hero cards matching (40 points) - MOST IMPORTANT
    hero_cards_score = 0.0
    if hand.hero_cards and screenshot.hero_cards:
        if _normalize_cards(hand.hero_cards) == _normalize_cards(screenshot.hero_cards):
            hero_cards_score = 40.0
        elif _cards_similar(hand.hero_cards, screenshot.hero_cards):
            hero_cards_score = 20.0  # Partial match (e.g., one card matches)
    breakdown['hero_cards'] = hero_cards_score
    score += hero_cards_score
    
    # 3. Hero position matching (15 points)
    hero_position_score = 0.0
    if screenshot.hero_name and screenshot.hero_position:
        # Find hero in hand seats
        hero_seat = next((s for s in hand.seats if s.player_id == 'Hero'), None)
        if hero_seat and hero_seat.seat_number == screenshot.hero_position:
            hero_position_score = 15.0
    breakdown['hero_position'] = hero_position_score
    score += hero_position_score
    
    # 4. Board cards matching (30 points total)
    board_score = 0.0
    
    # Flop (10 points)
    if hand.board_cards.flop and screenshot.board_cards:
        screenshot_flop = [
            screenshot.board_cards.get('flop1'),
            screenshot.board_cards.get('flop2'),
            screenshot.board_cards.get('flop3')
        ]
        screenshot_flop = [c for c in screenshot_flop if c]
        
        if len(screenshot_flop) == 3 and len(hand.board_cards.flop) == 3:
            flop_matches = sum(1 for c in hand.board_cards.flop if c in screenshot_flop)
            board_score += (flop_matches / 3.0) * 10.0
    
    # Turn (10 points)
    if hand.board_cards.turn and screenshot.board_cards.get('turn'):
        turn_card = screenshot.board_cards.get('turn')
        if turn_card and _normalize_cards(hand.board_cards.turn) == _normalize_cards(turn_card):
            board_score += 10.0
    
    # River (10 points)
    if hand.board_cards.river and screenshot.board_cards.get('river'):
        river_card = screenshot.board_cards.get('river')
        if river_card and _normalize_cards(hand.board_cards.river) == _normalize_cards(river_card):
            board_score += 10.0
    
    breakdown['board_cards'] = board_score
    score += board_score
    
    # 5. Stack size matching (5 points)
    stack_score = 0.0
    if screenshot.hero_name and screenshot.hero_stack:
        hero_seat = next((s for s in hand.seats if s.player_id == 'Hero'), None)
        if hero_seat:
            stack_diff_pct = abs(hero_seat.stack - screenshot.hero_stack) / hero_seat.stack
            if stack_diff_pct <= 0.20:  # Within 20%
                stack_score = 5.0 * (1.0 - stack_diff_pct / 0.20)
    breakdown['stack_size'] = stack_score
    score += stack_score
    
    # 6. Player name matching (10 points - 2pts per player, max 5 players)
    player_score = 0.0
    hand_players = set(s.player_id for s in hand.seats if s.player_id != 'Hero')
    screenshot_players = set(screenshot.player_names) - {'Hero', screenshot.hero_name}
    
    matching_players = len(hand_players & screenshot_players)
    player_score = min(matching_players * 2.0, 10.0)
    
    breakdown['player_names'] = player_score
    score += player_score
    
    return score, breakdown


def _build_seat_mapping(hand: ParsedHand, screenshot: ScreenshotAnalysis) -> Dict[str, str]:
    """
    Build name mapping from hand to screenshot based on seat positions
    Maps anonymized player IDs to real names (including Hero to real hero name)

    IMPORTANT: PokerCraft reorganizes visual positions with Hero always at position 1.
    We must calculate real seat numbers from visual positions using counter-clockwise mapping.

    Returns empty dict if duplicate names detected (indicates incorrect match)
    """
    mapping = {}
    used_names = set()  # Track names we've already mapped to prevent duplicates

    # Debug logging
    print(f"\n[DEBUG] Building seat mapping for hand {hand.hand_id}")
    print(f"[DEBUG] Hand seats: {[(s.seat_number, s.player_id, s.stack) for s in hand.seats]}")
    print(f"[DEBUG] Screenshot players: {[(ps.position, ps.player_name, ps.stack) for ps in screenshot.all_player_stacks]}")
    print(f"[DEBUG] Hero in screenshot: {screenshot.hero_name} at position {screenshot.hero_position}")

    # Step 1: Find Hero's real seat number in hand history
    hero_seat = next((s for s in hand.seats if s.player_id == 'Hero'), None)
    if not hero_seat:
        print(f"[ERROR] No Hero seat found in hand {hand.hand_id}")
        return {}

    hero_seat_number = hero_seat.seat_number
    max_seats = len(hand.seats)  # Usually 3 for 3-max

    print(f"[DEBUG] Hero is at Seat {hero_seat_number} (real seat number)")
    print(f"[DEBUG] Table has {max_seats} seats in hand history")

    # Step 2: Build mapping for ALL players in screenshot using counter-clockwise order
    # PokerCraft shows Hero at visual position 1, then other players in counter-clockwise order
    # 
    # IMPORTANT: PokerCraft visual positions are not seat numbers!
    # - Visual position is the display order on screen (Hero always at position 1)
    # - We need to calculate the REAL seat number from the visual position
    # - Formula: real_seat = hero_seat - (visual_position - 1), with wrap-around
    
    # Get all available seat numbers from hand history
    available_seats = sorted([s.seat_number for s in hand.seats])
    print(f"[DEBUG] Available seats in hand: {available_seats}")
    print(f"[DEBUG] Screenshot shows {len(screenshot.all_player_stacks)} players")
    
    for player_stack in screenshot.all_player_stacks:
        visual_position = player_stack.position
        real_name = player_stack.player_name

        # Calculate real seat number using counter-clockwise mapping
        # Visual position 1 = Hero's seat
        # Visual position 2 = Seat before Hero (counter-clockwise)
        # Visual position 3 = Seat 2 before Hero (counter-clockwise)
        offset = visual_position - 1
        real_seat_number = hero_seat_number - offset

        # Handle wrap-around for negative seat numbers
        # If we go below 1, wrap around to the end
        while real_seat_number < 1:
            real_seat_number += max_seats

        print(f"[DEBUG] Visual position {visual_position} → Real seat {real_seat_number} (hero={hero_seat_number}, offset={offset})")

        # Find the anonymized ID at this real seat
        seat_at_position = next((s for s in hand.seats if s.seat_number == real_seat_number), None)

        if not seat_at_position:
            print(f"[WARNING] No seat found at position {real_seat_number} in hand history")
            print(f"[WARNING] Available seats: {available_seats}, looking for seat {real_seat_number}")
            continue

        anon_id = seat_at_position.player_id

        # Check for duplicate name within this hand
        if real_name in used_names:
            print(f"[WARNING] Duplicate name '{real_name}' detected in mapping for hand {hand.hand_id}.")
            print(f"[WARNING] Seat {real_seat_number} ({anon_id}) tried to map to '{real_name}' but it's already used.")
            print(f"[WARNING] This indicates incorrect match. Rejecting mapping.")
            return {}  # Return empty mapping - this is an incorrect match

        # Add mapping
        mapping[anon_id] = real_name
        used_names.add(real_name)
        print(f"[DEBUG] Mapped: Seat {real_seat_number} ({anon_id}) → {real_name}")

    print(f"[DEBUG] Final mapping: {mapping}")
    print(f"[DEBUG] Mapping success: {len(mapping)} of {len(hand.seats)} seats mapped\n")

    # Verify we mapped all seats
    if len(mapping) != len(hand.seats):
        unmapped = [s.player_id for s in hand.seats if s.player_id not in mapping]
        print(f"[WARNING] Not all seats mapped. Unmapped: {unmapped}")

    return mapping


def _normalize_cards(cards: str) -> str:
    """Normalize card string for comparison"""
    # Remove spaces and sort
    card_list = cards.strip().split()
    return ' '.join(sorted(card_list))


def _cards_similar(cards1: str, cards2: str) -> bool:
    """Check if two card strings have at least one matching card"""
    cards1_list = set(cards1.strip().split())
    cards2_list = set(cards2.strip().split())
    return len(cards1_list & cards2_list) > 0


def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculate Levenshtein distance for fuzzy string matching"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]
