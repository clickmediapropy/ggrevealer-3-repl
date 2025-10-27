"""
GGPoker TXT Hand History Parser
Extracts structured data from GGPoker hand history files
"""

import re
from datetime import datetime
from typing import List, Optional, cast
from models import ParsedHand, Seat, BoardCards, Action, TournamentInfo, Position, ActionType


class GGPokerParser:
    """Parser for GGPoker hand history TXT files"""
    
    @staticmethod
    def parse_file(content: str) -> List[ParsedHand]:
        """Parse multiple hands from a TXT file"""
        hands = []
        hand_texts = re.split(r'\n\s*\n\s*\n', content.strip())
        
        for hand_text in hand_texts:
            if hand_text.strip():
                hand = GGPokerParser.parse_hand(hand_text.strip())
                if hand:
                    hands.append(hand)
        
        return hands
    
    @staticmethod
    def parse_hand(text: str) -> Optional[ParsedHand]:
        """Parse a single hand from text"""
        try:
            # Extract hand ID
            hand_id_match = re.search(r'Poker Hand #(\S+):', text)
            if not hand_id_match:
                return None
            hand_id = hand_id_match.group(1)
            
            # Extract timestamp
            timestamp_match = re.search(r'(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})', text)
            if not timestamp_match:
                return None
            timestamp = datetime.strptime(timestamp_match.group(1), '%Y/%m/%d %H:%M:%S')
            
            # Extract game type and stakes
            game_match = re.search(r"Poker Hand #\S+: (.*?) \((.*?)\)", text)
            if not game_match:
                return None
            game_type = game_match.group(1)
            stakes = game_match.group(2)
            
            # Detect table format
            table_format = '6-max'
            if '3-max' in text or re.search(r'Table.*3-max', text):
                table_format = '3-max'
            
            # Extract button seat
            button_match = re.search(r'Seat #(\d+) is the button', text)
            button_seat = int(button_match.group(1)) if button_match else 1
            
            # Parse seats
            seats = GGPokerParser._parse_seats(text, button_seat, table_format)
            
            # Parse board cards
            board_cards = GGPokerParser._parse_board_cards(text)
            
            # Parse hero cards
            hero_cards = GGPokerParser._parse_hero_cards(text)
            
            # Parse actions
            actions = GGPokerParser._parse_actions(text)
            
            # Check for tournament info
            tournament_info = GGPokerParser._parse_tournament_info(text)
            
            return ParsedHand(
                hand_id=hand_id,
                timestamp=timestamp,
                game_type=game_type,
                stakes=stakes,
                table_format=table_format,
                button_seat=button_seat,
                seats=seats,
                board_cards=board_cards,
                actions=actions,
                raw_text=text,
                hero_cards=hero_cards,
                tournament_info=tournament_info
            )
            
        except Exception as e:
            print(f"Error parsing hand: {e}")
            return None
    
    @staticmethod
    def _parse_seats(text: str, button_seat: int, table_format: str) -> List[Seat]:
        """Parse seat information"""
        seats = []
        seat_pattern = r'Seat (\d+): ([^\(]+) \(\$?([\d.]+) in chips\)'
        
        for match in re.finditer(seat_pattern, text):
            seat_num = int(match.group(1))
            player_id = match.group(2).strip()
            stack = float(match.group(3))
            
            # Determine position
            position = GGPokerParser._get_position(seat_num, button_seat, table_format)
            
            seats.append(Seat(
                seat_number=seat_num,
                player_id=player_id,
                stack=stack,
                position=cast(Position, position)
            ))
        
        return seats
    
    @staticmethod
    def _get_position(seat_num: int, button_seat: int, table_format: str) -> str:
        """Determine player position based on seat and button"""
        if seat_num == button_seat:
            return 'BTN'
        
        max_seats = 3 if table_format == '3-max' else 6
        
        # Calculate positions relative to button
        seats_after_button = (seat_num - button_seat) % max_seats
        
        if table_format == '3-max':
            if seats_after_button == 1:
                return 'SB'
            elif seats_after_button == 2:
                return 'BB'
        else:  # 6-max
            if seats_after_button == 1:
                return 'SB'
            elif seats_after_button == 2:
                return 'BB'
            elif seats_after_button == 3:
                return 'UTG'
            elif seats_after_button == 4:
                return 'MP'
            elif seats_after_button == 5:
                return 'CO'
        
        return 'BTN'
    
    @staticmethod
    def _parse_board_cards(text: str) -> BoardCards:
        """Parse board cards from text"""
        board = BoardCards()
        
        # Flop
        flop_match = re.search(r'\*\*\* FLOP \*\*\* \[([^\]]+)\]', text)
        if flop_match:
            cards = flop_match.group(1).strip().split()
            board.flop = cards
        
        # Turn
        turn_match = re.search(r'\*\*\* TURN \*\*\* \[.*?\] \[([^\]]+)\]', text)
        if turn_match:
            board.turn = turn_match.group(1).strip()
        
        # River
        river_match = re.search(r'\*\*\* RIVER \*\*\* \[.*?\] \[([^\]]+)\]', text)
        if river_match:
            board.river = river_match.group(1).strip()
        
        return board
    
    @staticmethod
    def _parse_hero_cards(text: str) -> Optional[str]:
        """Parse hero's hole cards"""
        hero_match = re.search(r'Dealt to Hero \[([^\]]+)\]', text)
        if hero_match:
            return hero_match.group(1).strip()
        return None
    
    @staticmethod
    def _parse_actions(text: str) -> List[Action]:
        """Parse all actions in the hand"""
        actions = []
        current_street = 'PREFLOP'
        
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            
            # Update street
            if '*** HOLE CARDS ***' in line:
                current_street = 'PREFLOP'
            elif '*** FLOP ***' in line:
                current_street = 'FLOP'
            elif '*** TURN ***' in line:
                current_street = 'TURN'
            elif '*** RIVER ***' in line:
                current_street = 'RIVER'
            elif '*** SHOW DOWN ***' in line or '*** SUMMARY ***' in line:
                current_street = 'SHOWDOWN'
            
            # Parse action
            action_match = re.match(r'([^:]+): (folds|checks|calls|bets|raises)(?: \$?([\d.]+))?(?: to \$?([\d.]+))?', line)
            if action_match:
                player = action_match.group(1).strip()
                action_type = action_match.group(2)
                amount = None
                
                if action_match.group(4):  # raise to amount
                    amount = float(action_match.group(4))
                elif action_match.group(3):  # bet/call amount
                    amount = float(action_match.group(3))
                
                actions.append(Action(
                    street=current_street,
                    player=player,
                    action=cast(ActionType, action_type),
                    amount=amount
                ))
            
            # Parse collected
            collected_match = re.match(r'([^:]+) collected \$?([\d.]+)', line)
            if collected_match:
                actions.append(Action(
                    street=current_street,
                    player=collected_match.group(1).strip(),
                    action='collected',
                    amount=float(collected_match.group(2))
                ))
            
            # Parse posts
            post_match = re.match(r'([^:]+): posts (?:small blind|big blind|ante) \$?([\d.]+)', line)
            if post_match:
                actions.append(Action(
                    street='PREFLOP',
                    player=post_match.group(1).strip(),
                    action='posts',
                    amount=float(post_match.group(2))
                ))
        
        return actions
    
    @staticmethod
    def _parse_tournament_info(text: str) -> Optional[TournamentInfo]:
        """Parse tournament information if present"""
        if 'Tournament' not in text:
            return None
        
        tournament_id = None
        buy_in = None
        level = None
        
        # Extract tournament ID
        tour_id_match = re.search(r'Tournament #(\d+)', text)
        if tour_id_match:
            tournament_id = tour_id_match.group(1)
        
        # Extract buy-in
        buyin_match = re.search(r'\$(\d+(?:\.\d+)?)\+\$(\d+(?:\.\d+)?)', text)
        if buyin_match:
            buy_in = f"${buyin_match.group(1)}+${buyin_match.group(2)}"
        
        # Extract level
        level_match = re.search(r'Level (\w+)', text)
        if level_match:
            level = level_match.group(1)
        
        if tournament_id or buy_in or level:
            return TournamentInfo(
                tournament_id=tournament_id,
                buy_in=buy_in,
                level=level
            )
        
        return None
