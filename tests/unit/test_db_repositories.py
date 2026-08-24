"""`core/db/repositories.py` の単体テスト（詳細設計 6.5・6.6）。

Stage 0 で使わない Entity（Source / Post / Performance）についても、
**最低限の書き込み・読み出し**を確認する（T-005 完了条件8）。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from media_agent.core.config.models import Config
from media_agent.core.db.connection import connect
from media_agent.core.db.migrations import ensure_schema
from media_agent.core.db.repositories import (
    DecisionRepository,
    PerformanceRepository,
    PostRepository,
    ProjectRepository,
    SourceRepository,
    TaskRepository,
)
from media_agent.core.observability.audit import AuditRecord
from media_agent.errors import DatabaseError

FIXED_NOW = datetime(2026, 8, 23, 10, 0, 0, 123456, tzinfo=UTC)


@pytest.fixture()
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(tmp_path / "media-agent.db")
    ensure_schema(connection)
    yield connection
    connection.close()


def _config(name: str = "sample-project", posts_per_day: int = 3) -> Config:
    return Config.model_validate(
        {
            "version": 1,
            "project": {"name": name},
            "content": {"posts_per_day": posts_per_day},
        }
    )


def _audit_record(**overrides: object) -> AuditRecord:
    values: dict[str, object] = {
        "timestamp": FIXED_NOW,
        "agent": "echo",
        "task": None,
        "input": {"message": "hi"},
        "decision": "ok",
        "reason": "テスト",
        "action": None,
        "result": {"message": "hi"},
        "error": None,
        "kind": "agent_run",
    }
    values.update(overrides)
    return AuditRecord.model_validate(values)


# --- projects（詳細設計 6.5）-----------------------------------------------------------


def test_project_sync_inserts_then_reuses_the_single_row(
    conn: sqlite3.Connection,
) -> None:
    """行は高々1つ。**この制約は Repository が保証する**（詳細設計 6.5）。"""
    repository = ProjectRepository(conn)

    first = repository.sync(_config())
    second = repository.sync(_config())

    assert first.project_id == second.project_id
    assert first.updated_at == second.updated_at  # 変化が無ければ更新しない
    assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1


def test_project_sync_updates_when_the_configuration_changes(
    conn: sqlite3.Connection,
) -> None:
    """設定が変わったときだけ `updated_at` を進める（詳細設計 6.5）。"""
    repository = ProjectRepository(conn)
    first = repository.sync(_config())

    changed = repository.sync(_config(posts_per_day=5))

    assert changed.project_id == first.project_id
    assert changed.updated_at >= first.updated_at
    assert changed.configuration["content"]["posts_per_day"] == 5


def test_project_configuration_is_a_snapshot_of_the_validated_config(
    conn: sqlite3.Connection,
) -> None:
    """**そのとき何の設定で動いたか**を DB から辿れる（要件20.5 再現性）。"""
    row = ProjectRepository(conn).sync(_config("snapshot"))

    assert row.configuration["project"]["name"] == "snapshot"
    assert row.configuration["actions"]["post"]["mode"] == "auto"


# --- sources / posts / performances（完了条件8）----------------------------------------


def test_source_can_be_written_and_read(conn: sqlite3.Connection) -> None:
    """Stage 1 以降が使う `sources` も器として動く（詳細設計 6.1）。"""
    repository = SourceRepository(conn)

    added = repository.add(
        title="記事", source_type="manual", url="https://example.test/a", score=0.5
    )

    assert repository.get(added.source_id) == added
    assert repository.list() == [added]
    assert added.content is None


def test_post_can_be_written_read_and_transitioned(conn: sqlite3.Connection) -> None:
    """`posts` の書き込み・読み出しと状態の更新。"""
    source = SourceRepository(conn).add(title="記事", source_type="manual")
    repository = PostRepository(conn)

    post = repository.add(content="本文", topic="ai", source_id=source.source_id)
    published_at = FIXED_NOW + timedelta(hours=1)
    updated = repository.set_status(
        post.post_id, "published", published_at=published_at
    )

    assert post.status == "draft"
    assert updated.status == "published"
    assert updated.published_at == published_at
    assert repository.list(status="published") == [updated]
    assert repository.list(status="draft") == []


def test_post_status_is_validated(conn: sqlite3.Connection) -> None:
    """値域の違反は `DatabaseError` として説明する（品質基準 Q8）。"""
    with pytest.raises(DatabaseError):
        PostRepository(conn).add(content="本文", status="unknown")


def test_performance_can_be_written_and_read(conn: sqlite3.Connection) -> None:
    """`performances` は同じ投稿に対して時系列で複数件持てる（詳細設計 6.4）。"""
    post = PostRepository(conn).add(content="本文")
    repository = PerformanceRepository(conn)

    first = repository.add(
        post_id=post.post_id, impressions=10, likes=1, collected_at=FIXED_NOW
    )
    second = repository.add(
        post_id=post.post_id,
        impressions=20,
        likes=3,
        collected_at=FIXED_NOW + timedelta(hours=1),
    )

    assert repository.list_for_post(post.post_id) == [first, second]
    assert second.replies is None


def test_performance_rejects_duplicate_collection_time(
    conn: sqlite3.Connection,
) -> None:
    """`UNIQUE (post_id, collected_at)`（詳細設計 6.4）。"""
    post = PostRepository(conn).add(content="本文")
    repository = PerformanceRepository(conn)
    repository.add(post_id=post.post_id, collected_at=FIXED_NOW)

    with pytest.raises(sqlite3.IntegrityError):
        repository.add(post_id=post.post_id, collected_at=FIXED_NOW)


# --- tasks（詳細設計 6.6）--------------------------------------------------------------


def test_task_is_created_as_pending(conn: sqlite3.Connection) -> None:
    """`add` は必ず `pending` で作る（詳細設計 6.6）。"""
    task = TaskRepository(conn).add(
        agent="echo", type="agent_run", input={"message": "hi"}
    )

    assert task.status == "pending"
    assert task.input == {"message": "hi"}
    assert task.started_at is None
    assert task.completed_at is None
    assert task.error is None


def test_task_update_status_keeps_untouched_columns(conn: sqlite3.Connection) -> None:
    """`None` を渡した項目は既存値を保つ。"""
    repository = TaskRepository(conn)
    task = repository.add(agent="echo", type="agent_run", input={})
    started = FIXED_NOW
    completed = FIXED_NOW + timedelta(seconds=1)

    running = repository.update_status(
        task.task_id, status="running", started_at=started
    )
    done = repository.update_status(
        task.task_id,
        status="completed",
        output={"message": "hi"},
        completed_at=completed,
    )

    assert running.started_at == started
    assert done.started_at == started
    assert done.completed_at == completed
    assert done.output == {"message": "hi"}


def test_task_update_status_validates_the_value(conn: sqlite3.Connection) -> None:
    repository = TaskRepository(conn)
    task = repository.add(agent="echo", type="agent_run", input={})

    with pytest.raises(DatabaseError):
        repository.update_status(task.task_id, status="done")


def test_task_update_status_rejects_unknown_task(conn: sqlite3.Connection) -> None:
    with pytest.raises(DatabaseError):
        TaskRepository(conn).update_status("missing", status="running")


def test_task_list_is_newest_first_and_filters_by_status(
    conn: sqlite3.Connection,
) -> None:
    """`created_at` の降順（詳細設計 6.6）。"""
    repository = TaskRepository(conn)
    first = repository.add(agent="echo", type="agent_run", input={})
    second = repository.add(agent="fail", type="agent_run", input={})
    repository.update_status(second.task_id, status="failed", error="失敗")

    listed = repository.list()

    assert [task.task_id for task in listed] == [second.task_id, first.task_id]
    assert [task.task_id for task in repository.list(status="failed")] == [
        second.task_id
    ]
    assert len(repository.list(limit=1)) == 1


def test_task_count_by_status_returns_all_five_keys(conn: sqlite3.Connection) -> None:
    """**5状態すべてのキーを返す**（詳細設計 6.6）。"""
    repository = TaskRepository(conn)
    repository.add(agent="echo", type="agent_run", input={})

    counts = repository.count_by_status()

    assert set(counts) == {"pending", "running", "completed", "failed", "cancelled"}
    assert counts["pending"] == 1
    assert counts["completed"] == 0


# --- decisions（詳細設計 6.6 / 10.5）---------------------------------------------------


def test_decision_add_commits_immediately(
    conn: sqlite3.Connection, tmp_path: Path
) -> None:
    """監査記録は正本。**別接続からも見える**（詳細設計 11.3 の手順1 / 申し送り K-5）。"""
    record = _audit_record()

    decision_id = DecisionRepository(conn).add(record)

    other = connect(tmp_path / "media-agent.db")
    rows = other.execute(
        "SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)
    ).fetchall()
    other.close()

    assert len(rows) == 1
    assert rows[0]["agent"] == "echo"


def test_decision_round_trips_all_nine_items(conn: sqlite3.Connection) -> None:
    """要件定義書5.5節の9項目が列として往復する（詳細設計 11.3 の対応表）。"""
    repository = DecisionRepository(conn)
    task = TaskRepository(conn).add(agent="echo", type="agent_run", input={})
    record = _audit_record(task=task.task_id, action=None, error=None)

    stored = repository.get(repository.add(record))

    assert stored is not None
    assert stored.timestamp == record.timestamp
    assert stored.agent == record.agent
    assert stored.task_id == task.task_id
    assert stored.input == record.input
    assert stored.decision == record.decision
    assert stored.reason == record.reason
    assert stored.action is None
    assert stored.result == record.result
    assert stored.error is None
    assert stored.kind == "agent_run"


def test_decision_list_filters_by_task_and_kind(conn: sqlite3.Connection) -> None:
    repository = DecisionRepository(conn)
    task = TaskRepository(conn).add(agent="echo", type="agent_run", input={})
    repository.add(_audit_record(task=task.task_id))
    repository.add(
        _audit_record(
            kind="policy_check",
            agent="policy-engine",
            action="post",
            decision="allow",
            timestamp=FIXED_NOW + timedelta(minutes=1),
        )
    )

    assert len(repository.list()) == 2
    assert len(repository.list(task_id=task.task_id)) == 1
    assert len(repository.list(kind="policy_check")) == 1
    assert repository.list(limit=1)[0].kind == "policy_check"  # 新しい順


def test_count_allowed_actions_counts_only_allowed_policy_checks(
    conn: sqlite3.Connection,
) -> None:
    """`kind='policy_check' AND decision='allow' AND action=?` を数える（詳細設計 10.5）。"""
    repository = DecisionRepository(conn)
    base = FIXED_NOW
    for index, (kind, decision, action) in enumerate(
        [
            ("policy_check", "allow", "post"),
            ("policy_check", "deny", "post"),
            ("policy_check", "allow", "reply"),
            ("agent_run", "allow", None),
        ]
    ):
        repository.add(
            _audit_record(
                kind=kind,
                decision=decision,
                action=action,
                timestamp=base + timedelta(seconds=index),
            )
        )

    since = base - timedelta(hours=1)

    assert repository.count_allowed_actions(action="post", since=since) == 1
    assert repository.count_allowed_actions(action="reply", since=since) == 1
    assert repository.count_allowed_actions(action=None, since=since) == 2


def test_count_allowed_actions_respects_the_rolling_window(
    conn: sqlite3.Connection,
) -> None:
    """窓は判定時刻からさかのぼる固定長（用語集「ローリングウィンドウ」）。"""
    repository = DecisionRepository(conn)
    repository.add(
        _audit_record(
            kind="policy_check",
            decision="allow",
            action="post",
            timestamp=FIXED_NOW - timedelta(hours=25),
        )
    )
    repository.add(
        _audit_record(
            kind="policy_check", decision="allow", action="post", timestamp=FIXED_NOW
        )
    )

    within_a_day = repository.count_allowed_actions(
        action="post", since=FIXED_NOW - timedelta(hours=24)
    )
    everything = repository.count_allowed_actions(
        action="post", since=FIXED_NOW - timedelta(days=7)
    )
    until_past = repository.count_allowed_actions(
        action="post",
        since=FIXED_NOW - timedelta(days=7),
        until=FIXED_NOW - timedelta(hours=1),
    )

    assert within_a_day == 1
    assert everything == 2
    assert until_past == 1
