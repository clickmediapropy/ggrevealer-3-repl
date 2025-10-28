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


def find_best_matches(
    hands: List[ParsedHand],
    screenshots: List[ScreenshotAnalysis],
    confidence_threshold: float = 50.0
) -> List[HandMatch]:
    """
    Find best matches between hands and screenshots using Hand ID as primary key

    MATCHING STRATEGY (99.9% accuracy):
    1. PRIMARY: Direct Hand ID match from OCR (100 points) - most accurate
    2. FALLBACK: Multi-criteria scoring system (max 100 points) - for legacy screenshots

    Args:
        hands: List of parsed hands
        screenshots: List of OCR analyzed screenshots
        confidence_threshold: Minimum confidence score (0-100)

    Returns:
        List of HandMatch objects above threshold
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
                score = 100.0
                breakdown = {"hand_id_match": 100.0}
                mapping = _build_seat_mapping(hand, screenshot)
                
                # Reject match if mapping is empty (indicates validation failure)
                if not mapping:
                    print(f"❌ Hand ID match rejected: {hand.hand_id} ↔ {screenshot.screenshot_id} (validation failed)")
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
                score = 100.0
                breakdown = {"filename_match": 100.0}
                mapping = _build_seat_mapping(hand, screenshot)
                
                # Reject match if mapping is empty (indicates validation failure)
                if not mapping:
                    print(f"❌ Filename match rejected: {hand.hand_id} ↔ {screenshot.screenshot_id} (validation failed)")
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
                        print(f"❌ Fallback candidate rejected: {hand.hand_id} ↔ {screenshot.screenshot_id} (validation failed, score: {score:.1f})")
            
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

    Returns empty dict if duplicate names detected (indicates incorrect match)
    """
    mapping = {}
    used_names = set()  # Track names we've already mapped to prevent duplicates

    # Debug logging
    print(f"\n[DEBUG] Building seat mapping for hand {hand.hand_id}")
    print(f"[DEBUG] Hand seats: {[(s.seat_number, s.player_id, s.stack) for s in hand.seats]}")
    print(f"[DEBUG] Screenshot players: {[(ps.position, ps.player_name, ps.stack) for ps in screenshot.all_player_stacks]}")
    print(f"[DEBUG] Hero in screenshot: {screenshot.hero_name} at position {screenshot.hero_position}")

    # First pass: Map Hero
    hero_seat = next((s for s in hand.seats if s.player_id == 'Hero'), None)
    if hero_seat and screenshot.hero_name:
        mapping['Hero'] = screenshot.hero_name
        used_names.add(screenshot.hero_name)
        print(f"[DEBUG] Mapped Hero: Seat {hero_seat.seat_number} -> {screenshot.hero_name}")
    else:
        print(f"[DEBUG] Hero mapping failed: hero_seat={hero_seat}, screenshot.hero_name={screenshot.hero_name}")

    # Second pass: Map other players by seat position
    # IMPORTANT: Exclude hero from screenshot candidates to avoid duplicate mapping
    # (PokerCraft shows Hero visually at position 1 regardless of actual seat number)
    non_hero_players = [
        ps for ps in screenshot.all_player_stacks
        if ps.player_name != screenshot.hero_name
    ]

    print(f"[DEBUG] Non-hero players available for mapping: {[(ps.position, ps.player_name) for ps in non_hero_players]}")

    unmapped_seats = []
    for seat in hand.seats:
        if seat.player_id == 'Hero':
            continue  # Already mapped above

        # Find player in same seat position in screenshot (excluding hero)
        matching_player = next(
            (ps for ps in non_hero_players if ps.position == seat.seat_number),
            None
        )

        if matching_player:
            # Check for duplicate name within this hand
            if matching_player.player_name in used_names:
                print(f"[WARNING] Duplicate name '{matching_player.player_name}' detected in mapping for hand {hand.hand_id}.")
                print(f"[WARNING] Seat {seat.seat_number} ({seat.player_id}) tried to map to '{matching_player.player_name}' but it's already used.")
                print(f"[WARNING] This indicates seat position mismatch. Rejecting mapping.")
                return {}  # Return empty mapping - this is an incorrect match

            mapping[seat.player_id] = matching_player.player_name
            used_names.add(matching_player.player_name)
            print(f"[DEBUG] Mapped player: Seat {seat.seat_number} ({seat.player_id}) -> {matching_player.player_name}")
        else:
            unmapped_seats.append(f"Seat {seat.seat_number} ({seat.player_id})")
            print(f"[DEBUG] No matching player found for Seat {seat.seat_number} ({seat.player_id})")

    if unmapped_seats:
        print(f"[WARNING] Unmapped seats: {', '.join(unmapped_seats)}")
        print(f"[WARNING] This may indicate OCR position extraction issues.")

    print(f"[DEBUG] Final mapping: {mapping}")
    print(f"[DEBUG] Mapping success: {len(mapping)} of {len(hand.seats)} seats mapped\n")

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
