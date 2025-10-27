"""
Type definitions for GGRevealer
Dataclasses for parsed hands, OCR results, matches, and mappings
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Literal


# ============================================================================
# PARSER TYPES
# ============================================================================

Position = Literal['BTN', 'SB', 'BB', 'UTG', 'MP', 'CO', 'UTG+1', 'UTG+2']
Street = Literal['PREFLOP', 'FLOP', 'TURN', 'RIVER', 'SHOWDOWN']
ActionType = Literal['folds', 'checks', 'calls', 'bets', 'raises', 'shows', 'collected', 'posts']


@dataclass
class Seat:
    """Player seat information"""
    seat_number: int
    player_id: str
    stack: float
    position: Position


@dataclass
class BoardCards:
    """Community cards on the board"""
    flop: Optional[List[str]] = None
    turn: Optional[str] = None
    river: Optional[str] = None


@dataclass
class Action:
    """Player action in a hand"""
    street: Street
    player: str
    action: ActionType
    amount: Optional[float] = None


@dataclass
class TournamentInfo:
    """Tournament-specific information"""
    tournament_id: Optional[str] = None
    buy_in: Optional[str] = None
    level: Optional[str] = None


@dataclass
class ParsedHand:
    """Parsed poker hand from GGPoker TXT file"""
    hand_id: str
    timestamp: datetime
    game_type: str
    stakes: str
    table_format: Literal['3-max', '6-max']
    button_seat: int
    seats: List[Seat]
    board_cards: BoardCards
    actions: List[Action]
    raw_text: str
    hero_cards: Optional[str] = None
    tournament_info: Optional[TournamentInfo] = None


# ============================================================================
# OCR TYPES
# ============================================================================

@dataclass
class PlayerStack:
    """Player stack information from OCR"""
    player_name: str
    stack: float
    position: int


@dataclass
class ScreenshotAnalysis:
    """OCR analysis result from a screenshot"""
    screenshot_id: str
    timestamp: Optional[str] = None
    table_name: Optional[str] = None
    player_names: List[str] = field(default_factory=list)
    hero_name: Optional[str] = None
    hero_position: Optional[int] = None
    hero_stack: Optional[float] = None
    hero_cards: Optional[str] = None
    board_cards: Dict[str, Optional[str]] = field(default_factory=dict)
    all_player_stacks: List[PlayerStack] = field(default_factory=list)
    confidence: int = 0
    warnings: List[str] = field(default_factory=list)


# ============================================================================
# MATCHER TYPES
# ============================================================================

@dataclass
class HandMatch:
    """Match between a parsed hand and a screenshot"""
    hand_id: str
    screenshot_id: str
    confidence: float
    score_breakdown: Dict[str, float]
    auto_mapping: Optional[Dict[str, str]] = None


# ============================================================================
# WRITER TYPES
# ============================================================================

@dataclass
class NameMapping:
    """Mapping from anonymized ID to real player name"""
    anonymized_identifier: str
    resolved_name: str
    source: Literal['auto-match', 'manual', 'imported']
    confidence: Optional[float] = None
    locked: bool = False


@dataclass
class ValidationResult:
    """Result of TXT format validation"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
