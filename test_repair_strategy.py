"""
Test suite for repair_strategy.py
Following TDD approach: Write tests first (RED phase)
"""

import pytest
from repair_strategy import (
    RepairAction,
    RepairPlan,
    generate_repair_plan,
    topological_sort,
    determine_action_type,
    build_action_params
)
from error_analyzer import ErrorAnalysis
from error_parser import PTError


class TestRepairActionDataclass:
    """Test RepairAction dataclass structure"""

    def test_basic_repair_action_creation(self):
        """Test creating a basic RepairAction object"""
        action = RepairAction(
            error_id="SG123",
            action_type="remove_duplicate_mapping",
            affected_phase="matcher",
            confidence=0.95,
            auto_executable=True,
            action_params={"seat": 3, "player_name": "TuichAAreko"},
            gemini_suggested="Remove seat 3 mapping for TuichAAreko"
        )

        assert action.error_id == "SG123"
        assert action.action_type == "remove_duplicate_mapping"
        assert action.affected_phase == "matcher"
        assert action.confidence == 0.95
        assert action.auto_executable is True
        assert action.action_params["seat"] == 3


class TestRepairPlanDataclass:
    """Test RepairPlan dataclass structure"""

    def test_basic_repair_plan_creation(self):
        """Test creating a RepairPlan object"""
        actions = [
            RepairAction("SG123", "fix1", "matcher", 0.9, True, {}, "Fix 1"),
            RepairAction("SG124", "fix2", "parser", 0.85, True, {}, "Fix 2")
        ]

        plan = RepairPlan(
            actions=actions,
            execution_order=actions,
            total_errors=2,
            high_confidence_fixes=2,
            medium_confidence_fixes=0,
            low_confidence_fixes=0,
            estimated_success_rate=0.875
        )

        assert plan.total_errors == 2
        assert plan.high_confidence_fixes == 2
        assert plan.estimated_success_rate == 0.875
        assert len(plan.actions) == 2


class TestDetermineActionType:
    """Test action type determination from analysis"""

    def test_duplicate_player_action_type(self):
        """Test that duplicate_player errors map to remove_duplicate_mapping"""
        analysis = ErrorAnalysis(
            error_type="duplicate_player",
            root_cause="Duplicate mapping",
            affected_phase="matcher",
            confidence=0.95,
            suggested_fix="Remove duplicate",
            auto_fixable=True,
            fix_code="remove_duplicate_mapping"
        )

        action_type = determine_action_type(analysis)
        assert action_type == "remove_duplicate_mapping"

    def test_invalid_pot_action_type(self):
        """Test that invalid_pot errors map to recalculate_pot"""
        analysis = ErrorAnalysis(
            error_type="invalid_pot",
            root_cause="Cash Drop fee missing",
            affected_phase="parser",
            confidence=0.88,
            suggested_fix="Add fee",
            auto_fixable=True,
            fix_code="add_cash_drop_fee"
        )

        action_type = determine_action_type(analysis)
        assert action_type == "add_cash_drop_fee"

    def test_uses_fix_code_if_available(self):
        """Test that fix_code from analysis is used as action_type"""
        analysis = ErrorAnalysis(
            error_type="custom_error",
            root_cause="Something wrong",
            affected_phase="writer",
            confidence=0.7,
            suggested_fix="Fix it",
            auto_fixable=True,
            fix_code="custom_fix_action"
        )

        action_type = determine_action_type(analysis)
        assert action_type == "custom_fix_action"


