"""WFE Execution Engine — business logic for plan execution.

Pure Python, no Flask dependency. Can be used by:
- Flask routes (wfe-ui/api.py)
- AI agents via Python API
- MCP tools (future)
"""

from .types import (
    ColumnDef,
    CellValue,
    PlanDefinition,
    ExecutionState,
    CellState,
    RowState,
    PlanState,
    AcceptanceResult,
    FillResult,
    Snapshot,
)
from .execution import PlanEngine
from .persistence import load_plan, load_execution_state, save_execution_state

__all__ = [
    "ColumnDef",
    "CellValue",
    "PlanDefinition",
    "ExecutionState",
    "CellState",
    "RowState",
    "PlanState",
    "AcceptanceResult",
    "FillResult",
    "Snapshot",
    "PlanEngine",
    "load_plan",
    "load_execution_state",
    "save_execution_state",
]
