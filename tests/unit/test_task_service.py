"""`core/task/service.py` の単体テスト（詳細設計 9.2 / 9.3）。

**遷移の可否を判定するのは `TaskService` だけである**（罠 D-T13）。ここでは
「表どおりに通す」「表に無いものを拒否し、DB を書き換えない」の両方を確認する。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from media_agent.core.db.connection import connect
from media_agent.core.db.migrations import ensure_schema
from media_agent.core.db.repositories import TaskRepository
from media_agent.core.task import TaskService, TaskStatus
from media_agent.core.task.service import UNKNOWN_ERROR
from media_agent.errors import DatabaseError, InvalidTaskTransitionError

FIXED_NOW = datetime(2026, 8, 24, 10, 0, 0, 123456, tzinfo=UTC)


@pytest.fixture()
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(tmp_path / "media-agent.db")
    ensure_schema(connection)
    yield connection
    connection.close()


@pytest.fixture()
def tasks(conn: sqlite3.Connection) -> TaskService:
    return TaskService(
        TaskRepository(conn, clock=lambda: FIXED_NOW), clock=lambda: FIXED_NOW
    )


def test_create_starts_from_pending(tasks: TaskService) -> None:
    """生成直後は `pending`。開始・終了時刻はまだ無い（詳細設計 9.2 の遷移1）。"""
    task = tasks.create(agent="echo", type="agent_run", input={"message": "hi"})

    assert task.status is TaskStatus.pending
    assert task.input == {"message": "hi"}
    assert task.created_at == FIXED_NOW
    assert task.started_at is None
    assert task.completed_at is None
    assert task.output is None
    assert task.error is None


def test_running_records_started_at(tasks: TaskService) -> None:
    """`pending` → `running` で `started_at` が入る（詳細設計 9.2 の遷移2）。"""
    task = tasks.create(agent="echo", type="agent_run", input={})

    running = tasks.transition(task.task_id, TaskStatus.running)

    assert running.started_at == FIXED_NOW
    assert running.completed_at is None


def test_completed_records_output_and_completed_at(tasks: TaskService) -> None:
    """`running` → `completed` で `output` と `completed_at` が入る（遷移4）。"""
    task = tasks.create(agent="echo", type="agent_run", input={})
    tasks.transition(task.task_id, TaskStatus.running)

    completed = tasks.transition(
        task.task_id, TaskStatus.completed, output={"message": "hi"}
    )

    assert completed.status is TaskStatus.completed
    assert completed.output == {"message": "hi"}
    assert completed.completed_at == FIXED_NOW


def test_failed_records_error_and_completed_at(tasks: TaskService) -> None:
    """`running` → `failed` で `error` と `completed_at` が入る（遷移5）。"""
    task = tasks.create(agent="fail", type="agent_run", input={})
    tasks.transition(task.task_id, TaskStatus.running)

    failed = tasks.transition(task.task_id, TaskStatus.failed, error="RuntimeError: x")

    assert failed.error == "RuntimeError: x"
    assert failed.completed_at == FIXED_NOW


def test_failed_without_error_gets_a_placeholder(tasks: TaskService) -> None:
    """`failed` なのに `error` が無ければ補う（詳細設計 9.3）。

    監査記録の `error` 項目が空になるのを防ぐため。
    """
    task = tasks.create(agent="fail", type="agent_run", input={})
    tasks.transition(task.task_id, TaskStatus.running)

    failed = tasks.transition(task.task_id, TaskStatus.failed)

    assert failed.error == UNKNOWN_ERROR


def test_completed_without_output_is_allowed(tasks: TaskService) -> None:
    """`completed` で `output` が無くてもよい（Agent が出力を返さないこともある）。"""
    task = tasks.create(agent="echo", type="agent_run", input={})
    tasks.transition(task.task_id, TaskStatus.running)

    completed = tasks.transition(task.task_id, TaskStatus.completed)

    assert completed.status is TaskStatus.completed
    assert completed.output is None


def test_pending_can_be_cancelled(tasks: TaskService) -> None:
    """`pending` → `cancelled` は許可され、終端時刻が入る（遷移3）。"""
    task = tasks.create(agent="echo", type="agent_run", input={})

    cancelled = tasks.transition(task.task_id, TaskStatus.cancelled)

    assert cancelled.status is TaskStatus.cancelled
    assert cancelled.completed_at == FIXED_NOW
    assert cancelled.started_at is None


#: 表に無い遷移（詳細設計 9.2 の6〜9行目）。到達させる経路と、要求する遷移先。
FORBIDDEN: tuple[tuple[tuple[TaskStatus, ...], TaskStatus], ...] = (
    ((), TaskStatus.completed),
    ((), TaskStatus.failed),
    ((), TaskStatus.pending),
    ((TaskStatus.running,), TaskStatus.cancelled),
    ((TaskStatus.running,), TaskStatus.running),
    ((TaskStatus.running, TaskStatus.completed), TaskStatus.running),
    ((TaskStatus.running, TaskStatus.failed), TaskStatus.running),
    ((TaskStatus.cancelled,), TaskStatus.running),
)


@pytest.mark.parametrize(("path", "target"), FORBIDDEN)
def test_forbidden_transition_is_rejected_before_writing(
    tasks: TaskService, path: tuple[TaskStatus, ...], target: TaskStatus
) -> None:
    """禁止された遷移は例外になり、**DB を書き換えない**（検査は書き込みより前）。"""
    task = tasks.create(agent="echo", type="agent_run", input={})
    for step in path:
        tasks.transition(task.task_id, step)
    before = tasks.get(task.task_id)

    with pytest.raises(InvalidTaskTransitionError) as excinfo:
        tasks.transition(task.task_id, target)

    message = str(excinfo.value)
    assert before.status.value in message
    assert target.value in message
    assert task.task_id in message
    assert tasks.get(task.task_id) == before


def test_transition_of_a_missing_task_is_a_database_error(tasks: TaskService) -> None:
    """存在しない `task_id` は `DatabaseError`（該当する行が無い）。"""
    with pytest.raises(DatabaseError, match="no-such-task"):
        tasks.transition("no-such-task", TaskStatus.running)


def test_get_of_a_missing_task_is_a_database_error(tasks: TaskService) -> None:
    with pytest.raises(DatabaseError, match="no-such-task"):
        tasks.get("no-such-task")


def test_list_is_ordered_by_creation_time_descending(
    conn: sqlite3.Connection,
) -> None:
    """一覧は作成時刻の降順（詳細設計 6.6 / 16.2）。"""
    moments = iter(
        [FIXED_NOW, FIXED_NOW + timedelta(minutes=1), FIXED_NOW + timedelta(minutes=2)]
    )
    service = TaskService(TaskRepository(conn, clock=lambda: next(moments)))
    first = service.create(agent="echo", type="agent_run", input={})
    second = service.create(agent="fail", type="agent_run", input={})
    third = service.create(agent="echo", type="agent_run", input={})

    listed = service.list()

    assert [task.task_id for task in listed] == [
        third.task_id,
        second.task_id,
        first.task_id,
    ]


def test_list_can_filter_by_status_and_limit(tasks: TaskService) -> None:
    kept = tasks.create(agent="echo", type="agent_run", input={})
    tasks.transition(kept.task_id, TaskStatus.cancelled)
    tasks.create(agent="echo", type="agent_run", input={})

    cancelled = tasks.list(status=TaskStatus.cancelled)

    assert [task.task_id for task in cancelled] == [kept.task_id]
    assert len(tasks.list(limit=1)) == 1


def test_counts_returns_every_status_key(tasks: TaskService) -> None:
    """`counts()` は5状態すべてのキーを返す（詳細設計 6.6 / 9.3）。

    キーが欠けると、呼び出し側が表示のたびに `get(..., 0)` を書くことになる。
    """
    task = tasks.create(agent="echo", type="agent_run", input={})
    tasks.transition(task.task_id, TaskStatus.running)

    counts = tasks.counts()

    assert set(counts) == set(TaskStatus)
    assert counts[TaskStatus.running] == 1
    assert counts[TaskStatus.completed] == 0
