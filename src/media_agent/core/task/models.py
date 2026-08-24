"""Task の型と状態遷移表（詳細設計 9.1 / 9.2）。

遷移表は `ALLOWED_TRANSITIONS` **1箇所だけ**に置く。呼び出し側に
`if status == ...` を書かない（9.3）。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from media_agent.core.db.models import TaskRow

__all__ = [
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATUSES",
    "Task",
    "TaskStatus",
]


class TaskStatus(StrEnum):
    """Task の状態（詳細設計 9.1）。値は `tasks.status` の CHECK 制約と同じ。"""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


#: 終端の状態（詳細設計 9.2）。ここからの遷移はすべて禁止である。
TERMINAL_STATUSES: frozenset[TaskStatus] = frozenset(
    {TaskStatus.completed, TaskStatus.failed, TaskStatus.cancelled}
)

#: 許される状態遷移（詳細設計 9.2 の表）。**表に無い遷移はすべて禁止**。
#:
#: - `pending` → `running` / `cancelled`
#: - `running` → `completed` / `failed`
#: - `running` → `cancelled` は **Stage 0 では禁止**。同期実行の Agent を中断する手段が
#:   無く、「`cancelled` と記録されているのに Agent は最後まで動いた」状態を作れてしまう
#:   （D-X3。Scheduler / 非同期実行が入る Stage 3 以降で、中断機構と同時に解禁する）
#: - 同じ状態への遷移（`running` → `running` 等）も禁止
ALLOWED_TRANSITIONS: Mapping[TaskStatus, frozenset[TaskStatus]] = MappingProxyType(
    {
        TaskStatus.pending: frozenset({TaskStatus.running, TaskStatus.cancelled}),
        TaskStatus.running: frozenset({TaskStatus.completed, TaskStatus.failed}),
        TaskStatus.completed: frozenset(),
        TaskStatus.failed: frozenset(),
        TaskStatus.cancelled: frozenset(),
    }
)


class Task(BaseModel):
    """Task の1件（詳細設計 9.1）。不変であり、遷移は新しい `Task` を返す。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task_id: str
    agent: str
    type: str
    status: TaskStatus
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def is_terminal(self) -> bool:
        """終端に達しているか（詳細設計 9.1 / 9.2）。"""
        return self.status in TERMINAL_STATUSES

    @classmethod
    def from_row(cls, row: TaskRow) -> Task:
        """`TaskRepository` の戻り値から作る。

        `TaskRow.status` は `str` である（DB の値をそのまま持つ）。ここで `TaskStatus`
        へ変換することで、**DB 由来の値が値域の外なら読み出し時点で分かる**。
        """
        return cls(
            task_id=row.task_id,
            agent=row.agent,
            type=row.type,
            status=TaskStatus(row.status),
            input=row.input,
            output=row.output,
            error=row.error,
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
        )
