"""`core/observability/audit.py` の単体テスト（詳細設計 11.1・11.3・11.4）。

**受け入れテスト S-H は `run`（T-007）と Policy / Runtime（T-006）を経由するため、
本タスクの時点では実行できない。** ここでは S-H が判定する性質を、`AuditRecorder` の
公開 API に対して確認する。
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest

from media_agent.core.clock import to_iso
from media_agent.core.config.models import LogLevel
from media_agent.core.db.connection import connect
from media_agent.core.db.migrations import ensure_schema
from media_agent.core.db.repositories import DecisionRepository, TaskRepository
from media_agent.core.observability.audit import (
    AUDIT_KEYS,
    AUDIT_SCHEMA_VERSION,
    AuditRecord,
    AuditRecorder,
)
from media_agent.core.observability.log import (
    ROOT_LOGGER_NAME,
    get_logger,
    setup_logging,
)

FIXED_NOW = datetime(2026, 8, 23, 10, 0, 0, 123456, tzinfo=UTC)


@dataclass
class _Stack:
    conn: sqlite3.Connection
    decisions: DecisionRepository
    audit_path: Path
    recorder: AuditRecorder

    def records(self) -> list[dict[str, Any]]:
        lines = self.audit_path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]

    def task_id(self, agent: str = "echo") -> str:
        """`decisions.task_id` は `tasks` への外部キー。実在する Task を作る（詳細設計 6.4）。"""
        return (
            TaskRepository(self.conn)
            .add(agent=agent, type="agent_run", input={})
            .task_id
        )


@pytest.fixture()
def stack(tmp_path: Path) -> Iterator[_Stack]:
    conn = connect(tmp_path / "data" / "media-agent.db")
    ensure_schema(conn)
    decisions = DecisionRepository(conn)
    audit_path = tmp_path / "logs" / "audit.jsonl"
    recorder = AuditRecorder(
        decisions=decisions,
        audit_path=audit_path,
        logger=get_logger("test"),
        clock=lambda: FIXED_NOW,
    )
    yield _Stack(
        conn=conn, decisions=decisions, audit_path=audit_path, recorder=recorder
    )
    conn.close()


# --- Policy の型の代役（T-006 が実装する。ここでは構造だけを満たす）------------------


class _Outcome(StrEnum):
    ALLOW = "allow"


class _ReasonCode(StrEnum):
    MODE_AUTO = "mode_auto"


@dataclass(frozen=True)
class _Request:
    action: str = "post"
    topic: str | None = "ai"
    target_user: str | None = None
    requested_by: str = "policy-engine"
    task_id: str | None = None
    requested_at: datetime | None = None


@dataclass(frozen=True)
class _Decision:
    outcome: _Outcome = _Outcome.ALLOW
    reason_code: _ReasonCode = _ReasonCode.MODE_AUTO
    message: str = "auto モードのため許可しました"
    detail: dict[str, Any] = field(default_factory=dict)


# --- 9項目 -----------------------------------------------------------------------------


def test_agent_run_is_recorded_with_all_nine_items(stack: _Stack) -> None:
    """JSONL の1行が9キーとメタ情報を持つ（詳細設計 11.3）。"""
    task = TaskRepository(stack.conn).add(
        agent="echo", type="agent_run", input={"message": "hi"}
    )

    returned = stack.recorder.record_agent_run(
        agent="echo",
        agent_version=1,
        task_id=task.task_id,
        input={"message": "hi"},
        decision="completed",
        reason="echo は入力をそのまま返す",
        result={"message": "hi"},
    )

    record = stack.records()[-1]
    assert set(AUDIT_KEYS) <= set(record)
    assert record["timestamp"] == to_iso(FIXED_NOW)
    assert record["agent"] == "echo"
    assert record["task"] == task.task_id
    assert record["input"] == {"message": "hi"}
    assert record["decision"] == "completed"
    assert record["reason"]
    assert record["action"] is None
    assert record["result"] == {"message": "hi"}
    assert record["error"] is None
    assert record["kind"] == "agent_run"
    assert record["decision_id"] == returned.decision_id
    assert record["schema_version"] == AUDIT_SCHEMA_VERSION


def test_jsonl_keys_are_never_omitted(stack: _Stack) -> None:
    """値が無い項目は**キーを落とさず `null`**（詳細設計 11.3）。"""
    stack.recorder.record_agent_run(
        agent="echo",
        agent_version=1,
        task_id=stack.task_id(),
        input={},
        decision="completed",
        reason="理由",
    )

    record = stack.records()[-1]

    assert record["result"] is None
    assert record["error"] is None
    assert record["action"] is None


def test_record_is_persisted_in_the_decisions_table(stack: _Stack) -> None:
    """**正本は `decisions` テーブル**、JSONL はその写し（詳細設計 11.1）。"""
    returned = stack.recorder.record_agent_run(
        agent="echo",
        agent_version=1,
        task_id=stack.task_id(),
        input={"message": "hi"},
        decision="completed",
        reason="理由",
        result={"message": "hi"},
    )

    record = stack.records()[-1]
    stored = stack.decisions.get(returned.decision_id)

    assert stored is not None
    assert stored.decision_id == record["decision_id"]
    assert stored.agent == record["agent"]
    assert stored.decision == record["decision"]
    assert stored.reason == record["reason"]
    assert to_iso(stored.timestamp) == record["timestamp"]
    assert stored.input == record["input"]
    assert stored.result == record["result"]


def test_jsonl_is_written_as_readable_sorted_json(stack: _Stack) -> None:
    """`ensure_ascii=False` / `sort_keys=True`（罠 D-T12。再現性のため）。"""
    stack.recorder.record_agent_run(
        agent="echo",
        agent_version=1,
        task_id=stack.task_id(),
        input={"b": 2, "a": "日本語"},
        decision="completed",
        reason="理由",
    )

    line = stack.audit_path.read_text(encoding="utf-8").splitlines()[-1]

    assert "日本語" in line
    assert line.index('"agent"') < line.index('"decision"') < line.index('"timestamp"')
    assert line.index('"a"') < line.index('"b"')


def test_records_are_appended_not_rotated(stack: _Stack) -> None:
    """追記専用（詳細設計 11.1。監査記録の欠落を許容しない）。"""
    for _ in range(3):
        stack.recorder.record_agent_run(
            agent="echo",
            agent_version=1,
            task_id=stack.task_id(),
            input={},
            decision="completed",
            reason="理由",
        )

    assert len(stack.records()) == 3
    assert len({record["decision_id"] for record in stack.records()}) == 3


# --- 失敗の記録 -------------------------------------------------------------------------


def test_failed_run_is_recorded_as_an_error_without_traceback(stack: _Stack) -> None:
    """`decision == "error"`、`error` は1行（詳細設計 11.1 / 11.3）。"""
    stack.recorder.record_agent_run(
        agent="fail",
        agent_version=1,
        task_id=stack.task_id("fail"),
        input={},
        decision="error",
        reason="RuntimeError: 意図的な失敗",
        result=None,
        error="RuntimeError: 意図的な失敗\nTraceback (most recent call last):\n  ...",
    )

    record = stack.records()[-1]

    assert record["decision"] == "error"
    assert record["error"] is not None and record["error"] != ""
    assert record["error"].count("\n") == 0
    assert record["result"] is None


# --- 運用ログとの別物性 ------------------------------------------------------------------


def test_audit_is_not_suppressed_by_log_level(stack: _Stack, tmp_path: Path) -> None:
    """**監査記録は `logging.level` で消えない**（詳細設計 11.1 / 完了条件6）。"""
    log_path = tmp_path / "logs" / "media-agent.log"
    task_id = stack.task_id()
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    saved = list(logger.handlers)
    logger.handlers = []
    try:
        setup_logging(level=LogLevel.ERROR, log_path=log_path)
        stack.recorder.record_agent_run(
            agent="echo",
            agent_version=1,
            task_id=task_id,
            input={},
            decision="completed",
            reason="理由",
        )
    finally:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()
        logger.handlers = saved

    assert len(stack.records()) == 1
    assert stack.decisions.list() != []


def test_audit_file_is_not_the_log_file(stack: _Stack, tmp_path: Path) -> None:
    """出力先が別である（詳細設計 11.1 の表）。"""
    stack.recorder.record_agent_run(
        agent="echo",
        agent_version=1,
        task_id=stack.task_id(),
        input={},
        decision="completed",
        reason="理由",
    )

    assert stack.audit_path.name == "audit.jsonl"
    assert stack.audit_path != tmp_path / "logs" / "media-agent.log"
    assert stack.audit_path.is_file()


# --- 秘密値のマスク ----------------------------------------------------------------------


def test_secret_looking_keys_are_masked_in_both_destinations(stack: _Stack) -> None:
    """マスクは**唯一の書き込み口**で一度だけ行う（詳細設計 11.4）。"""
    returned = stack.recorder.record_agent_run(
        agent="echo",
        agent_version=1,
        task_id=stack.task_id(),
        input={"api_key": "s3cret-value", "message": "hi"},
        decision="completed",
        reason="理由",
        result={"nested": {"token": "s3cret-value"}},
    )

    record = stack.records()[-1]
    stored = stack.decisions.get(returned.decision_id)

    assert record["input"]["api_key"] == "***"
    assert record["input"]["message"] == "hi"
    assert record["result"]["nested"]["token"] == "***"
    assert "s3cret-value" not in stack.audit_path.read_text(encoding="utf-8")
    assert stored is not None and stored.input["api_key"] == "***"
    assert returned.input["api_key"] == "***"


# --- Policy の記録 -----------------------------------------------------------------------


def test_policy_check_is_recorded_with_its_reason_code(stack: _Stack) -> None:
    """`reason` は `"<reason_code>: <message>"`（詳細設計 11.3 の種別ごとの値の入れ方）。"""
    request = _Request(task_id=stack.task_id())
    decision = _Decision(detail={"limit": 3, "observed": 1})

    stack.recorder.record_policy_check(request=request, decision=decision)

    record = stack.records()[-1]
    assert set(AUDIT_KEYS) <= set(record)
    assert record["kind"] == "policy_check"
    assert record["agent"] == "policy-engine"
    assert record["task"] == request.task_id
    assert record["action"] == "post"
    assert record["decision"] == "allow"
    assert record["reason"].startswith("mode_auto")
    assert record["input"] == {"action": "post", "topic": "ai", "target_user": None}
    assert record["result"] == {"limit": 3, "observed": 1}
    assert record["error"] is None


def test_policy_check_uses_the_requested_time_when_given(stack: _Stack) -> None:
    """`requested_at` があればそれを使う（無ければ `clock()`）。"""
    requested_at = datetime(2026, 1, 1, tzinfo=UTC)

    stack.recorder.record_policy_check(
        request=_Request(requested_at=requested_at), decision=_Decision()
    )

    assert stack.records()[-1]["timestamp"] == to_iso(requested_at)


def test_policy_check_records_are_counted_as_the_limit_input(stack: _Stack) -> None:
    """記録が上限判定の入力になる（詳細設計 10.5 の代理計数）。"""
    stack.recorder.record_policy_check(request=_Request(), decision=_Decision())

    counted = stack.decisions.count_allowed_actions(
        action="post", since=datetime(2026, 1, 1, tzinfo=UTC)
    )

    assert counted == 1


# --- 失敗時の扱い -------------------------------------------------------------------------


def test_jsonl_failure_is_logged_but_does_not_raise(
    stack: _Stack, caplog: pytest.LogCaptureFixture
) -> None:
    """写しが書けなくても実行を止めない（詳細設計 11.3 の手順3。正本は残っている）。"""
    stack.audit_path.parent.mkdir(parents=True, exist_ok=True)
    stack.audit_path.mkdir()  # ファイルとして開けなくする

    task_id = stack.task_id()
    with caplog.at_level(logging.ERROR, logger=f"{ROOT_LOGGER_NAME}.test"):
        returned = stack.recorder.record_agent_run(
            agent="echo",
            agent_version=1,
            task_id=task_id,
            input={},
            decision="completed",
            reason="理由",
        )

    assert stack.decisions.get(returned.decision_id) is not None
    assert any("audit_jsonl_write_failed" in message for message in caplog.messages)


def test_database_failure_raises(stack: _Stack) -> None:
    """正本が書けないなら例外を送出する（詳細設計 11.3 の手順4）。"""
    task_id = stack.task_id()
    stack.conn.close()

    with pytest.raises(sqlite3.Error):
        stack.recorder.record_agent_run(
            agent="echo",
            agent_version=1,
            task_id=task_id,
            input={},
            decision="completed",
            reason="理由",
        )


def test_record_is_the_single_entry_point(stack: _Stack) -> None:
    """`record()` を通せば、どの経路でも同じ加工（マスク・1行化）が効く。"""
    returned = stack.recorder.record(
        AuditRecord(
            timestamp=FIXED_NOW,
            agent="custom",
            task=None,
            input={"password": "p"},
            decision="allow",
            reason="複数行\nの理由",
            action=None,
            result=None,
            error=None,
            kind="agent_run",
        )
    )

    assert returned.input == {"password": "***"}
    assert returned.reason == "複数行 の理由"
    assert stack.records()[-1]["reason"] == "複数行 の理由"
