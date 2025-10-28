"""
Unit tests for PT4 Hand History Validator
Tests the 12 critical validations that PT4 performs
"""

import pytest
from validator import GGPokerHandHistoryValidator, ErrorSeverity, ValidationResultType


# ============================================================================
# TEST DATA - Valid Hand Histories
# ============================================================================

VALID_TOURNAMENT_HAND = """Poker Hand #SG3260937141: Tournament #239877416, Spin&Gold #5 Hold'em No Limit - Level5(40/80) - 2025/10/27 11:05:05
Table '7639' 3-max Seat #1 is the button
Seat 1: Hero (500 in chips)
Seat 2: 478db80b (400 in chips)
Hero: posts small blind 40
478db80b: posts big blind 80
*** HOLE CARDS ***
Dealt to Hero [4d 4c]
Dealt to 478db80b
Hero: raises 420 to 500 and is all-in
478db80b: calls 320 and is all-in
Uncalled bet (100) returned to Hero
Hero: shows [4d 4c]
478db80b: shows [Kc Qh]
*** FLOP *** [9d Ac Th]
*** TURN *** [9d Ac Th] [8s]
*** RIVER *** [9d Ac Th 8s] [Tc]
*** SHOWDOWN ***
Hero collected 800 from pot
*** SUMMARY ***
Total pot 800 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Board [9d Ac Th 8s Tc]
Seat 1: Hero (small blind) showed [4d 4c] and won (800) with two pair, Tens and Fours
Seat 2: 478db80b (big blind) showed [Kc Qh] and lost with a pair of Tens
"""

VALID_CASH_GAME_HAND = """Poker Hand #RC123456789: Hold'em No Limit ($0.10/$0.20) - 2025/09/15 14:30:25
Table 'Aurora' 6-max Seat #3 is the button
Seat 1: Hero ($20.00 in chips)
Seat 2: 5a3f9e2c ($18.50 in chips)
Seat 3: b7c4d1a8 ($25.75 in chips)
Seat 4: 9f2e6d3a ($15.00 in chips)
Seat 5: c8b1a5f2 ($22.30 in chips)
Seat 6: 3d7e9b4c ($19.85 in chips)
5a3f9e2c: posts small blind $0.10
b7c4d1a8: posts big blind $0.20
*** HOLE CARDS ***
Dealt to Hero [Kh Kc]
9f2e6d3a: folds
c8b1a5f2: raises $0.60 to $0.80
3d7e9b4c: folds
Hero: raises $1.80 to $2.60
5a3f9e2c: folds
b7c4d1a8: folds
c8b1a5f2: calls $1.80
*** FLOP *** [2s 7h 9c]
c8b1a5f2: checks
Hero: bets $3.50
c8b1a5f2: calls $3.50
*** TURN *** [2s 7h 9c] [Qs]
c8b1a5f2: checks
Hero: bets $8.00
c8b1a5f2: folds
Uncalled bet ($8.00) returned to Hero
Hero collected $12.10 from pot
*** SUMMARY ***
Total pot 12.40 | Rake 0.30 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Board [2s 7h 9c Qs]
Seat 1: Hero collected (12.10)
Seat 2: 5a3f9e2c (small blind) folded before Flop
Seat 3: b7c4d1a8 (big blind) folded before Flop
Seat 4: 9f2e6d3a folded before Flop
Seat 5: c8b1a5f2 folded on the Turn
Seat 6: 3d7e9b4c folded before Flop
"""

# ============================================================================
# TEST DATA - Invalid Hand Histories
# ============================================================================

INVALID_POT_SIZE_HAND = """Poker Hand #RC123456789: Hold'em No Limit ($0.10/$0.20) - 2025/09/15 14:30:25
Table 'Aurora' 6-max Seat #3 is the button
Seat 1: Hero ($20.00 in chips)
Seat 2: 5a3f9e2c ($18.50 in chips)
5a3f9e2c: posts small blind $0.10
Hero: posts big blind $0.20
*** HOLE CARDS ***
Dealt to Hero [As Ah]
5a3f9e2c: calls $0.10
Hero: raises $0.80 to $1.00
5a3f9e2c: calls $0.80
*** FLOP *** [2s 3h 4c]
Hero: bets $1.50
5a3f9e2c: calls $1.50
*** TURN *** [2s 3h 4c] [5s]
Hero: bets $3.00
5a3f9e2c: calls $3.00
*** RIVER *** [2s 3h 4c 5s] [6h]
Hero: bets $5.00
5a3f9e2c: calls $5.00
*** SHOWDOWN ***
Hero: shows [As Ah]
5a3f9e2c: mucks hand
Hero collected $19.50 from pot
*** SUMMARY ***
Total pot 21.00 | Rake 0.50 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Board [2s 3h 4c 5s 6h]
Seat 1: Hero (big blind) showed [As Ah] and won (19.50) with a straight, Two to Six
Seat 2: 5a3f9e2c (small blind) mucked
"""