class TestBuildActionParams:
    """Test building action parameters from analysis and error"""

    def test_build_params_for_duplicate_player(self):
        """Test building params for duplicate player error"""
        error = PTError(
            hand_id="SG123",
            error_type="duplicate_player",
            line_number=5,
            raw_message="Error...",
            player_name="TuichAAreko",
            seats_involved=[2, 3]
        )

        analysis = ErrorAnalysis(
            error_type="duplicate_player",
            root_cause="Duplicate",
            affected_phase="matcher",
            confidence=0.95,
            suggested_fix="Remove seat 3",
            auto_fixable=True
        )

        params = build_action_params(error, analysis)

        assert params["hand_id"] == "SG123"
        assert params["player_name"] == "TuichAAreko"
        assert params["seats_involved"] == [2, 3]

    def test_build_params_for_invalid_pot(self):
        """Test building params for invalid pot error"""
        error = PTError(
            hand_id="RC456",
            error_type="invalid_pot",
            line_number=10,
            raw_message="Error...",
            expected_pot=45.50,
            found_pot=44.00
        )

        analysis = ErrorAnalysis(
            error_type="invalid_pot",
            root_cause="Cash Drop",
            affected_phase="parser",
            confidence=0.88,
            suggested_fix="Add fee",
            auto_fixable=True
        )

        params = build_action_params(error, analysis)

        assert params["hand_id"] == "RC456"
        assert params["expected_pot"] == 45.50
        assert params["found_pot"] == 44.00
        assert params["pot_difference"] == 1.50


class TestTopologicalSort:
    """Test topological sorting of repair actions"""

    def test_sort_by_phase_priority(self):
        """Test that actions are sorted by phase priority"""
        actions = [
            RepairAction("SG1", "fix1", "writer", 0.9, True, {}, "Fix 1"),
            RepairAction("SG2", "fix2", "parser", 0.9, True, {}, "Fix 2"),
            RepairAction("SG3", "fix3", "matcher", 0.9, True, {}, "Fix 3"),
            RepairAction("SG4", "fix4", "ocr", 0.9, True, {}, "Fix 4")
        ]

        sorted_actions = topological_sort(actions)

        # Expected order: parser -> ocr -> matcher -> writer
        assert sorted_actions[0].affected_phase == "parser"
        assert sorted_actions[1].affected_phase == "ocr"
        assert sorted_actions[2].affected_phase == "matcher"
        assert sorted_actions[3].affected_phase == "writer"

    def test_sort_by_confidence_within_phase(self):
        """Test that higher confidence actions come first within same phase"""
        actions = [
            RepairAction("SG1", "fix1", "matcher", 0.7, True, {}, "Fix 1"),
            RepairAction("SG2", "fix2", "matcher", 0.95, True, {}, "Fix 2"),
            RepairAction("SG3", "fix3", "matcher", 0.85, True, {}, "Fix 3")
        ]

        sorted_actions = topological_sort(actions)

        # Should be sorted by confidence (descending) within matcher phase
        assert sorted_actions[0].confidence == 0.95
        assert sorted_actions[1].confidence == 0.85
        assert sorted_actions[2].confidence == 0.7


