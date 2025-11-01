"""
Repair Strategy Module for PT4 Error Recovery System

Generates executable repair plans from error analyses:
- Converts ErrorAnalysis objects to RepairAction objects
- Orders actions by dependencies (topological sort)
- Calculates confidence metrics
- Estimates success rate

Author: Claude Code
Date: 2025-11-01
"""

from dataclasses import dataclass
from typing import List, Dict, Any
from error_analyzer import ErrorAnalysis
from error_parser import PTError


@dataclass
class RepairAction:
    """Single action to fix a PT4 error

    Attributes:
        error_id: Hand ID or error identifier (e.g., "SG3247401164")
        action_type: Type of repair action (e.g., "remove_duplicate_mapping")
        affected_phase: Which pipeline phase to repair (parser/matcher/ocr/writer)
        confidence: Confidence in this fix (0.0-1.0)
        auto_executable: Whether system can automatically execute this
        action_params: Dictionary of parameters for the repair executor
        gemini_suggested: Human-readable description from Gemini
    """
    error_id: str
    action_type: str
    affected_phase: str
    confidence: float
    auto_executable: bool
    action_params: Dict[str, Any]
    gemini_suggested: str


@dataclass
class RepairPlan:
    """Complete repair strategy for all errors

    Attributes:
        actions: List of all RepairAction objects
        execution_order: Actions sorted by dependencies (topological order)
        total_errors: Total number of errors to fix
        high_confidence_fixes: Count of fixes with confidence > 0.8
        medium_confidence_fixes: Count of fixes with confidence 0.5-0.8
        low_confidence_fixes: Count of fixes with confidence < 0.5
        estimated_success_rate: Average confidence across all fixes
    """
    actions: List[RepairAction]
    execution_order: List[RepairAction]
    total_errors: int
    high_confidence_fixes: int
    medium_confidence_fixes: int
    low_confidence_fixes: int
    estimated_success_rate: float


def determine_action_type(analysis: ErrorAnalysis) -> str:
    """Determine the action type from error analysis

    Uses fix_code from Gemini if available, otherwise maps error_type to action.

    Args:
        analysis: ErrorAnalysis object from Gemini

    Returns:
        Action type string (e.g., "remove_duplicate_mapping")

    Example:
        >>> analysis = ErrorAnalysis(..., fix_code="remove_duplicate_mapping")
        >>> determine_action_type(analysis)
        'remove_duplicate_mapping'
    """
    # Use fix_code from Gemini if available
    if analysis.fix_code:
        return analysis.fix_code

    # Fallback: map error_type to action_type
    error_to_action_map = {
        "duplicate_player": "remove_duplicate_mapping",
        "invalid_pot": "recalculate_pot",
        "unmapped_id": "manual_review_required",
        "missing_blind": "fix_blind_posting",
        "invalid_stack": "recalculate_stack"
    }

    return error_to_action_map.get(analysis.error_type, "unknown_action")


def build_action_params(error: PTError, analysis: ErrorAnalysis) -> Dict[str, Any]:
    """Build action parameters from error and analysis

    Extracts relevant fields from PTError for the repair executor.

    Args:
        error: PTError object with error details
        analysis: ErrorAnalysis object from Gemini

    Returns:
        Dictionary of parameters for repair execution

    Example:
        >>> error = PTError(hand_id="SG123", player_name="Alice", ...)
        >>> params = build_action_params(error, analysis)
        >>> params["hand_id"]
        'SG123'
    """
    params = {
        "hand_id": error.hand_id,
        "error_type": error.error_type,
        "line_number": error.line_number
    }

    # Add error-specific parameters
    if error.error_type == "duplicate_player":
        params["player_name"] = error.player_name
        params["seats_involved"] = error.seats_involved

    elif error.error_type == "invalid_pot":
        params["expected_pot"] = error.expected_pot
        params["found_pot"] = error.found_pot
        params["pot_difference"] = error.expected_pot - error.found_pot

    elif error.error_type == "unmapped_id":
        params["unmapped_id"] = error.unmapped_id
        params["filename"] = error.filename

    return params


