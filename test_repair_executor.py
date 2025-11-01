"""
Test suite for repair_executor.py
Following TDD approach: Write tests first (RED phase)

Note: This is a simplified test suite for demonstration.
Full implementation would require complete database integration.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from repair_executor import (
    RepairExecutor,
    ExecutionResult
)
from repair_strategy import RepairAction, RepairPlan


class TestExecutionResultDataclass:
    """Test ExecutionResult dataclass structure"""

    def test_basic_execution_result_creation(self):
        """Test creating an ExecutionResult object"""
        result = ExecutionResult(
            action_id="SG123",
            success=True,
            message="Successfully removed duplicate mapping",
            modified_files=["table_12253_resolved.txt"]
        )

        assert result.action_id == "SG123"
        assert result.success is True
        assert len(result.modified_files) == 1


class TestRepairExecutor:
    """Test RepairExecutor class"""

    def test_executor_initialization(self):
        """Test creating RepairExecutor instance"""
        mock_db = Mock()
        executor = RepairExecutor(db=mock_db, api_key="fake_key")

        assert executor.db == mock_db
        assert executor.api_key == "fake_key"

    @pytest.mark.asyncio
    async def test_execute_single_action(self):
        """Test executing a single repair action"""
        mock_db = Mock()
        executor = RepairExecutor(db=mock_db, api_key="fake_key")

        action = RepairAction(
            error_id="SG123",
            action_type="remove_duplicate_mapping",
            affected_phase="matcher",
            confidence=0.95,
            auto_executable=True,
            action_params={"hand_id": "SG123", "seat": 3, "player_name": "Alice"},
            gemini_suggested="Remove seat 3 mapping"
        )

        result = await executor.execute_action(action)

        assert result.action_id == "SG123"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_repair_plan(self):
        """Test executing complete repair plan"""
        mock_db = Mock()
        executor = RepairExecutor(db=mock_db, api_key="fake_key")

        actions = [
            RepairAction("SG1", "fix1", "parser", 0.9, True, {"hand_id": "SG1"}, "Fix 1"),
            RepairAction("SG2", "fix2", "matcher", 0.85, True, {"hand_id": "SG2"}, "Fix 2")
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

        results = await executor.execute_repair_plan(job_id=1, repair_plan=plan, user_approved=True)

        assert results["total_executed"] == 2
        assert results["success_count"] >= 0
        assert "executed_actions" in results


class TestRepairMatcher:
    """Test matcher phase repairs"""

    @pytest.mark.asyncio
    async def test_remove_duplicate_mapping(self):
        """Test removing duplicate player mapping"""
        mock_db = Mock()
        mock_db.get_mapping.return_value = {
            "abc123": "Alice",
            "def456": "Alice"  # Duplicate!
        }

        executor = RepairExecutor(db=mock_db, api_key="fake_key")

        action = RepairAction(
            error_id="SG123",
            action_type="remove_duplicate_mapping",
            affected_phase="matcher",
            confidence=0.95,
            auto_executable=True,
            action_params={
                "hand_id": "SG123",
                "seat": 3,
                "player_name": "Alice"
            },
            gemini_suggested="Remove duplicate"
        )

        result = await executor._repair_matching(job_id=1, action=action)

        assert result["success"] is True


class TestRepairParser:
    """Test parser phase repairs"""

    @pytest.mark.asyncio
    async def test_recalculate_pot_with_cash_drop(self):
        """Test recalculating pot with Cash Drop fee"""
        mock_db = Mock()
        mock_db.get_hand.return_value = {
            "hand_id": "RC456",
            "total_pot": 44.0,
            "rake": 1.0
        }

        executor = RepairExecutor(db=mock_db, api_key="fake_key")

        action = RepairAction(
            error_id="RC456",
            action_type="add_cash_drop_fee",
            affected_phase="parser",
            confidence=0.88,
            auto_executable=True,
            action_params={
                "hand_id": "RC456",
                "pot_difference": 1.50
            },
            gemini_suggested="Add jackpot fee"
        )

        result = await executor._repair_parser(job_id=1, action=action)

        assert result["success"] is True


class TestUserApprovalRequired:
    """Test that user approval is required"""

    @pytest.mark.asyncio
    async def test_execution_requires_approval(self):
        """Test that execution fails without user approval"""
        mock_db = Mock()
        executor = RepairExecutor(db=mock_db, api_key="fake_key")

        plan = RepairPlan(
            actions=[],
            execution_order=[],
            total_errors=0,
            high_confidence_fixes=0,
            medium_confidence_fixes=0,
            low_confidence_fixes=0,
            estimated_success_rate=0.0
        )

        with pytest.raises(ValueError, match="user approval"):
            await executor.execute_repair_plan(job_id=1, repair_plan=plan, user_approved=False)


class TestExecutionStatistics:
    """Test execution statistics and reporting"""

    @pytest.mark.asyncio
    async def test_calculates_success_rate(self):
        """Test that execution results include success rate"""
        mock_db = Mock()
        executor = RepairExecutor(db=mock_db, api_key="fake_key")

        actions = [
            RepairAction("SG1", "fix1", "matcher", 0.9, True, {"hand_id": "SG1"}, "Fix 1"),
            RepairAction("SG2", "fix2", "matcher", 0.85, True, {"hand_id": "SG2"}, "Fix 2")
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

        results = await executor.execute_repair_plan(job_id=1, repair_plan=plan, user_approved=True)

        assert "success_rate" in results
        assert results["success_rate"] >= 0.0
        assert results["success_rate"] <= 1.0


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