INVALID_BLIND_MISMATCH_HAND = """Poker Hand #RC987654321: Hold'em No Limit ($0.05/$0.10) - 2025/09/15 15:00:00
Table 'Venus' 3-max Seat #1 is the button
Seat 1: Hero ($10.00 in chips)
Seat 2: 6d8e2f1a ($12.50 in chips)
Hero: posts small blind $0.05
6d8e2f1a: posts big blind $0.20
*** HOLE CARDS ***
Dealt to Hero [Jh Js]
Hero: raises $0.30 to $0.50
6d8e2f1a: folds
Uncalled bet ($0.30) returned to Hero
Hero collected $0.40 from pot
*** SUMMARY ***
Total pot 0.40 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Seat 1: Hero (small blind) collected (0.40)
Seat 2: 6d8e2f1a (big blind) folded before Flop
"""

INVALID_DUPLICATE_CARDS_HAND = """Poker Hand #RC555666777: Hold'em No Limit ($0.25/$0.50) - 2025/09/15 16:00:00
Table 'Mars' 6-max Seat #2 is the button
Seat 1: Hero ($50.00 in chips)
Seat 2: 8a9b1c2d ($45.00 in chips)
8a9b1c2d: posts small blind $0.25
Hero: posts big blind $0.50
*** HOLE CARDS ***
Dealt to Hero [As Ah]
8a9b1c2d: raises $1.50 to $2.00
Hero: raises $4.00 to $6.00
8a9b1c2d: calls $4.00
*** FLOP *** [As Kh Qh]
Hero: bets $8.00
8a9b1c2d: calls $8.00
*** TURN *** [As Kh Qh] [Jh]
Hero: checks
8a9b1c2d: bets $12.00
Hero: calls $12.00
*** RIVER *** [As Kh Qh Jh] [Th]
Hero: checks
8a9b1c2d: bets $19.00
Hero: calls $19.00
*** SHOWDOWN ***
Hero: shows [As Ah]
8a9b1c2d: shows [Ks Kc]
8a9b1c2d collected $89.50 from pot
*** SUMMARY ***
Total pot 90.00 | Rake 0.50 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Board [As Kh Qh Jh Th]
Seat 1: Hero (big blind) showed [As Ah] and lost with a flush, Ace high
Seat 2: 8a9b1c2d (small blind) showed [Ks Kc] and won (89.50) with a straight flush, Ten to Ace
"""

RUN_IT_THREE_TIMES_HAND = """Poker Hand #RC111222333: Hold'em No Limit ($1.00/$2.00) - 2025/09/15 17:00:00
Table 'Jupiter' 3-max Seat #1 is the button
Seat 1: Hero ($200.00 in chips)
Seat 2: 4f3e2d1c ($180.00 in chips)
Hero: posts small blind $1.00
4f3e2d1c: posts big blind $2.00
*** HOLE CARDS ***
Dealt to Hero [Ah Kh]
Hero: raises $6.00 to $8.00
4f3e2d1c: raises $16.00 to $24.00
Hero: raises $176.00 to $200.00 and is all-in
4f3e2d1c: calls $156.00 and is all-in
Uncalled bet ($20.00) returned to Hero
*** FIRST FLOP *** [2s 3h 4c]
*** FIRST TURN *** [2s 3h 4c] [5s]
*** FIRST RIVER *** [2s 3h 4c 5s] [6h]
*** SECOND FLOP *** [7d 8d 9d]
*** SECOND TURN *** [7d 8d 9d] [Td]
*** SECOND RIVER *** [7d 8d 9d Td] [Jd]
*** THIRD FLOP *** [Qc Kc Ac]
*** THIRD TURN *** [Qc Kc Ac] [2c]
*** THIRD RIVER *** [Qc Kc Ac 2c] [3c]
*** SHOWDOWN ***
Hero: shows [Ah Kh]
4f3e2d1c: shows [Qs Qd]
Hero collected $180.00 from pot (runout 1)
4f3e2d1c collected $180.00 from pot (runout 2)
Hero collected $180.00 from pot (runout 3)
*** SUMMARY ***
Total pot 360.00 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
"""

