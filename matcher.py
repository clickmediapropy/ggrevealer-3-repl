"""
Intelligent matching algorithm for pairing hand histories with screenshots
Uses 100-point scoring system with multiple criteria
"""

from typing import List, Optional, Dict
from datetime import timedelta
from models import ParsedHand, ScreenshotAnalysis, HandMatch


def find_best_matches(
    hands: List[ParsedHand],
    screenshots: List[ScreenshotAnalysis],
    confidence_threshold: float = 50.0
) -> List[HandMatch]:
    """
    Find best matches between hands and screenshots
    
    Args:
        hands: List of parsed hands
        screenshots: List of OCR analyzed screenshots
        confidence_threshold: Minimum confidence score (0-100)
        
    Returns:
        List of HandMatch objects above threshold
    """
    matches = []
    
    for hand in hands:
        best_match = None
        best_score = 0.0
        best_breakdown = {}
        best_mapping = None
        
        for screenshot in screenshots:
            # Check for direct hand ID match in filename
            if hand.hand_id in screenshot.screenshot_id:
                score = 100.0
                breakdown = {"direct_match": 100.0}
                mapping = _build_seat_mapping(hand, screenshot)
                
                matches.append(HandMatch(
                    hand_id=hand.hand_id,
                    screenshot_id=screenshot.screenshot_id,
                    confidence=score,
                    score_breakdown=breakdown,
                    auto_mapping=mapping
                ))
                break
            
            # Calculate match score
            score, breakdown = _calculate_match_score(hand, screenshot)
            
            if score > best_score:
                best_score = score
                best_breakdown = breakdown
                best_match = screenshot
                best_mapping = _build_seat_mapping(hand, screenshot)
        
        # Add best match if above threshold and not already matched
        if best_match and best_score >= confidence_threshold:
            # Check if we haven't already added this via direct match
            if not any(m.hand_id == hand.hand_id for m in matches):
                matches.append(HandMatch(
                    hand_id=hand.hand_id,
                    screenshot_id=best_match.screenshot_id,
                    confidence=best_score,
                    score_breakdown=best_breakdown,
                    auto_mapping=best_mapping
                ))
    
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
        if _normalize_cards(hand.board_cards.turn) == _normalize_cards(screenshot.board_cards['turn']):
            board_score += 10.0
    
    # River (10 points)
    if hand.board_cards.river and screenshot.board_cards.get('river'):
        if _normalize_cards(hand.board_cards.river) == _normalize_cards(screenshot.board_cards['river']):
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
    Maps anonymized player IDs to real names
    """
    mapping = {}
    
    # Map by seat position (not by name!)
    for seat in hand.seats:
        if seat.player_id == 'Hero':
            continue  # Never map Hero
        
        # Find player in same seat position in screenshot
        matching_player = next(
            (ps for ps in screenshot.all_player_stacks if ps.position == seat.seat_number),
            None
        )
        
        if matching_player:
            mapping[seat.player_id] = matching_player.player_name
    
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