def topological_sort(actions: List[RepairAction]) -> List[RepairAction]:
    """Order actions by dependencies (phase priority + confidence)

    Pipeline phases must be executed in order:
    1. parser (recalculate pots, fix blinds)
    2. ocr (re-run OCR if needed)
    3. matcher (re-match hands to screenshots)
    4. writer (regenerate output files)

    Within each phase, higher confidence actions are executed first.

    Args:
        actions: List of RepairAction objects

    Returns:
        List of actions sorted by execution order

    Example:
        >>> actions = [writer_action, parser_action, matcher_action]
        >>> sorted_actions = topological_sort(actions)
        >>> [a.affected_phase for a in sorted_actions]
        ['parser', 'matcher', 'writer']
    """
    # Phase priority order (earlier phases must complete first)
    phase_priority = {
        "parser": 0,
        "ocr": 1,
        "matcher": 2,
        "writer": 3
    }

    # Sort by: 1) phase priority, 2) confidence (descending)
    return sorted(actions, key=lambda a: (
        phase_priority.get(a.affected_phase, 99),  # Phase first
        -a.confidence  # Higher confidence first within same phase
    ))


def generate_repair_plan(
    job_id: int,
    errors: Dict[str, List[PTError]],
    analyses: Dict[str, ErrorAnalysis]
) -> RepairPlan:
    """Generate executable repair plan from error analyses

    Creates RepairAction objects from analyses, orders them by dependencies,
    and calculates confidence metrics.

    Args:
        job_id: Job ID being repaired
        errors: Dictionary mapping filename → list of PTError objects
        analyses: Dictionary mapping hand_id → ErrorAnalysis

    Returns:
        Complete RepairPlan with ordered actions and metrics

    Example:
        >>> errors = {"file1.txt": [PTError(...)]}
        >>> analyses = {"SG123": ErrorAnalysis(...)}
        >>> plan = generate_repair_plan(1, errors, analyses)
        >>> plan.total_errors
        1
    """
    # Flatten errors into a dictionary by hand_id
    errors_by_hand_id = {}
    for filename, error_list in errors.items():
        for error in error_list:
            errors_by_hand_id[error.hand_id] = error

    # Create RepairActions for each analyzed error
    actions = []

    for hand_id, analysis in analyses.items():
        # Only create action if we have the corresponding error
        if hand_id not in errors_by_hand_id:
            continue

        error = errors_by_hand_id[hand_id]

        action = RepairAction(
            error_id=hand_id,
            action_type=determine_action_type(analysis),
            affected_phase=analysis.affected_phase,
            confidence=analysis.confidence,
            auto_executable=analysis.auto_fixable,
            action_params=build_action_params(error, analysis),
            gemini_suggested=analysis.suggested_fix
        )

        actions.append(action)

    # If no actions, return empty plan
    if not actions:
        return RepairPlan(
            actions=[],
            execution_order=[],
            total_errors=0,
            high_confidence_fixes=0,
            medium_confidence_fixes=0,
            low_confidence_fixes=0,
            estimated_success_rate=0.0
        )

    # Sort actions by dependencies
    execution_order = topological_sort(actions)

    # Calculate confidence metrics
    high_confidence = sum(1 for a in actions if a.confidence > 0.8)
    medium_confidence = sum(1 for a in actions if 0.5 <= a.confidence <= 0.8)
    low_confidence = sum(1 for a in actions if a.confidence < 0.5)

    # Estimate success rate (average confidence)
    avg_confidence = sum(a.confidence for a in actions) / len(actions)

    return RepairPlan(
        actions=actions,
        execution_order=execution_order,
        total_errors=len(actions),
        high_confidence_fixes=high_confidence,
        medium_confidence_fixes=medium_confidence,
        low_confidence_fixes=low_confidence,
        estimated_success_rate=avg_confidence
    )


if __name__ == "__main__":
    # Example usage
    from error_analyzer import ErrorAnalysis
    from error_parser import PTError

    # Mock data
    errors = {
        "file1.txt": [
            PTError(
                hand_id="SG123",
                error_type="duplicate_player",
                line_number=5,
                raw_message="Error...",
                player_name="Alice",
                seats_involved=[1, 2]
            )
        ]
    }

    analyses = {
        "SG123": ErrorAnalysis(
            error_type="duplicate_player",
            root_cause="Duplicate mapping",
            affected_phase="matcher",
            confidence=0.95,
            suggested_fix="Remove duplicate",
            auto_fixable=True,
            fix_code="remove_duplicate_mapping"
        )
    }

    plan = generate_repair_plan(job_id=1, errors=errors, analyses=analyses)

    print(f"Generated repair plan:")
    print(f"  Total errors: {plan.total_errors}")
    print(f"  High confidence: {plan.high_confidence_fixes}")
    print(f"  Success rate: {plan.estimated_success_rate:.2f}")
    print(f"  Actions: {len(plan.actions)}")