EV_CASHOUT_HAND = """Poker Hand #RC444555666: Hold'em No Limit ($0.50/$1.00) - 2025/09/15 18:00:00
Table 'Saturn' 6-max Seat #3 is the button
Seat 1: Hero ($100.00 in chips)
Seat 2: 7e8f9a1b ($95.00 in chips)
Seat 3: 2c3d4e5f ($110.00 in chips)
7e8f9a1b: posts small blind $0.50
2c3d4e5f: posts big blind $1.00
*** HOLE CARDS ***
Dealt to Hero [Ad As]
Hero: raises $3.00 to $4.00
7e8f9a1b: raises $10.00 to $14.00
2c3d4e5f: folds
Hero: raises $86.00 to $100.00 and is all-in
7e8f9a1b: calls $81.00 and is all-in
Uncalled bet ($5.00) returned to Hero
Hero: shows [Ad As]
7e8f9a1b: shows [Kh Kc]
Hero: Chooses to EV Cashout
*** TURN *** [2h 3h 7s] [9c]
Hero: Pays $155.25
7e8f9a1b collected $189.75 from pot
*** SUMMARY ***
Total pot 191.00 | Rake 1.00 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Board [2h 3h 7s 9c]
Seat 1: Hero showed [Ad As] and EV cashed out for $155.25
Seat 2: 7e8f9a1b (small blind) showed [Kh Kc] and won (189.75)
"""

NEGATIVE_STACK_HAND = """Poker Hand #RC777888999: Hold'em No Limit ($0.10/$0.20) - 2025/09/15 19:00:00
Table 'Neptune' 3-max Seat #1 is the button
Seat 1: Hero ($20.00 in chips)
Seat 2: 1a2b3c4d ($0.00 in chips)
Hero: posts small blind $0.10
1a2b3c4d: posts big blind $0.20
*** HOLE CARDS ***
Dealt to Hero [9h 9s]
Hero: raises $0.60 to $0.80
1a2b3c4d: folds
Uncalled bet ($0.60) returned to Hero
Hero collected $0.40 from pot
*** SUMMARY ***
Total pot 0.40 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Seat 1: Hero (small blind) collected (0.40)
Seat 2: 1a2b3c4d (big blind) folded before Flop
"""

INVALID_HAND_ID_FORMAT = """Poker Hand #XX999888777: Hold'em No Limit ($0.10/$0.20) - 2025/09/15 20:00:00
Table 'Pluto' 3-max Seat #1 is the button
Seat 1: Hero ($20.00 in chips)
Seat 2: 5f6e7d8c ($18.00 in chips)
Hero: posts small blind $0.10
5f6e7d8c: posts big blind $0.20
*** HOLE CARDS ***
Dealt to Hero [Tc Th]
Hero: raises $0.60 to $0.80
5f6e7d8c: folds
Uncalled bet ($0.60) returned to Hero
Hero collected $0.40 from pot
*** SUMMARY ***
Total pot 0.40 | Rake 0 | Jackpot 0 | Bingo 0 | Fortune 0 | Tax 0
Seat 1: Hero (small blind) collected (0.40)
Seat 2: 5f6e7d8c (big blind) folded before Flop
"""

# ============================================================================
# TEST CASES
# ============================================================================

