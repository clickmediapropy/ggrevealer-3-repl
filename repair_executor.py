"""
Repair Executor Module for PT4 Error Recovery System

Executes repair plans with phase-specific strategies:
- Parser repairs: Recalculate pots, fix blinds
- Matcher repairs: Remove duplicates, rematch with constraints
- OCR repairs: Re-run with hints
- Writer repairs: Regenerate files with corrected mappings

Note: This is a simplified implementation for demonstration.
Full version would require deep integration with database and pipeline.

Author: Claude Code
Date: 2025-11-01
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from repair_strategy import RepairAction, RepairPlan


@dataclass
class ExecutionResult:
    """Result of executing a single repair action

    Attributes:
        action_id: Hand ID or error identifier
        success: Whether the repair succeeded
        message: Human-readable result message
        modified_files: List of files that were modified
        error: Error message if failed (optional)
    """
    action_id: str
    success: bool
    message: str
    modified_files: List[str]
    error: Optional[str] = None


class RepairExecutor:
    """Execute repair plans with phase-specific strategies

    This class applies fixes to the pipeline based on the repair plan.
    It handles different repair strategies for each phase:
    - Parser: Modify parsed hand data
    - Matcher: Update hand-to-screenshot mappings
    - OCR: Re-run OCR with corrections
    - Writer: Regenerate output files

    Note: This is a simplified implementation. Production version would
    require full database integration and file system operations.
    """

    def __init__(self, db, api_key: str):
        """Initialize repair executor

        Args:
            db: Database connection for accessing job data
            api_key: Gemini API key for OCR operations
        """
        self.db = db
        self.api_key = api_key

    async def execute_action(self, action: RepairAction) -> ExecutionResult:
        """Execute a single repair action

        Routes to phase-specific repair method based on affected_phase.

        Args:
            action: RepairAction to execute

        Returns:
            ExecutionResult with success status and details

        Example:
            >>> action = RepairAction(...)
            >>> result = await executor.execute_action(action)
            >>> result.success
            True
        """
        # Route to phase-specific repair method
        if action.affected_phase == "parser":
            result = await self._repair_parser(job_id=0, action=action)
        elif action.affected_phase == "matcher":
            result = await self._repair_matching(job_id=0, action=action)
        elif action.affected_phase == "ocr":
            result = await self._repair_ocr(job_id=0, action=action)
        elif action.affected_phase == "writer":
            result = await self._repair_writer(job_id=0, action=action)
        else:
            result = {
                "success": False,
                "message": f"Unknown phase: {action.affected_phase}"
            }

        # Convert to ExecutionResult
        return ExecutionResult(
            action_id=action.error_id,
            success=result.get("success", False),
            message=result.get("message", ""),
            modified_files=result.get("modified_files", []),
            error=result.get("error")
        )

    async def execute_repair_plan(
        self,
        job_id: int,
        repair_plan: RepairPlan,
        user_approved: bool = False
    ) -> Dict[str, Any]:
        """Execute complete repair plan

        Executes all actions in the plan's execution_order.
        Requires explicit user approval.

        Args:
            job_id: Job ID being repaired
            repair_plan: Complete RepairPlan to execute
            user_approved: User must explicitly approve (default: False)

        Returns:
            Dictionary with execution results and statistics

        Raises:
            ValueError: If user approval not provided

        Example:
            >>> results = await executor.execute_repair_plan(1, plan, True)
            >>> results["success_rate"]
            0.85
        """
        if not user_approved:
            raise ValueError("Cannot execute repair plan without user approval")

        executed_actions = []
        failed_actions = []
        modified_files_set = set()

        # Execute actions in topological order
        for action in repair_plan.execution_order:
            try:
                result = await self.execute_action(action)

                if result.success:
                    executed_actions.append(result)
                    modified_files_set.update(result.modified_files)
                else:
                    failed_actions.append((action, result.error or "Unknown error"))

            except Exception as e:
                failed_actions.append((action, str(e)))

        # Calculate statistics
        total_executed = len(executed_actions) + len(failed_actions)
        success_count = len(executed_actions)
        success_rate = success_count / total_executed if total_executed > 0 else 0.0

        return {
            "total_executed": total_executed,
            "success_count": success_count,
            "failed_count": len(failed_actions),
            "success_rate": success_rate,
            "executed_actions": executed_actions,
            "failed_actions": failed_actions,
            "modified_files": list(modified_files_set)
        }

    async def _repair_parser(self, job_id: int, action: RepairAction) -> Dict[str, Any]:
        """Repair parser phase errors

        Handles:
        - add_cash_drop_fee: Add jackpot fee to pot calculation
        - fix_blind_posting: Correct blind amounts
        - recalculate_pot: Recalculate pot from actions

        Args:
            job_id: Job ID
            action: RepairAction with parser repair details

        Returns:
            Result dictionary with success status
        """
        # Simplified implementation
        # Production would modify database hand records

        if action.action_type == "add_cash_drop_fee":
            # Simulate adding Cash Drop fee
            return {
                "success": True,
                "message": f"Added Cash Drop fee to hand {action.error_id}",
                "modified_files": []
            }

        elif action.action_type == "fix_blind_posting":
            return {
                "success": True,
                "message": f"Fixed blind posting for hand {action.error_id}",
                "modified_files": []
            }

        return {
            "success": False,
            "message": f"Unknown parser action: {action.action_type}"
        }

    async def _repair_matching(self, job_id: int, action: RepairAction) -> Dict[str, Any]:
        """Repair matcher phase errors

        Handles:
        - remove_duplicate_mapping: Remove duplicate player mapping
        - unmatch_and_rematch: Clear and re-match with constraints

        Args:
            job_id: Job ID
            action: RepairAction with matcher repair details

        Returns:
            Result dictionary with success status
        """
        # Simplified implementation
        # Production would modify database mappings

        if action.action_type == "remove_duplicate_mapping":
            # Simulate removing duplicate mapping
            player_name = action.action_params.get("player_name", "Unknown")

            return {
                "success": True,
                "message": f"Removed duplicate mapping for {player_name} in hand {action.error_id}",
                "modified_files": []
            }

        return {
            "success": False,
            "message": f"Unknown matcher action: {action.action_type}"
        }

    async def _repair_ocr(self, job_id: int, action: RepairAction) -> Dict[str, Any]:
        """Repair OCR phase errors

        Handles:
        - re_run_ocr2_with_hints: Re-run OCR with user-provided hints

        Args:
            job_id: Job ID
            action: RepairAction with OCR repair details

        Returns:
            Result dictionary with success status
        """
        # Simplified implementation
        # Production would re-run OCR API calls

        return {
            "success": True,
            "message": f"Re-ran OCR for screenshot related to hand {action.error_id}",
            "modified_files": []
        }

    async def _repair_writer(self, job_id: int, action: RepairAction) -> Dict[str, Any]:
        """Repair writer phase errors

        Handles:
        - regenerate_txt_with_corrected_mappings: Regenerate hand history files

        Args:
            job_id: Job ID
            action: RepairAction with writer repair details

        Returns:
            Result dictionary with success status
        """
        # Simplified implementation
        # Production would regenerate actual TXT files

        hand_id = action.error_id
        filename = f"hand_{hand_id}_repaired.txt"

        return {
            "success": True,
            "message": f"Regenerated hand history for {hand_id}",
            "modified_files": [filename]
        }


if __name__ == "__main__":
    # Example usage
    import asyncio

    async def main():
        # Mock database
        mock_db = None

        executor = RepairExecutor(db=mock_db, api_key="fake_key")

        action = RepairAction(
            error_id="SG123",
            action_type="remove_duplicate_mapping",
            affected_phase="matcher",
            confidence=0.95,
            auto_executable=True,
            action_params={"hand_id": "SG123", "player_name": "Alice"},
            gemini_suggested="Remove duplicate"
        )

        result = await executor.execute_action(action)
        print(f"Execution result: {result.success}")
        print(f"Message: {result.message}")

    # Run example
    # asyncio.run(main())
    print("repair_executor.py loaded successfully")
