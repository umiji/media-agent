"""Task の生成・遷移・参照（詳細設計 9.3）。

**遷移の可否を判定するのはこのクラスだけである**（罠 D-T13）。判定は
`ALLOWED_TRANSITIONS` の参照1箇所に閉じており、状態名の分岐を書かない。
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

#: `failed` へ遷移するのに `error` が渡されなかったときに補う文字列。
#: 監査記録の `error` 項目が空になるのを防ぐ（詳細設計 9.3）。
UNKNOWN_ERROR = "unknown error"


class TaskService:
    """Task の状態を管理する唯一の窓口（詳細設計 9.3）。

    トランザクションの境界は持たない（詳細設計 6.6）。書き込みが確定するのは
    `AuditRecorder` 経由の記録時である（`DecisionRepository.add` がコミットする。
    申し送り L-2）。**Runner は「状態を変えてから記録する」順で呼ぶ**（8.3）ため、
    記録が済んだ時点で Task の更新も一緒に確定する。
    """

    def __init__(
        self,
        repo: TaskRepository,
        *,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._repo = repo
        self._clock = clock

    def create(self, *, agent: str, type: str, input: dict[str, Any]) -> Task:
        """`pending` の Task を1件作る（詳細設計 9.2 の遷移1）。"""
        return Task.from_row(self._repo.add(agent=agent, type=type, input=input))

    def transition(
        self,
        task_id: str,
        to: TaskStatus,
        *,
        output: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> Task:
        """状態を遷移させる（詳細設計 9.2 / 9.3）。

        検査は**書き込みより前**に行う。禁止された遷移を要求されたとき、DB は
        書き換わらない（S-F の判定対象）。

        Raises:
            InvalidTaskTransitionError: 9.2 の表に無い遷移を要求した。メッセージには
                遷移元・遷移先の状態名と `task_id` を含める（安定文字列。詳細設計 17.3）。
            DatabaseError: `task_id` に該当する Task が無い。
        """
        current = self.get(task_id)
        if to not in ALLOWED_TRANSITIONS[current.status]:
            allowed = sorted(
                status.value for status in ALLOWED_TRANSITIONS[current.status]
            )
            raise InvalidTaskTransitionError(
                f"Task の状態を {current.status.value} から {to.value} へ"
                f"遷移させることはできません: {task_id}",
                details=[
                    f"{current.status.value} から遷移できる状態: "
                    + (", ".join(allowed) if allowed else "（終端の状態です）")
                ],
            )
        now = self._clock()
        row = self._repo.update_status(
            task_id,
            status=to.value,
            output=output,
            error=self._error_for(to, error),
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
            raise DatabaseError(f"tasks に該当する行がありません: {task_id}")
        return Task.from_row(row)

    def list(self, *, status: TaskStatus | None = None, limit: int = 20) -> list[Task]:
        """作成時刻の降順で一覧する（詳細設計 6.6 / 16.2）。"""
        rows = self._repo.list(
            status=None if status is None else status.value, limit=limit
        )
        return [Task.from_row(row) for row in rows]

    def counts(self) -> dict[TaskStatus, int]:
        """状態ごとの件数。**5状態すべてのキーを返す**（詳細設計 6.6 / 9.3）。"""
        counts = self._repo.count_by_status()
        return {status: counts.get(status.value, 0) for status in TaskStatus}

    @staticmethod
    def _error_for(to: TaskStatus, error: str | None) -> str | None:
        """`failed` で `error` が無い場合だけ補う（詳細設計 9.3）。

        引数の不整合そのものは許す（Agent が出力を返さないこともある）。ただし
        `error` が空のまま `failed` にすると、監査記録の `error` 項目が空になる。
        """
        if to is not TaskStatus.failed:
            return error
        return error if error else UNKNOWN_ERROR