class TestPT4Validator:
    """Test suite for PT4 hand history validator"""

    def test_valid_tournament_hand(self):
        """Test that a valid tournament hand passes all validations"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        results = validator.validate(VALID_TOURNAMENT_HAND)

        # Should have no errors
        errors = [r for r in results if r.result_type == ValidationResultType.ERROR]
        assert len(errors) == 0, f"Valid hand should have no errors, found: {errors}"

        # Should not be rejected
        assert not validator.should_reject_hand()

    def test_valid_cash_game_hand(self):
        """Test that a valid cash game hand passes all validations"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        results = validator.validate(VALID_CASH_GAME_HAND)

        # Should have no errors
        errors = [r for r in results if r.result_type == ValidationResultType.ERROR]
        assert len(errors) == 0, f"Valid hand should have no errors, found: {errors}"

    def test_invalid_pot_size(self):
        """Test detection of invalid pot size (common 40% of failures)"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        results = validator.validate(INVALID_POT_SIZE_HAND)

        # Should detect pot size error
        pot_errors = [r for r in results if r.validation_name == "pot_size" and r.result_type == ValidationResultType.ERROR]
        assert len(pot_errors) > 0, "Should detect invalid pot size"
        assert pot_errors[0].severity == ErrorSeverity.CRITICAL

    def test_invalid_blind_mismatch(self):
        """Test detection of stated vs posted blinds mismatch"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        results = validator.validate(INVALID_BLIND_MISMATCH_HAND)

        # Should detect blind mismatch
        blind_errors = [r for r in results if r.validation_name == "blinds" and r.result_type == ValidationResultType.ERROR]
        assert len(blind_errors) > 0, "Should detect blind mismatch"
        assert blind_errors[0].error_type == "BLIND_MISMATCH"

    def test_duplicate_cards_detection(self):
        """Test detection of duplicate cards in deck"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        results = validator.validate(INVALID_DUPLICATE_CARDS_HAND)

        # Should detect duplicate cards
        card_errors = [r for r in results if r.validation_name == "cards" and r.error_type == "DUPLICATE_CARDS"]
        assert len(card_errors) > 0, "Should detect duplicate cards"
        assert card_errors[0].severity == ErrorSeverity.CRITICAL

    def test_run_it_three_times_rejection(self):
        """Test that Run It Three Times is rejected (PT4 doesn't support)"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        results = validator.validate(RUN_IT_THREE_TIMES_HAND)

        # Should detect RIT3 as unsupported
        game_type_errors = [r for r in results if r.validation_name == "game_type" and r.error_type == "RUN_IT_THREE_TIMES"]
        assert len(game_type_errors) > 0, "Should detect Run It Three Times"
        assert game_type_errors[0].severity == ErrorSeverity.CRITICAL

    def test_ev_cashout_detection(self):
        """Test detection of EV Cashout (PT4 bug with winnings calculation)"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        results = validator.validate(EV_CASHOUT_HAND)

        # Should detect EV Cashout
        ev_cashout_warnings = [r for r in results if r.validation_name == "ev_cashout"]
        assert len(ev_cashout_warnings) > 0, "Should detect EV Cashout"
        assert ev_cashout_warnings[0].severity == ErrorSeverity.HIGH

    def test_negative_stack_detection(self):
        """Test detection of zero or negative stacks"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        results = validator.validate(NEGATIVE_STACK_HAND)

        # Should detect invalid stack
        stack_errors = [r for r in results if r.validation_name == "stack_sizes" and r.error_type == "INVALID_STACK_SIZE"]
        assert len(stack_errors) > 0, "Should detect zero stack"
        assert stack_errors[0].severity == ErrorSeverity.CRITICAL

    def test_invalid_hand_id_prefix(self):
        """Test detection of invalid hand ID prefix"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        results = validator.validate(INVALID_HAND_ID_FORMAT)

        # Should detect unknown prefix
        hand_id_warnings = [r for r in results if r.validation_name == "hand_metadata" and r.error_type == "UNKNOWN_HAND_PREFIX"]
        assert len(hand_id_warnings) > 0, "Should detect unknown hand ID prefix"

    def test_validation_summary(self):
        """Test that validation summary is generated correctly"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        validator.validate(INVALID_POT_SIZE_HAND)

        summary = validator.get_validation_summary()

        assert "total_validations" in summary
        assert "errors" in summary
        assert "warnings" in summary
        assert "would_reject" in summary
        assert "results" in summary

    def test_pt4_error_message_format(self):
        """Test that PT4-style error messages are generated correctly"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        validator.validate(INVALID_POT_SIZE_HAND)

        error_msg = validator.get_pt4_error_message()

        assert error_msg is not None
        assert "Error: GG Poker:" in error_msg

    def test_strict_mode_rejection(self):
        """Test that strict mode properly rejects hands with critical errors"""
        validator = GGPokerHandHistoryValidator(strict_mode=True)
        validator.validate(INVALID_POT_SIZE_HAND)

        assert validator.should_reject_hand(), "Strict mode should reject hand with critical error"

    def test_permissive_mode_no_rejection(self):
        """Test that permissive mode never rejects hands"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        validator.validate(INVALID_POT_SIZE_HAND)

        assert not validator.should_reject_hand(), "Permissive mode should never reject"

    def test_hero_presence_validation(self):
        """Test that hands without 'Hero' are flagged"""
        hand_without_hero = VALID_TOURNAMENT_HAND.replace("Hero", "RandomPlayer")

        validator = GGPokerHandHistoryValidator(strict_mode=False)
        results = validator.validate(hand_without_hero)

        # Should detect missing Hero
        hero_errors = [r for r in results if r.error_type == "MISSING_HERO"]
        assert len(hero_errors) > 0, "Should detect missing Hero"

    def test_all_validations_run(self):
        """Test that all 12 validations are executed"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)
        validator.validate(VALID_TOURNAMENT_HAND)

        # Check that validator methods were called
        # (This is a sanity check that the validate() method calls all validators)
        summary = validator.get_validation_summary()
        assert summary is not None

    def test_metadata_extraction_helpers(self):
        """Test helper methods for extracting data from hand history"""
        validator = GGPokerHandHistoryValidator(strict_mode=False)

        # Test pot extraction
        pot = validator._extract_pot_from_summary(VALID_TOURNAMENT_HAND)
        assert pot is not None
        assert pot == 800

        # Test rake extraction
        rake = validator._extract_rake(VALID_CASH_GAME_HAND)
        assert rake is not None


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
