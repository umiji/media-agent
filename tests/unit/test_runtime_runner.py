"""`core/runtime/runner.py` の単体テスト（詳細設計 8.3）。

確認したい性質:

- 手順の**順序**（Task を進めてから記録する）。S-F / S-H の期待値がこの順序に依存する
- **Agent の例外を外へ漏らさない**（T-006 完了条件2）。ただし `BaseException` は漏らす
- 監査記録が `AuditRecorder`（唯一の書き込み口）を通ること。新しい記録機構を作らない
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import pytest

from media_agent.agents.builtin import build_default_registry
from media_agent.core.config.models import Config
from media_agent.core.db.connection import connect
from media_agent.core.db.migrations import ensure_schema
from media_agent.core.db.repositories import DecisionRepository, TaskRepository
from media_agent.core.observability.audit import AuditRecorder
from media_agent.core.runtime import (
    Agent,
    AgentContext,
    AgentInput,
    AgentOutput,
    AgentRegistry,
    AgentRunner,
)
from media_agent.core.runtime.runner import format_error
from media_agent.core.task import TaskService, TaskStatus
from media_agent.errors import AgentNotFoundError

FIXED_NOW = datetime(2026, 8, 24, 10, 0, 0, 123456, tzinfo=UTC)


class _CapturingAgent(Agent):
    """`AgentContext` と `AgentInput` に何が渡ったかを記録する。"""

    name: ClassVar[str] = "capture"
    version: ClassVar[int] = 1
    description: ClassVar[str] = "文脈と入力を控える"

    def __init__(self) -> None:
        self.seen_input: AgentInput | None = None
        self.seen_ctx: AgentContext | None = None

    def run(self, input: AgentInput, ctx: AgentContext) -> AgentOutput:
        self.seen_input = input
        self.seen_ctx = ctx
        return AgentOutput(payload={"seen": True}, decision="captured", reason="控えた")


class _BoomAgent(Agent):
    name: ClassVar[str] = "boom"
    version: ClassVar[int] = 1
    description: ClassVar[str] = "複数行のメッセージで失敗する"

    def run(self, input: AgentInput, ctx: AgentContext) -> AgentOutput:
        raise ValueError("1行目\n2行目")


class _InterruptedAgent(Agent):
    name: ClassVar[str] = "interrupted"
    version: ClassVar[int] = 1
    description: ClassVar[str] = "BaseException を投げる"

    def run(self, input: AgentInput, ctx: AgentContext) -> AgentOutput:
        raise KeyboardInterrupt


@dataclass
class _SpyRecorder:
    """記録された時点の Task 状態を控える偽の記録先（D-O6 が想定する差し込み）。"""

    tasks: TaskService
    calls: list[dict[str, Any]] = field(default_factory=list)

    def record_agent_run(self, **kwargs: Any) -> None:
        self.calls.append(
            {**kwargs, "status_at_record": self.tasks.get(kwargs["task_id"]).status}
        )


@pytest.fixture()
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(tmp_path / "media-agent.db")
    ensure_schema(connection)
    yield connection
    connection.close()


@pytest.fixture()
def tasks(conn: sqlite3.Connection) -> TaskService:
    return TaskService(TaskRepository(conn))


@pytest.fixture()
def audit(conn: sqlite3.Connection, tmp_path: Path) -> AuditRecorder:
    return AuditRecorder(
        decisions=DecisionRepository(conn),
        audit_path=tmp_path / "audit.jsonl",
        logger=logging.getLogger("test.audit"),
        clock=lambda: FIXED_NOW,
    )


def _config() -> Config:
    return Config.model_validate({"version": 1, "project": {"name": "sample-project"}})


def _runner(
    tasks: TaskService,
    audit: Any,
    tmp_path: Path,
    registry: AgentRegistry | None = None,
    logger: logging.Logger | None = None,
) -> AgentRunner:
    return AgentRunner(
        registry=registry if registry is not None else build_default_registry(),
        tasks=tasks,
        audit=audit,
        logger=logger if logger is not None else logging.getLogger("test.runner"),
        config=_config(),
        project_root=tmp_path,
    )


def test_run_returns_the_agent_output(
    tasks: TaskService, audit: AuditRecorder, tmp_path: Path
) -> None:
    result = _runner(tasks, audit, tmp_path).run("echo", {"message": "hi"})

    assert result.output is not None
    assert result.output.payload == {"message": "hi"}
    assert result.error is None
    assert result.task.status is TaskStatus.completed


def test_unknown_agent_does_not_create_a_task(
    tasks: TaskService, audit: AuditRecorder, tmp_path: Path
) -> None:
    """手順1で失敗したら **Task を作らない**（詳細設計 8.3）。"""
    with pytest.raises(AgentNotFoundError):
        _runner(tasks, audit, tmp_path).run("no-such-agent")

    assert tasks.list() == []


def test_agent_receives_the_input_and_the_context(
    tasks: TaskService, audit: AuditRecorder, tmp_path: Path
) -> None:
    """Agent には `AgentInput` と `AgentContext` だけを渡す（品質基準 Q9）。"""
    agent = _CapturingAgent()
    registry = AgentRegistry()
    registry.register(agent)

    result = _runner(tasks, audit, tmp_path, registry).run("capture", {"a": 1})

    assert agent.seen_input is not None
    assert agent.seen_input.payload == {"a": 1}
    assert agent.seen_ctx is not None
    assert agent.seen_ctx.task_id == result.task.task_id
    assert agent.seen_ctx.project_root == tmp_path
    assert agent.seen_ctx.config == _config()


def test_agent_cannot_mutate_the_stored_input(
    tasks: TaskService, audit: AuditRecorder, tmp_path: Path
) -> None:
    """呼び出し側の辞書をそのまま握らない（実行後の書き換えが Task に波及しない）。"""
    payload = {"message": "hi"}
    runner = _runner(tasks, audit, tmp_path)

    result = runner.run("echo", payload)
    payload["message"] = "changed"

    assert tasks.get(result.task.task_id).input == {"message": "hi"}


def test_failing_agent_does_not_raise(
    tasks: TaskService, audit: AuditRecorder, tmp_path: Path
) -> None:
    """例外を捕捉し、`failed` の `TaskRunResult` を返す（T-006 完了条件2）。"""
    result = _runner(tasks, audit, tmp_path).run("fail")

    assert result.task.status is TaskStatus.failed
    assert result.output is None
    assert result.error is not None
    assert result.error.startswith("AgentFailedForVerificationError: ")


def test_failure_message_is_a_single_line(
    tasks: TaskService, audit: AuditRecorder, tmp_path: Path
) -> None:
    """`error` は1行（監査記録にトレースバックを出さない。詳細設計 11.1）。"""
    registry = AgentRegistry()
    registry.register(_BoomAgent())

    result = _runner(tasks, audit, tmp_path, registry).run("boom")

    assert result.error == "ValueError: 1行目 2行目"
    assert tasks.get(result.task.task_id).error == "ValueError: 1行目 2行目"


def test_base_exception_is_not_swallowed(
    tasks: TaskService, audit: AuditRecorder, tmp_path: Path
) -> None:
    """`KeyboardInterrupt` / `SystemExit` は捕捉しない（利用者の中断を握り潰さない）。"""
    registry = AgentRegistry()
    registry.register(_InterruptedAgent())

    with pytest.raises(KeyboardInterrupt):
        _runner(tasks, audit, tmp_path, registry).run("interrupted")


def test_audit_is_recorded_after_the_task_reaches_its_terminal_state(
    tasks: TaskService, tmp_path: Path
) -> None:
    """記録は**遷移のあと**（詳細設計 8.3 の手順6・7）。

    順序が逆だと、監査記録の時点の Task 状態が `running` になり、
    `decisions.task_id` の外部キー（申し送り L-1）とあわせて実態と食い違う。
    """
    spy = _SpyRecorder(tasks=tasks)
    runner = _runner(tasks, spy, tmp_path)

    runner.run("echo", {"message": "hi"})
    runner.run("fail")

    assert [call["status_at_record"] for call in spy.calls] == [
        TaskStatus.completed,
        TaskStatus.failed,
    ]


def test_audit_arguments_follow_the_kind_table(
    tasks: TaskService, tmp_path: Path
) -> None:
    """`kind="agent_run"` の値の入れ方（詳細設計 11.3 の表）。"""
    spy = _SpyRecorder(tasks=tasks)
    runner = _runner(tasks, spy, tmp_path)

    runner.run("echo", {"message": "hi"})
    runner.run("fail")

    success, failure = spy.calls
    assert success["agent"] == "echo"
    assert success["input"] == {"message": "hi"}
    assert success["decision"] == "echo"
    assert success["reason"]
    assert success["result"] == {"message": "hi"}
    assert success["error"] is None

    assert failure["decision"] == "error"
    assert failure["result"] is None
    assert failure["error"] == failure["reason"]
    assert failure["error"] is not None


def test_run_is_persisted_through_the_audit_recorder(
    conn: sqlite3.Connection, tasks: TaskService, audit: AuditRecorder, tmp_path: Path
) -> None:
    """記録は `AuditRecorder` を通り、`decisions` と `audit.jsonl` の両方に残る。

    **新しい記録機構を作らない**（T-006 完了条件3）。
    """
    result = _runner(tasks, audit, tmp_path).run("echo", {"message": "hi"})

    rows = DecisionRepository(conn).list(task_id=result.task.task_id)
    assert len(rows) == 1
    assert rows[0].kind == "agent_run"
    assert rows[0].agent == "echo"
    assert (tmp_path / "audit.jsonl").read_text(encoding="utf-8").count("\n") == 1


def test_run_is_visible_from_another_connection(
    conn: sqlite3.Connection, tasks: TaskService, audit: AuditRecorder, tmp_path: Path
) -> None:
    """実行の結果は**別接続からも見える**（申し送り K-5）。

    `DecisionRepository.add` がコミットする（L-2）ため、記録の時点で Task の更新も
    確定する。Runner が「遷移 → 記録」の順である前提に依存している。
    """
    result = _runner(tasks, audit, tmp_path).run("echo")

    other = connect(tmp_path / "media-agent.db")
    try:
        rows = other.execute(
            "SELECT status FROM tasks WHERE task_id = ?", (result.task.task_id,)
        ).fetchall()
    finally:
        other.close()
    assert [row["status"] for row in rows] == ["completed"]


def test_task_type_defaults_to_agent_run(
    tasks: TaskService, audit: AuditRecorder, tmp_path: Path
) -> None:
    result = _runner(tasks, audit, tmp_path).run("echo")

    assert result.task.type == "agent_run"
    assert (
        _runner(tasks, audit, tmp_path).run("echo", task_type="probe").task.type
        == "probe"
    )


def test_operational_log_carries_key_value_pairs_without_the_payload(
    tasks: TaskService,
    audit: AuditRecorder,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """運用ログは `key=value` で追跡できる。**payload は出さない**（詳細設計 11.2 / 11.4）。"""
    logger = logging.getLogger("test.runner.log")
    with caplog.at_level(logging.DEBUG, logger=logger.name):
        result = _runner(tasks, audit, tmp_path, logger=logger).run(
            "echo", {"api_key": "s3cret-value"}
        )

    text = caplog.text
    assert f"agent=echo task={result.task.task_id} started" in text
    assert "completed" in text
    assert "s3cret-value" not in text


def test_traceback_goes_to_the_operational_log_only(
    tasks: TaskService,
    audit: AuditRecorder,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """トレースバックは運用ログにだけ出す（詳細設計 8.3 の手順7-3 / 11.1）。"""
    logger = logging.getLogger("test.runner.traceback")
    with caplog.at_level(logging.ERROR, logger=logger.name):
        _runner(tasks, audit, tmp_path, logger=logger).run("fail")

    assert "Traceback (most recent call last)" in caplog.text
    audit_text = (tmp_path / "audit.jsonl").read_text(encoding="utf-8")
    assert "Traceback" not in audit_text


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (ValueError("壊れた"), "ValueError: 壊れた"),
        (ValueError(""), "ValueError"),
        (ValueError("1行目\n2行目"), "ValueError: 1行目 2行目"),
    ],
)
def test_format_error(exc: Exception, expected: str) -> None:
    assert format_error(exc) == expected
