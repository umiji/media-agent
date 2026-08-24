"""Task Model と状態遷移（要件定義書5.2節 / 詳細設計9章）。

主な公開物を再エクスポートする（申し送り K-1）。

**状態を変えてよいのは `TaskService.transition` だけである**（罠 D-T13）。
`TaskRepository.update_status` は遷移の可否を判定しない。
"""

from __future__ import annotations

from media_agent.core.task.models import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    Task,
    TaskStatus,
)
from media_agent.core.task.service import TaskService

__all__ = [
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATUSES",
    "Task",
    "TaskService",
    "TaskStatus",
]
