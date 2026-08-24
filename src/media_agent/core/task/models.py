"""Task の型と状態遷移表（詳細設計 9.1・9.2）。

**状態遷移の可否を決めるのは `ALLOWED_TRANSITIONS` ただ1つである**（9.3）。
呼び出し側に `if status == ...` の分岐を書かないこと。判定が2か所に分かれた時点で、
片方だけが更新される（罠 D-T13）。
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
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
    """Task の状態（詳細設計 9.1）。値は `tasks.status` の CHECK 制約と一致する。"""

    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


#: 終端の状態（詳細設計 9.2 の 3・4・5 の遷移先）。ここからの遷移は無い。
TERMINAL_STATUSES: frozenset[TaskStatus] = frozenset(
    {TaskStatus.completed, TaskStatus.failed, TaskStatus.cancelled}
)

#: 許される状態遷移（詳細設計 9.2 の表そのもの）。
#:
#: **表に無い遷移はすべて禁止である。** 同じ状態への遷移（9行目）も、終端からの遷移（8行目）も、
#: `running` → `cancelled`（6行目・Stage 0 では中断機構が無いため）も含まれない。
ALLOWED_TRANSITIONS: Mapping[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.pending: frozenset({TaskStatus.running, TaskStatus.cancelled}),
    TaskStatus.running: frozenset({TaskStatus.completed, TaskStatus.failed}),
    TaskStatus.completed: frozenset(),
    TaskStatus.failed: frozenset(),
    TaskStatus.cancelled: frozenset(),
}


class Task(BaseModel):
    """Task の1件（詳細設計 9.1）。

    `TaskRow`（DB の行）との違いは `status` が `TaskStatus` であること。
    **DB の行をそのまま外へ流さない**（罠 D-T11）ことと同じ理由で、状態を文字列のまま
    持ち回らない。文字列で持つと、遷移表の引き当てが呼び出し側の責任になる。
    """

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
        """終端の状態か（`completed` / `failed` / `cancelled`）。"""
        return self.status in TERMINAL_STATUSES

    @classmethod
    def from_row(cls, row: TaskRow) -> Task:
        """Repository の戻り値から作る。"""
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
