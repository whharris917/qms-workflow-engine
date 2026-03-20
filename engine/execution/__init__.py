"""WFE Execution Engine — business logic for plan execution.

Pure Python, no Flask dependency. Can be used by:
- Flask routes (app/api.py)
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
from .persistence import load_plan

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
]
