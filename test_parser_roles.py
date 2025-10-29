"""Tests for parser role-finding functionality"""
import pytest
from parser import GGPokerParser, find_seat_by_role

def test_find_seat_by_role_button():
    """Test finding button seat"""
    hand_text = """
Poker Hand #SG3247423387: Hold'em No Limit ($0.02/$0.04) - 2025/10/22 11:32:00
Table 'Test' 3-max Seat #3 is the button
Seat 1: Hero ($3.00 in chips)
Seat 2: c460cec2 ($3.00 in chips)
Seat 3: 9018bbd8 ($3.00 in chips)
Hero: posts small blind $0.02
c460cec2: posts big blind $0.04
    """
    hand = GGPokerParser.parse_hand(hand_text)

    button_seat = find_seat_by_role(hand, "button")
    assert button_seat is not None
    assert button_seat.seat_number == 3
    assert button_seat.player_id == "9018bbd8"

def test_find_seat_by_role_small_blind():
    """Test finding small blind seat"""
    hand_text = """
Poker Hand #SG3247423387: Hold'em No Limit ($0.02/$0.04) - 2025/10/22 11:32:00
Table 'Test' 3-max Seat #3 is the button
Seat 1: Hero ($3.00 in chips)
Seat 2: c460cec2 ($3.00 in chips)
Seat 3: 9018bbd8 ($3.00 in chips)
Hero: posts small blind $0.02
c460cec2: posts big blind $0.04
    """
    hand = GGPokerParser.parse_hand(hand_text)

    sb_seat = find_seat_by_role(hand, "small blind")
    assert sb_seat is not None
    assert sb_seat.player_id == "Hero"

def test_find_seat_by_role_big_blind():
    """Test finding big blind seat"""
    hand_text = """
Poker Hand #SG3247423387: Hold'em No Limit ($0.02/$0.04) - 2025/10/22 11:32:00
Table 'Test' 3-max Seat #3 is the button
Seat 1: Hero ($3.00 in chips)
Seat 2: c460cec2 ($3.00 in chips)
Seat 3: 9018bbd8 ($3.00 in chips)
Hero: posts small blind $0.02
c460cec2: posts big blind $0.04
    """
    hand = GGPokerParser.parse_hand(hand_text)

    bb_seat = find_seat_by_role(hand, "big blind")
    assert bb_seat is not None
    assert bb_seat.player_id == "c460cec2"

def test_find_seat_by_role_invalid():
    """Test invalid role returns None"""
    hand_text = """
Poker Hand #SG3247423387: Hold'em No Limit ($0.02/$0.04) - 2025/10/22 11:32:00
Table 'Test' 3-max Seat #3 is the button
Seat 1: Hero ($3.00 in chips)
    """
    hand = GGPokerParser.parse_hand(hand_text)

    result = find_seat_by_role(hand, "invalid_role")
    assert result is None
