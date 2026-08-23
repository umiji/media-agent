"""S-F: Agent 実行が Task として記録され、状態遷移が観測できる。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-003 完了条件3 S-F / 要件定義書5.2節（Task）・16節 |
| 期待値の正典 | 詳細設計 19章 S-F 行 → 詳細設計 9.2（許される状態遷移）/ 8.3（Runner の手順） |
| 経路 | 遷移違反は CLI から観測できないため公開 API で判定する（申し送り N-2 / 詳細設計 15.4） |
"""

from __future__ import annotations

from pathlib import Path

import pytest
from media_agent.core.task import TaskStatus
from media_agent.errors import InvalidTaskTransitionError

from tests.acceptance.expectations import (
    EXIT_OK,
    EXIT_RUNTIME_ERROR,
    TASK_STATUSES,
    CliInvoke,
    RuntimeStack,
    parse_json,
)

pytestmark = pytest.mark.acceptance


def test_successful_run_records_pending_running_completed(
    runtime_stack: RuntimeStack,
) -> None:
    """`echo` 実行後の Task は `completed` で、開始・終了時刻が残る（詳細設計 8.3 / 19章）。"""
    result = runtime_stack.runner.run("echo", {"message": "hi"})

    task = runtime_stack.tasks.get(result.task.task_id)
    assert task.status == TaskStatus.completed
    assert task.created_at is not None
    assert task.started_at is not None
    assert task.completed_at is not None
    assert task.output == {"message": "hi"}
    assert task.error is None
    assert task.is_terminal


def test_transitions_are_observable_step_by_step(runtime_stack: RuntimeStack) -> None:
    """`pending` → `running` → `completed` の各段階が観測できる（詳細設計 9.2 の 1・2・4）。"""
    created = runtime_stack.tasks.create(
        agent="echo", type="agent_run", input={"message": "hi"}
    )
    assert created.status == TaskStatus.pending
    assert created.started_at is None

    running = runtime_stack.tasks.transition(created.task_id, TaskStatus.running)
    assert running.status == TaskStatus.running
    assert running.started_at is not None
    assert running.completed_at is None

    completed = runtime_stack.tasks.transition(
        created.task_id, TaskStatus.completed, output={"message": "hi"}
    )
    assert completed.status == TaskStatus.completed
    assert completed.completed_at is not None


def test_pending_task_can_be_cancelled(runtime_stack: RuntimeStack) -> None:
    """`pending` → `cancelled` は許可され、終端時刻が入る（詳細設計 9.2 の 3）。"""
    created = runtime_stack.tasks.create(agent="echo", type="agent_run", input={})

    cancelled = runtime_stack.tasks.transition(created.task_id, TaskStatus.cancelled)

    assert cancelled.status == TaskStatus.cancelled
    assert cancelled.completed_at is not None


def test_failing_agent_marks_the_task_failed(runtime_stack: RuntimeStack) -> None:
    """`fail` を実行すると Task は `failed` になり、Runner は例外を送出しない。

    出所: 詳細設計 8.3 の手順7 / 8.4 / 19章 S-F 行。
    """
    result = runtime_stack.runner.run("fail")

    task = runtime_stack.tasks.get(result.task.task_id)
    assert task.status == TaskStatus.failed
    assert task.error is not None and task.error != ""
    assert task.completed_at is not None
    assert result.output is None
    assert result.error is not None


#: 9.2 の表に無い遷移（6〜9行目）。テストID / 到達させる経路 / 要求する遷移先。
FORBIDDEN_TRANSITIONS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("pending-to-completed", (), "completed"),
    ("pending-to-failed", (), "failed"),
    ("running-to-cancelled", ("running",), "cancelled"),
    ("running-to-running", ("running",), "running"),
    ("completed-to-running", ("running", "completed"), "running"),
    ("failed-to-running", ("running", "failed"), "running"),
    ("cancelled-to-running", ("cancelled",), "running"),
)


@pytest.mark.parametrize(
    ("label", "path", "target"),
    FORBIDDEN_TRANSITIONS,
    ids=[t[0] for t in FORBIDDEN_TRANSITIONS],
)
def test_forbidden_transitions_are_rejected_without_changing_the_task(
    runtime_stack: RuntimeStack, label: str, path: tuple[str, ...], target: str
) -> None:
    """9.2 の表に無い遷移は `InvalidTaskTransitionError` で拒否され、DB 上の状態が変わらない。"""
    task = runtime_stack.tasks.create(agent="echo", type="agent_run", input={})
    for step in path:
        runtime_stack.tasks.transition(task.task_id, TaskStatus(step))
    before = runtime_stack.tasks.get(task.task_id)

    with pytest.raises(InvalidTaskTransitionError) as excinfo:
        runtime_stack.tasks.transition(task.task_id, TaskStatus(target))

    message = str(excinfo.value)
    assert before.status.value in message
    assert target in message
    assert task.task_id in message

    after = runtime_stack.tasks.get(task.task_id)
    assert after.status == before.status
    assert after.completed_at == before.completed_at


def test_task_counts_cover_all_statuses(runtime_stack: RuntimeStack) -> None:
    """`counts()` は5状態すべてのキーを返す（詳細設計 6.6 / 9.3）。"""
    counts = runtime_stack.tasks.counts()

    assert {status.value for status in counts} == set(TASK_STATUSES)


def test_run_command_reports_failure_of_the_fail_agent(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """CLI からも失敗が観測できる。`fail` の実行は終了コード 1（詳細設計 15.1 / 15.2）。"""
    result = cli("run", "--agent", "fail", "--json", project=initialized_project)

    assert result.exit_code == EXIT_RUNTIME_ERROR, result.output
    payload = parse_json(result.stdout)
    assert payload["status"] == "failed"
    assert payload["error"]
    assert payload["output"] is None


def test_task_list_shows_recorded_tasks(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """実行した Task が `task list` から観測できる（詳細設計 16.2）。"""
    assert (
        cli("run", "--agent", "echo", project=initialized_project).exit_code == EXIT_OK
    )
    assert (
        cli("run", "--agent", "fail", project=initialized_project).exit_code != EXIT_OK
    )

    payload = parse_json(
        cli("task", "list", "--json", project=initialized_project).stdout
    )
    assert {task["status"] for task in payload["tasks"]} == {"completed", "failed"}

    filtered = parse_json(
        cli(
            "task", "list", "--status", "failed", "--json", project=initialized_project
        ).stdout
    )
    assert [task["agent"] for task in filtered["tasks"]] == ["fail"]