class TestGenerateRepairPlan:
    """Test generating complete repair plans"""

    def test_generate_plan_from_analyses(self):
        """Test generating repair plan from error analyses"""
        job_id = 1

        errors = {
            "file1.txt": [
                PTError("SG123", "duplicate_player", 5, "Error...", player_name="Alice", seats_involved=[1, 2]),
                PTError("RC456", "invalid_pot", 10, "Error...", expected_pot=45.5, found_pot=44.0)
            ]
        }

        analyses = {
            "SG123": ErrorAnalysis(
                error_type="duplicate_player",
                root_cause="Duplicate",
                affected_phase="matcher",
                confidence=0.95,
                suggested_fix="Remove duplicate",
                auto_fixable=True,
                fix_code="remove_duplicate_mapping"
            ),
            "RC456": ErrorAnalysis(
                error_type="invalid_pot",
                root_cause="Cash Drop",
                affected_phase="parser",
                confidence=0.88,
                suggested_fix="Add fee",
                auto_fixable=True,
                fix_code="add_cash_drop_fee"
            )
        }

        plan = generate_repair_plan(job_id, errors, analyses)

        assert plan.total_errors == 2
        assert len(plan.actions) == 2
        assert plan.high_confidence_fixes == 2
        assert plan.estimated_success_rate > 0.9

    def test_plan_calculates_confidence_metrics(self):
        """Test that plan correctly categorizes confidence levels"""
        errors = {
            "file1.txt": [
                PTError("SG1", "error1", 1, "E1"),
                PTError("SG2", "error2", 2, "E2"),
                PTError("SG3", "error3", 3, "E3"),
                PTError("SG4", "error4", 4, "E4")
            ]
        }

        analyses = {
            "SG1": ErrorAnalysis("error1", "cause", "matcher", 0.95, "fix", True, "fix1"),  # High
            "SG2": ErrorAnalysis("error2", "cause", "matcher", 0.85, "fix", True, "fix2"),  # High
            "SG3": ErrorAnalysis("error3", "cause", "parser", 0.65, "fix", True, "fix3"),   # Medium
            "SG4": ErrorAnalysis("error4", "cause", "writer", 0.45, "fix", False, "fix4")  # Low
        }

        plan = generate_repair_plan(1, errors, analyses)

        assert plan.high_confidence_fixes == 2  # >0.8
        assert plan.medium_confidence_fixes == 1  # 0.5-0.8
        assert plan.low_confidence_fixes == 1  # <0.5

    def test_plan_orders_actions_topologically(self):
        """Test that plan orders actions by phase dependencies"""
        errors = {
            "file1.txt": [
                PTError("SG1", "error1", 1, "E1"),
                PTError("SG2", "error2", 2, "E2"),
                PTError("SG3", "error3", 3, "E3")
            ]
        }

        analyses = {
            "SG1": ErrorAnalysis("error1", "cause", "writer", 0.9, "fix", True, "fix1"),
            "SG2": ErrorAnalysis("error2", "cause", "parser", 0.9, "fix", True, "fix2"),
            "SG3": ErrorAnalysis("error3", "cause", "matcher", 0.9, "fix", True, "fix3")
        }

        plan = generate_repair_plan(1, errors, analyses)

        # Should be ordered: parser -> matcher -> writer
        assert plan.execution_order[0].affected_phase == "parser"
        assert plan.execution_order[1].affected_phase == "matcher"
        assert plan.execution_order[2].affected_phase == "writer"

    def test_plan_calculates_success_rate(self):
        """Test that estimated success rate is average of confidences"""
        errors = {
            "file1.txt": [
                PTError("SG1", "error1", 1, "E1"),
                PTError("SG2", "error2", 2, "E2")
            ]
        }

        analyses = {
            "SG1": ErrorAnalysis("error1", "cause", "matcher", 0.9, "fix", True, "fix1"),
            "SG2": ErrorAnalysis("error2", "cause", "parser", 0.8, "fix", True, "fix2")
        }

        plan = generate_repair_plan(1, errors, analyses)

        # Average of 0.9 and 0.8 = 0.85
        assert abs(plan.estimated_success_rate - 0.85) < 0.001  # Floating point tolerance


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_errors_dict(self):
        """Test generating plan with no errors"""
        plan = generate_repair_plan(1, {}, {})

        assert plan.total_errors == 0
        assert len(plan.actions) == 0
        assert plan.estimated_success_rate == 0.0

    def test_mismatched_errors_and_analyses(self):
        """Test when errors and analyses don't match"""
        errors = {
            "file1.txt": [PTError("SG123", "error1", 1, "E1")]
        }
        analyses = {
            "SG999": ErrorAnalysis("error1", "cause", "matcher", 0.9, "fix", True, "fix1")
        }

        # Should only create actions for matching hand IDs
        plan = generate_repair_plan(1, errors, analyses)

        # No matching hand_id, so no actions created
        assert plan.total_errors == 0


class TestRepairActionSerialization:
    """Test serializing repair actions for API responses"""

    def test_repair_action_to_dict(self):
        """Test converting RepairAction to dictionary"""
        action = RepairAction(
            error_id="SG123",
            action_type="remove_duplicate_mapping",
            affected_phase="matcher",
            confidence=0.95,
            auto_executable=True,
            action_params={"seat": 3},
            gemini_suggested="Remove seat 3"
        )

        # RepairAction should be serializable (dataclass with asdict)
        from dataclasses import asdict
        action_dict = asdict(action)

        assert action_dict["error_id"] == "SG123"
        assert action_dict["confidence"] == 0.95


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
