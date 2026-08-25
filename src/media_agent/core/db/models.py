"""Repository が返す行の型（詳細設計 6.6 / 罠 D-T11）。

**`sqlite3.Row` を `core/db/` の外へ出さない。** 出すと DB 方式の差し替え（拡張点 E-2）が
呼び出し側へ波及する。ここで定義する `*Row` は不変（frozen）の Pydantic モデルであり、
時刻は `datetime`、JSON 列は `dict` へ変換済みである。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from media_agent.core.clock import from_iso

__all__ = [
    "DecisionRow",
    "PerformanceRow",
    "PostRow",
    "ProjectRow",
    "SourceRow",
    "TaskRow",
    "dump_json",
    "load_json",
]


def dump_json(value: Any) -> str:
    """JSON 列へ書く文字列（詳細設計 6.2）。

    **`sort_keys=True` は再現性（要件20.5）のため必須。** 同じ内容が常に同じ文字列になる。
    """
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_json(text: str | None) -> Any:
    """JSON 列を読む。NULL は `None` のまま返す。"""
    if text is None:
        return None
    return json.loads(text)


def _dt(value: str | None) -> datetime | None:
    return None if value is None else from_iso(value)


class _Row(BaseModel):
    """行を表す不変モデル。"""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ProjectRow(_Row):
    """`projects` の1行（詳細設計 6.4 / 6.5）。"""

    project_id: str
    name: str
    configuration: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ProjectRow:
        return cls(
            project_id=row["project_id"],
            name=row["name"],
            configuration=load_json(row["configuration"]),
            created_at=from_iso(row["created_at"]),
            updated_at=from_iso(row["updated_at"]),
        )


class SourceRow(_Row):
    """`sources` の1行。Stage 1 以降が使う（Stage 0 は器だけ。6.1）。"""

    source_id: str
    title: str
    url: str | None
    source_type: str
    content: str | None
    collected_at: datetime
    score: float | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> SourceRow:
        return cls(
            source_id=row["source_id"],
            title=row["title"],
            url=row["url"],
            source_type=row["source_type"],
            content=row["content"],
            collected_at=from_iso(row["collected_at"]),
            score=row["score"],
        )


class PostRow(_Row):
    """`posts` の1行。Stage 1 以降が使う。"""

    post_id: str
    content: str
    topic: str | None
    source_id: str | None
    status: str
    created_at: datetime
    scheduled_at: datetime | None
    published_at: datetime | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> PostRow:
        return cls(
            post_id=row["post_id"],
            content=row["content"],
            topic=row["topic"],
            source_id=row["source_id"],
            status=row["status"],
            created_at=from_iso(row["created_at"]),
            scheduled_at=_dt(row["scheduled_at"]),
            published_at=_dt(row["published_at"]),
        )


class PerformanceRow(_Row):
    """`performances` の1行。Stage 5 以降が使う。"""

    performance_id: str
    post_id: str
    impressions: int | None
    likes: int | None
    replies: int | None
    reposts: int | None
    collected_at: datetime

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> PerformanceRow:
        return cls(
            performance_id=row["performance_id"],
            post_id=row["post_id"],
            impressions=row["impressions"],
            likes=row["likes"],
            replies=row["replies"],
            reposts=row["reposts"],
            collected_at=from_iso(row["collected_at"]),
        )


class TaskRow(_Row):
    """`tasks` の1行（詳細設計 6.4）。

    **状態遷移の正しさはここでは保証しない。** 遷移を判定するのは `TaskService`（9.3 / 罠 D-T13）。
    """

    task_id: str
    agent: str
    type: str
    status: str
    input: dict[str, Any]
    output: dict[str, Any] | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> TaskRow:
        return cls(
            task_id=row["task_id"],
            agent=row["agent"],
            type=row["type"],
            status=row["status"],
            input=load_json(row["input"]),
            output=load_json(row["output"]),
            error=row["error"],
            created_at=from_iso(row["created_at"]),
            started_at=_dt(row["started_at"]),
            completed_at=_dt(row["completed_at"]),
        )


class DecisionRow(_Row):
    """`decisions` の1行（詳細設計 6.4）。

    **このテーブルは Decision Entity であると同時に監査記録の正本である**（11.1 / 11.3）。
    """

    decision_id: str
    kind: str
    agent: str
    task_id: str | None
    input: dict[str, Any]
    decision: str
    reason: str
    action: str | None
    result: dict[str, Any] | None
    error: str | None
    timestamp: datetime
    #: 実行した Agent の版数（スキーマ版数 2。`policy_check` と版数1 の行は `None`）。
    agent_version: int | None = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> DecisionRow:
        return cls(
            decision_id=row["decision_id"],
            kind=row["kind"],
            agent=row["agent"],
            task_id=row["task_id"],
            input=load_json(row["input"]),
            decision=row["decision"],
            reason=row["reason"],
            action=row["action"],
            result=load_json(row["result"]),
            error=row["error"],
            timestamp=from_iso(row["timestamp"]),
            agent_version=row["agent_version"],
        )
