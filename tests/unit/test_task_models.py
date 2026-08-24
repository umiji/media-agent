"""`core/task/models.py` の単体テスト（詳細設計 9.1 / 9.2）。

遷移表そのものの性質（到達可能性・終端・自己遷移の禁止）を、`TaskService` を通さずに
確認する。**表が壊れていれば、Service のテストより先にここが落ちる**ようにしておく。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from media_agent.core.db.models import TaskRow
from media_agent.core.task import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    Task,
    TaskStatus,
)

FIXED_NOW = datetime(2026, 8, 24, 10, 0, 0, 123456, tzinfo=UTC)


def test_task_status_values_match_the_db_check_constraint() -> None:
    """`TaskStatus` の値は `tasks.status` の値域と一致する（詳細設計 6.4 / 9.1）。"""
    from media_agent.core.db.repositories import TASK_STATUSES

    assert {status.value for status in TaskStatus} == set(TASK_STATUSES)


def test_allowed_transitions_covers_every_status() -> None:
    """遷移表は5状態すべてをキーに持つ（欠けたキーは `KeyError` になる）。"""
    assert set(ALLOWED_TRANSITIONS) == set(TaskStatus)


def test_terminal_statuses_have_no_outgoing_transition() -> None:
    """終端からの遷移はすべて禁止（詳細設計 9.2 の8行目）。"""
    for status in TERMINAL_STATUSES:
        assert ALLOWED_TRANSITIONS[status] == frozenset()


def test_no_self_transition_is_allowed() -> None:
    """同じ状態への遷移は禁止（詳細設計 9.2 の9行目）。"""
    for status, targets in ALLOWED_TRANSITIONS.items():
        assert status not in targets


def test_running_to_cancelled_is_forbidden_in_stage_0() -> None:
    """`running` → `cancelled` は Stage 0 では禁止（詳細設計 9.2 / D-X3）。

    同期実行の Agent を中断する手段が無いため、許すと「`cancelled` と記録されて
    いるのに Agent は最後まで動いた」状態を作れてしまう。
    """
    assert TaskStatus.cancelled not in ALLOWED_TRANSITIONS[TaskStatus.running]
    assert ALLOWED_TRANSITIONS[TaskStatus.running] == frozenset(
        {TaskStatus.completed, TaskStatus.failed}
    )


def test_every_status_is_reachable_from_pending() -> None:
    """到達不能な状態が無い（停止条件「到達不能な状態または矛盾がある」の確認）。"""
    reached = {TaskStatus.pending}
    frontier = [TaskStatus.pending]
    while frontier:
        for target in ALLOWED_TRANSITIONS[frontier.pop()]:
            if target not in reached:
                reached.add(target)
                frontier.append(target)
    assert reached == set(TaskStatus)


def test_allowed_transitions_is_read_only() -> None:
    """遷移表は書き換えられない（呼び出し側が実行時に緩められないようにする）。"""
    with pytest.raises(TypeError):
        ALLOWED_TRANSITIONS[TaskStatus.completed] = frozenset()  # type: ignore[index]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (TaskStatus.pending, False),
        (TaskStatus.running, False),
        (TaskStatus.completed, True),
        (TaskStatus.failed, True),
        (TaskStatus.cancelled, True),
    ],
)
def test_is_terminal(status: TaskStatus, expected: bool) -> None:
    task = Task(
        task_id="t-1",
        agent="echo",
        type="agent_run",
        status=status,
        created_at=FIXED_NOW,
    )
    assert task.is_terminal is expected


def test_task_is_frozen() -> None:
    """`Task` は不変（遷移は新しい `Task` を返す）。"""
    task = Task(
        task_id="t-1",
        agent="echo",
        type="agent_run",
        status=TaskStatus.pending,
        created_at=FIXED_NOW,
    )
    with pytest.raises(Exception, match="frozen"):
        task.status = TaskStatus.running  # type: ignore[misc]


def test_from_row_converts_status_to_the_enum() -> None:
    """`TaskRow.status`（`str`）を `TaskStatus` へ変換する。"""
    row = TaskRow(
        task_id="t-1",
        agent="echo",
        type="agent_run",
        status="completed",
        input={"message": "hi"},
        output={"message": "hi"},
        error=None,
        created_at=FIXED_NOW,
        started_at=FIXED_NOW,
        completed_at=FIXED_NOW,
    )

    task = Task.from_row(row)

    assert task.status is TaskStatus.completed
    assert task.is_terminal
    assert task.input == {"message": "hi"}


def test_from_row_rejects_a_status_outside_the_domain() -> None:
    """値域の外の `status` は**読み出し時点で**分かる（DB 由来の値を素通しさせない）。"""
    row = TaskRow(
        task_id="t-1",
        agent="echo",
        type="agent_run",
        status="zombie",
        input={},
        output=None,
        error=None,
        created_at=FIXED_NOW,
        started_at=None,
        completed_at=None,
    )

    with pytest.raises(ValueError, match="zombie"):
        Task.from_row(row)
