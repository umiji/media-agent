"""6 Entity の Repository（詳細設計 6.6）。

- すべて `sqlite3.Connection` を**位置引数で**受け取る（申し送り K-2）
- **トランザクションの境界は呼び出し側が持つ**（`with conn:`）。
  唯一の例外が `DecisionRepository.add` である（監査記録は正本であり、その場でコミットする。11.3）
- 戻り値は `models.py` の `*Row`。**`sqlite3.Row` を外へ出さない**（罠 D-T11）
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypeVar

from media_agent.core.clock import to_iso, utcnow
from media_agent.core.db.models import (
    DecisionRow,
    PerformanceRow,
    PostRow,
    ProjectRow,
    SourceRow,
    TaskRow,
    dump_json,
)
from media_agent.errors import DatabaseError

if TYPE_CHECKING:  # pragma: no cover - 型注釈のためだけの参照
    from media_agent.core.config.models import Config
    from media_agent.core.observability.audit import AuditRecord

__all__ = [
    "DecisionRepository",
    "PerformanceRepository",
    "PostRepository",
    "ProjectRepository",
    "SourceRepository",
    "TaskRepository",
    "POST_STATUSES",
    "TASK_STATUSES",
]

#: `tasks.status` の値域（詳細設計 6.4 の CHECK 制約と同じ）。
TASK_STATUSES: tuple[str, ...] = (
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
)

#: `posts.status` の値域（詳細設計 6.4 の CHECK 制約と同じ）。
POST_STATUSES: tuple[str, ...] = (
    "draft",
    "approved",
    "scheduled",
    "published",
    "rejected",
    "failed",
)

Clock = Callable[[], datetime]

_T = TypeVar("_T")


def new_id() -> str:
    """主キーの値（詳細設計 6.2: `str(uuid.uuid4())`）。"""
    return str(uuid.uuid4())


class _Repository:
    """接続と時計を持つ共通の基底。"""

    def __init__(self, conn: sqlite3.Connection, *, clock: Clock = utcnow) -> None:
        self._conn = conn
        self._clock = clock

    def _now(self, value: datetime | None = None) -> str:
        return to_iso(value if value is not None else self._clock())


class ProjectRepository(_Repository):
    """`projects`（詳細設計 6.5）。**行は高々1つ。この制約は DB ではなくここが保証する。**"""

    def sync(self, config: Config) -> ProjectRow:
        """設定のスナップショットを同期する。

        行が無ければ採番して挿入し、あれば `name` / `configuration` が変化したときだけ
        `updated_at` とともに更新する。**再現性（要件20.5）のため、そのとき何の設定で
        動いたかを DB から辿れるようにする。**
        """
        configuration = dump_json(config.model_dump(mode="json"))
        name = config.project.name
        current = self.get()
        now = self._now()
        if current is None:
            project_id = new_id()
            self._conn.execute(
                "INSERT INTO projects"
                " (project_id, name, configuration, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (project_id, name, configuration, now, now),
            )
            return _require(self.get(), project_id)
        if current.name == name and dump_json(current.configuration) == configuration:
            return current
        self._conn.execute(
            "UPDATE projects SET name = ?, configuration = ?, updated_at = ?"
            " WHERE project_id = ?",
            (name, configuration, now, current.project_id),
        )
        return _require(self.get(), current.project_id)

    def get(self) -> ProjectRow | None:
        """唯一の行を返す（無ければ `None`）。"""
        row = self._conn.execute(
            "SELECT * FROM projects ORDER BY created_at LIMIT 1"
        ).fetchone()
        return None if row is None else ProjectRow.from_row(row)


class SourceRepository(_Repository):
    """`sources`（Stage 1 以降が使う。Stage 0 は器と最低限の読み書きのみ）。"""

    def add(
        self,
        *,
        title: str,
        source_type: str,
        url: str | None = None,
        content: str | None = None,
        score: float | None = None,
        collected_at: datetime | None = None,
    ) -> SourceRow:
        source_id = new_id()
        self._conn.execute(
            "INSERT INTO sources"
            " (source_id, title, url, source_type, content, collected_at, score)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                source_id,
                title,
                url,
                source_type,
                content,
                self._now(collected_at),
                score,
            ),
        )
        return _require(self.get(source_id), source_id)

    def get(self, source_id: str) -> SourceRow | None:
        row = self._conn.execute(
            "SELECT * FROM sources WHERE source_id = ?", (source_id,)
        ).fetchone()
        return None if row is None else SourceRow.from_row(row)

    def list(self, *, limit: int = 50) -> list[SourceRow]:
        rows = self._conn.execute(
            "SELECT * FROM sources ORDER BY collected_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [SourceRow.from_row(row) for row in rows]


class PostRepository(_Repository):
    """`posts`（Stage 1 以降が使う）。"""

    def add(
        self,
        *,
        content: str,
        status: str = "draft",
        topic: str | None = None,
        source_id: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> PostRow:
        _check_value(status, POST_STATUSES, "posts.status")
        post_id = new_id()
        self._conn.execute(
            "INSERT INTO posts"
            " (post_id, content, topic, source_id, status, created_at, scheduled_at,"
            "  published_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
            (
                post_id,
                content,
                topic,
                source_id,
                status,
                self._now(),
                None if scheduled_at is None else to_iso(scheduled_at),
            ),
        )
        return _require(self.get(post_id), post_id)

    def get(self, post_id: str) -> PostRow | None:
        row = self._conn.execute(
            "SELECT * FROM posts WHERE post_id = ?", (post_id,)
        ).fetchone()
        return None if row is None else PostRow.from_row(row)

    def list(self, *, status: str | None = None, limit: int = 50) -> list[PostRow]:
        if status is None:
            rows = self._conn.execute(
                "SELECT * FROM posts ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM posts WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        return [PostRow.from_row(row) for row in rows]

    def set_status(
        self, post_id: str, status: str, *, published_at: datetime | None = None
    ) -> PostRow:
        _check_value(status, POST_STATUSES, "posts.status")
        if self.get(post_id) is None:
            raise DatabaseError(f"posts に該当する行がありません: {post_id}")
        if published_at is None:
            self._conn.execute(
                "UPDATE posts SET status = ? WHERE post_id = ?", (status, post_id)
            )
        else:
            self._conn.execute(
                "UPDATE posts SET status = ?, published_at = ? WHERE post_id = ?",
                (status, to_iso(published_at), post_id),
            )
        return _require(self.get(post_id), post_id)


class PerformanceRepository(_Repository):
    """`performances`（Stage 5 以降が使う）。"""

    def add(
        self,
        *,
        post_id: str,
        impressions: int | None = None,
        likes: int | None = None,
        replies: int | None = None,
        reposts: int | None = None,
        collected_at: datetime | None = None,
    ) -> PerformanceRow:
        performance_id = new_id()
        self._conn.execute(
            "INSERT INTO performances"
            " (performance_id, post_id, impressions, likes, replies, reposts,"
            "  collected_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                performance_id,
                post_id,
                impressions,
                likes,
                replies,
                reposts,
                self._now(collected_at),
            ),
        )
        row = self._conn.execute(
            "SELECT * FROM performances WHERE performance_id = ?", (performance_id,)
        ).fetchone()
        return PerformanceRow.from_row(_require(row, performance_id))

    def list_for_post(self, post_id: str) -> list[PerformanceRow]:
        rows = self._conn.execute(
            "SELECT * FROM performances WHERE post_id = ? ORDER BY collected_at",
            (post_id,),
        ).fetchall()
        return [PerformanceRow.from_row(row) for row in rows]


class TaskRepository(_Repository):
    """`tasks`（詳細設計 6.6）。

    **状態遷移の可否はここでは判定しない**（罠 D-T13）。`update_status` を呼んでよいのは
    `TaskService.transition` だけである（T-006）。
    """

    def add(self, *, agent: str, type: str, input: dict[str, Any]) -> TaskRow:
        task_id = new_id()
        self._conn.execute(
            "INSERT INTO tasks"
            " (task_id, agent, type, status, input, output, error, created_at,"
            "  started_at, completed_at)"
            " VALUES (?, ?, ?, 'pending', ?, NULL, NULL, ?, NULL, NULL)",
            (task_id, agent, type, dump_json(input), self._now()),
        )
        return _require(self.get(task_id), task_id)

    def get(self, task_id: str) -> TaskRow | None:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        return None if row is None else TaskRow.from_row(row)

    def update_status(
        self,
        task_id: str,
        *,
        status: str,
        output: dict[str, Any] | None = None,
        error: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> TaskRow:
        """状態と付随する値を更新する。**`None` の項目は既存値を保つ。**"""
        _check_value(status, TASK_STATUSES, "tasks.status")
        if self.get(task_id) is None:
            raise DatabaseError(f"tasks に該当する行がありません: {task_id}")
        assignments = ["status = ?"]
        params: list[Any] = [status]
        if output is not None:
            assignments.append("output = ?")
            params.append(dump_json(output))
        if error is not None:
            assignments.append("error = ?")
            params.append(error)
        if started_at is not None:
            assignments.append("started_at = ?")
            params.append(to_iso(started_at))
        if completed_at is not None:
            assignments.append("completed_at = ?")
            params.append(to_iso(completed_at))
        params.append(task_id)
        self._conn.execute(
            f"UPDATE tasks SET {', '.join(assignments)} WHERE task_id = ?",
            tuple(params),
        )
        return _require(self.get(task_id), task_id)

    def list(self, *, status: str | None = None, limit: int = 20) -> list[TaskRow]:
        """作成時刻の降順（詳細設計 6.6）。"""
        if status is None:
            rows = self._conn.execute(
                "SELECT * FROM tasks ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE status = ?"
                " ORDER BY created_at DESC, rowid DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        return [TaskRow.from_row(row) for row in rows]

    def count_by_status(self) -> dict[str, int]:
        """**5状態すべてのキーを返す**（該当が無ければ 0。詳細設計 6.6）。

        キーが欠けると、呼び出し側が `status` の表示で毎回 `get(..., 0)` を書くことになる。
        """
        counts = dict.fromkeys(TASK_STATUSES, 0)
        for row in self._conn.execute(
            "SELECT status, COUNT(*) AS count FROM tasks GROUP BY status"
        ).fetchall():
            counts[str(row["status"])] = int(row["count"])
        return counts


class DecisionRepository(_Repository):
    """`decisions`（詳細設計 6.6 / 11.3）。

    **監査記録の正本の書き込み先である。** 書き込み口は `AuditRecorder` ただ1つであり、
    この Repository を直接呼んで監査行を作らないこと（用語集「AuditRecorder」）。
    """

    def add(self, record: AuditRecord) -> str:
        """1行 INSERT して**コミットする**（詳細設計 11.3 の手順1）。

        監査記録は正本であるため、呼び出し側のトランザクション境界を待たずに確定させる。
        これは 6.6 の「境界は呼び出し側が持つ」規約の唯一の例外である。
        """
        self._conn.execute(
            "INSERT INTO decisions"
            " (decision_id, kind, agent, task_id, input, decision, reason, action,"
            "  result, error, timestamp)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                record.decision_id,
                record.kind,
                record.agent,
                record.task,
                dump_json(record.input),
                record.decision,
                record.reason,
                record.action,
                None if record.result is None else dump_json(record.result),
                record.error,
                to_iso(record.timestamp),
            ),
        )
        self._conn.commit()
        return record.decision_id

    def get(self, decision_id: str) -> DecisionRow | None:
        row = self._conn.execute(
            "SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)
        ).fetchone()
        return None if row is None else DecisionRow.from_row(row)

    def list(
        self,
        *,
        task_id: str | None = None,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[DecisionRow]:
        conditions: list[str] = []
        params: list[Any] = []
        if task_id is not None:
            conditions.append("task_id = ?")
            params.append(task_id)
        if kind is not None:
            conditions.append("kind = ?")
            params.append(kind)
        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        params.append(limit)
        rows = self._conn.execute(
            f"SELECT * FROM decisions{where}"
            " ORDER BY timestamp DESC, rowid DESC LIMIT ?",
            tuple(params),
        ).fetchall()
        return [DecisionRow.from_row(row) for row in rows]

    def count_allowed_actions(
        self,
        *,
        action: str | None,
        since: datetime,
        until: datetime | None = None,
    ) -> int:
        """`allow` と判定した Action の件数（詳細設計 10.5 の代理計数）。

        `action=None` なら全 Action の合計（`limits.max_actions_per_hour` 用）。
        **Stage 0 では「許可された回数」を「実行された回数」の代理とする**（D-X1）。
        Stage 3 で Action を実装したら、このメソッドを実行回数の計数へ差し替える（拡張点 E-4）。
        """
        sql = (
            "SELECT COUNT(*) AS count FROM decisions"
            " WHERE kind = 'policy_check' AND decision = 'allow' AND timestamp >= ?"
        )
        params: list[Any] = [to_iso(since)]
        if action is not None:
            sql += " AND action = ?"
            params.append(action)
        if until is not None:
            sql += " AND timestamp < ?"
            params.append(to_iso(until))
        row = self._conn.execute(sql, tuple(params)).fetchone()
        return int(row["count"])


def _check_value(value: str, allowed: tuple[str, ...], label: str) -> None:
    """値域の検査。DB の CHECK 制約より前に、説明できるエラーへ変換する。"""
    if value not in allowed:
        raise DatabaseError(
            f"{label} に指定できない値です: {value!r}",
            details=[f"指定できる値: {', '.join(allowed)}"],
        )


def _require(value: _T | None, key: str) -> _T:
    """直前に書いた行が読み戻せることを保証する。"""
    if value is None:
        raise DatabaseError(f"書き込んだ行を読み戻せませんでした: {key}")
    return value
