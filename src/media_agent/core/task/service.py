"""Task の生成と状態遷移（詳細設計 9.3）。

**`TaskRepository.update_status` を呼んでよいのは `TaskService.transition` だけである**
（罠 D-T13）。Repository は遷移の可否を判定しないため、直接呼ぶと遷移表を迂回できる。
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from media_agent.core.clock import utcnow
from media_agent.core.db.repositories import TaskRepository
from media_agent.core.task.models import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    Task,
    TaskStatus,
)
from media_agent.errors import DatabaseError, InvalidTaskTransitionError

__all__ = ["TaskService"]

#: `failed` なのに理由が渡されなかった場合に補う値（詳細設計 9.3）。
#: 監査記録の `error` 項目が空になるのを防ぐ。
UNKNOWN_ERROR = "unknown error"

Clock = Callable[[], datetime]


class TaskService:
    """Task のライフサイクルを持つ唯一の入口（詳細設計 9.3）。"""

    def __init__(self, repo: TaskRepository, *, clock: Clock = utcnow) -> None:
        self._repo = repo
        self._clock = clock

    def create(self, *, agent: str, type: str, input: dict[str, Any]) -> Task:
        """`pending` の Task を作る（詳細設計 9.2 の遷移1）。"""
        return Task.from_row(self._repo.add(agent=agent, type=type, input=input))

    def transition(
        self,
        task_id: str,
        to: TaskStatus,
        *,
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> Task:
        """状態を遷移させる（詳細設計 9.2）。

        **検査は書き込みより前に行う。** 表に無い遷移では DB を書き換えない。

        引数の不整合（`completed` なのに `output=None` 等）は許す。Agent が出力を返さない
        こともあるため。ただし `failed` で `error=None` のときだけ `UNKNOWN_ERROR` を補う。

        Raises:
            InvalidTaskTransitionError: 詳細設計 9.2 の表に無い遷移を要求した。
        """
        current = self.get(task_id)
        if to not in ALLOWED_TRANSITIONS[current.status]:
            allowed = sorted(status.value for status in ALLOWED_TRANSITIONS[current.status])
            raise InvalidTaskTransitionError(
                f"Task の状態遷移が許可されていません: "
                f"{current.status.value} -> {to.value} (task_id={task_id})",
                details=[
                    f"{current.status.value} から遷移できる状態: "
                    f"{', '.join(allowed) if allowed else '（終端。遷移できません）'}"
                ],
            )
        now = self._clock()
        if to is TaskStatus.failed and error is None:
            error = UNKNOWN_ERROR
        row = self._repo.update_status(
            task_id,
            status=to.value,
            output=output,
            error=error,
            started_at=now if to is TaskStatus.running else None,
            completed_at=now if to in TERMINAL_STATUSES else None,
        )
        return Task.from_row(row)

    def get(self, task_id: str) -> Task:
        """1件取得する。

        Raises:
            DatabaseError: 該当する Task が無い。
        """
        row = self._repo.get(task_id)
        if row is None:
            raise DatabaseError(f"Task が見つかりません: {task_id}")
        return Task.from_row(row)

    def list(self, *, status: TaskStatus | None = None, limit: int = 20) -> list[Task]:
        """作成時刻の降順に一覧する（詳細設計 6.6）。"""
        rows = self._repo.list(
            status=None if status is None else status.value, limit=limit
        )
        return [Task.from_row(row) for row in rows]

    def counts(self) -> dict[TaskStatus, int]:
        """状態ごとの件数。**5状態すべてのキーを返す**（詳細設計 6.6 / 9.3）。"""
        counted = self._repo.count_by_status()
        return {status: counted.get(status.value, 0) for status in TaskStatus}
