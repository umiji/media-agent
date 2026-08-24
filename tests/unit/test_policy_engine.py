"""`core/policy/engine.py` の単体テスト（詳細設計 10.4〜10.6）。

受け入れテスト S-G が確認するのは 10.3 の4通りと主要な順序である。ここでは
**判定順序の全体**（10.4 の1〜9）と、上限の窓が**ローリング**であること（10.5）を確認する。
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from media_agent.core.config.models import Config
from media_agent.core.db.connection import connect
from media_agent.core.db.migrations import ensure_schema
from media_agent.core.db.repositories import DecisionRepository, TaskRepository
from media_agent.core.observability.audit import AuditRecorder
from media_agent.core.policy import (
    PolicyEngine,
    PolicyOutcome,
    PolicyReasonCode,
    PolicyRequest,
)

FIXED_NOW = datetime(2026, 8, 24, 10, 0, 0, 123456, tzinfo=UTC)


@pytest.fixture()
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect(tmp_path / "media-agent.db")
    ensure_schema(connection)
    yield connection
    connection.close()


@pytest.fixture()
def decisions(conn: sqlite3.Connection) -> DecisionRepository:
    return DecisionRepository(conn)


@pytest.fixture()
def engine_for(decisions: DecisionRepository, tmp_path: Path) -> Any:
    """設定セクションを与えて `PolicyEngine` を組み立てる。

    Policy Engine は Config を**受け取るだけ**であり、自分で `config.yaml` を読まない
    （順序制約 O-3）。ここでも読み込みは呼び出し側が行う。
    """

    def _build(**sections: Any) -> PolicyEngine:
        config = Config.model_validate(
            {"version": 1, "project": {"name": "sample-project"}, **sections}
        )
        audit = AuditRecorder(
            decisions=decisions,
            audit_path=tmp_path / "audit.jsonl",
            logger=logging.getLogger("test.policy"),
            clock=lambda: FIXED_NOW,
        )
        return PolicyEngine(
            config=config, decisions=decisions, audit=audit, clock=lambda: FIXED_NOW
        )

    return _build


def _pair(decision: Any) -> tuple[PolicyOutcome, PolicyReasonCode]:
    return (decision.outcome, decision.reason_code)


# -- 10.4 の判定順序 -------------------------------------------------------------------


def test_unknown_action_is_denied_first(engine_for: Any) -> None:
    """順1: 未知の Action。**例外にしない**（詳細設計 10.6）。"""
    engine = engine_for(actions={"post": {"mode": "auto"}})

    decision = engine.check(PolicyRequest(action="follow"))

    assert _pair(decision) == (PolicyOutcome.deny, PolicyReasonCode.unknown_action)
    assert decision.detail["action"] == "follow"
    assert "post" in decision.detail["known_actions"]


def test_disabled_beats_the_forbidden_topic(engine_for: Any) -> None:
    """順2 は順3 より先。どちらも `deny` だが理由が変わる。"""
    engine = engine_for(
        actions={"post": {"mode": "disabled"}}, limits={"forbidden_topics": ["crypto"]}
    )

    decision = engine.check(PolicyRequest(action="post", topic="crypto"))

    assert decision.reason_code is PolicyReasonCode.mode_disabled


def test_forbidden_topic_beats_the_daily_limit(engine_for: Any) -> None:
    """順3 は順5 より先。"""
    engine = engine_for(
        actions={"post": {"mode": "auto", "max_per_day": 0}},
        limits={"forbidden_topics": ["crypto"]},
    )

    decision = engine.check(PolicyRequest(action="post", topic="crypto"))

    assert decision.reason_code is PolicyReasonCode.topic_forbidden


def test_forbidden_user_beats_the_approval_switch(engine_for: Any) -> None:
    """順4 は順7 より先。「承認すれば禁止ユーザーへ送れる」設計にしない。"""
    engine = engine_for(
        automation={"require_approval": True},
        actions={"reply": {"mode": "auto"}},
        limits={"forbidden_users": ["@Spammer"]},
    )

    decision = engine.check(PolicyRequest(action="reply", target_user="SPAMMER"))

    assert _pair(decision) == (PolicyOutcome.deny, PolicyReasonCode.user_forbidden)


def test_daily_limit_beats_the_hourly_limit(engine_for: Any) -> None:
    """順5 は順6 より先（両方が上限に達していても `per_day` を返す）。"""
    engine = engine_for(
        actions={"post": {"mode": "auto", "max_per_day": 0, "max_per_hour": 0}}
    )

    decision = engine.check(PolicyRequest(action="post"))

    assert decision.reason_code is PolicyReasonCode.limit_exceeded_per_day
    assert decision.detail["window"] == "24h"


def test_action_hourly_limit_is_evaluated_before_the_global_one(
    engine_for: Any,
) -> None:
    """順6: Action 個別 → 全 Action 合計。`detail` には先に評価した個別の値が入る。"""
    engine = engine_for(
        actions={"post": {"mode": "auto", "max_per_hour": 0}},
        limits={"max_actions_per_hour": 0},
    )

    decision = engine.check(PolicyRequest(action="post"))

    assert decision.reason_code is PolicyReasonCode.limit_exceeded_per_hour
    assert decision.detail["scope"] == "action"
    assert decision.detail["limit"] == 0


def test_global_hourly_limit_applies_when_the_action_has_none(engine_for: Any) -> None:
    engine = engine_for(
        actions={"post": {"mode": "auto"}}, limits={"max_actions_per_hour": 0}
    )

    decision = engine.check(PolicyRequest(action="post"))

    assert decision.reason_code is PolicyReasonCode.limit_exceeded_per_hour
    assert decision.detail["scope"] == "all"


def test_global_approval_switch_beats_mode_auto(engine_for: Any) -> None:
    """順7 は順9 より先（`automation.require_approval` は `mode: auto` より優先）。"""
    engine = engine_for(
        automation={"require_approval": True}, actions={"post": {"mode": "auto"}}
    )

    assert _pair(engine.check(PolicyRequest(action="post"))) == (
        PolicyOutcome.require_approval,
        PolicyReasonCode.global_approval_required,
    )


def test_mode_approval_and_mode_auto(engine_for: Any) -> None:
    """順8・順9。"""
    engine = engine_for(
        actions={"reply": {"mode": "approval"}, "post": {"mode": "auto"}}
    )

    assert _pair(engine.check(PolicyRequest(action="reply"))) == (
        PolicyOutcome.require_approval,
        PolicyReasonCode.mode_approval,
    )
    assert _pair(engine.check(PolicyRequest(action="post"))) == (
        PolicyOutcome.allow,
        PolicyReasonCode.mode_auto,
    )


def test_defaults_apply_to_actions_that_are_not_written(engine_for: Any) -> None:
    """書かれていない Action は既定表で補う（詳細設計 5.2.5 / 5.3）。

    `like` の既定は `disabled` である。**暗黙に許可しない。**
    """
    engine = engine_for(actions={"post": {"mode": "auto"}})

    assert engine.check(PolicyRequest(action="like")).reason_code is (
        PolicyReasonCode.mode_disabled
    )


# -- 10.4 の3・4（一致判定）------------------------------------------------------------


@pytest.mark.parametrize("topic", ["crypto", "Crypto", " CRYPTO ", "cRyPtO"])
def test_topic_matching_ignores_case_and_surrounding_space(
    engine_for: Any, topic: str
) -> None:
    engine = engine_for(
        actions={"post": {"mode": "auto"}}, limits={"forbidden_topics": ["Crypto"]}
    )

    assert engine.check(PolicyRequest(action="post", topic=topic)).reason_code is (
        PolicyReasonCode.topic_forbidden
    )


@pytest.mark.parametrize("topic", ["cryptography", "crypt", "crypto currency", ""])
def test_topic_matching_is_exact(engine_for: Any, topic: str) -> None:
    """**完全一致**である（部分一致にしない。D-X2）。"""
    engine = engine_for(
        actions={"post": {"mode": "auto"}}, limits={"forbidden_topics": ["Crypto"]}
    )

    assert engine.check(PolicyRequest(action="post", topic=topic)).outcome is (
        PolicyOutcome.allow
    )


@pytest.mark.parametrize("user", ["spammer", "@spammer", " @Spammer ", "SPAMMER"])
def test_user_matching_ignores_a_leading_at_mark(engine_for: Any, user: str) -> None:
    engine = engine_for(
        actions={"reply": {"mode": "auto"}}, limits={"forbidden_users": ["@Spammer"]}
    )

    assert engine.check(
        PolicyRequest(action="reply", target_user=user)
    ).reason_code is (PolicyReasonCode.user_forbidden)


# -- 10.5 上限の数え方 -----------------------------------------------------------------


def test_allowed_checks_consume_the_daily_limit(engine_for: Any) -> None:
    """代理計数: `allow` と判定した回数が上限の入力になる（D-X1）。"""
    engine = engine_for(actions={"post": {"mode": "auto", "max_per_day": 2}})

    outcomes = [
        engine.check(PolicyRequest(action="post")).reason_code for _ in range(3)
    ]

    assert outcomes == [
        PolicyReasonCode.mode_auto,
        PolicyReasonCode.mode_auto,
        PolicyReasonCode.limit_exceeded_per_day,
    ]


def test_denied_checks_do_not_consume_the_limit(engine_for: Any) -> None:
    """数えるのは `allow` だけ（`deny` の記録は計数に入らない）。"""
    engine = engine_for(
        actions={
            "like": {"mode": "disabled"},
            "post": {"mode": "auto", "max_per_day": 1},
        }
    )

    for _ in range(3):
        engine.check(PolicyRequest(action="like"))

    assert engine.check(PolicyRequest(action="post")).outcome is PolicyOutcome.allow


def test_other_actions_do_not_consume_the_per_action_limit(engine_for: Any) -> None:
    """`max_per_day` は当該 Action だけを数える（詳細設計 10.5 / L-5）。"""
    engine = engine_for(
        actions={
            "post": {"mode": "auto", "max_per_day": 1},
            "reply": {"mode": "auto"},
        },
        limits={"max_actions_per_hour": None},
    )

    engine.check(PolicyRequest(action="reply"))

    assert engine.check(PolicyRequest(action="post")).outcome is PolicyOutcome.allow


def test_the_window_rolls_forward(engine_for: Any) -> None:
    """窓は**判定時刻からさかのぼる固定長**（ローリングウィンドウ。詳細設計 10.5）。

    カレンダー日（0時区切り）ではないので、25時間前の記録は数えられない。
    """
    engine = engine_for(actions={"post": {"mode": "auto", "max_per_day": 1}})
    old = FIXED_NOW - timedelta(hours=25)

    assert (
        engine.check(PolicyRequest(action="post", requested_at=old)).outcome
        is PolicyOutcome.allow
    )

    assert engine.check(PolicyRequest(action="post")).outcome is PolicyOutcome.allow


def test_a_record_inside_the_window_still_counts(engine_for: Any) -> None:
    engine = engine_for(actions={"post": {"mode": "auto", "max_per_day": 1}})
    recent = FIXED_NOW - timedelta(hours=23)

    engine.check(PolicyRequest(action="post", requested_at=recent))

    assert engine.check(PolicyRequest(action="post")).reason_code is (
        PolicyReasonCode.limit_exceeded_per_day
    )


def test_limit_detail_reports_the_observed_count(engine_for: Any) -> None:
    engine = engine_for(actions={"post": {"mode": "auto", "max_per_day": 1}})
    engine.check(PolicyRequest(action="post"))

    detail = engine.check(PolicyRequest(action="post")).detail

    assert detail["limit"] == 1
    assert detail["observed"] == 1
    assert detail["window"] == "24h"


# -- 10.6 記録 -------------------------------------------------------------------------


def test_check_records_through_the_audit_recorder(
    engine_for: Any, decisions: DecisionRepository, tmp_path: Path
) -> None:
    """記録は `AuditRecorder`（唯一の書き込み口）を通る（詳細設計 11.3）。"""
    engine = engine_for(actions={"post": {"mode": "auto"}})

    decision = engine.check(PolicyRequest(action="post", topic="ai", task_id=None))

    rows = decisions.list(kind="policy_check")
    assert len(rows) == 1
    assert rows[0].agent == "policy-engine"
    assert rows[0].action == "post"
    assert rows[0].decision == decision.outcome.value
    assert rows[0].reason.startswith(decision.reason_code.value)
    assert rows[0].timestamp == FIXED_NOW
    assert rows[0].error is None
    assert (tmp_path / "audit.jsonl").is_file()


def test_record_false_leaves_no_trace(
    engine_for: Any, decisions: DecisionRepository
) -> None:
    """`record=False` は記録も計数もしない（罠 D-T14。`doctor` が使う）。"""
    engine = engine_for(actions={"post": {"mode": "auto", "max_per_day": 1}})

    for _ in range(3):
        assert (
            engine.check(PolicyRequest(action="post"), record=False).outcome
            is PolicyOutcome.allow
        )

    assert decisions.list(kind="policy_check") == []
    assert engine.check(PolicyRequest(action="post")).outcome is PolicyOutcome.allow


def test_requested_at_is_used_as_the_record_timestamp(
    engine_for: Any, decisions: DecisionRepository
) -> None:
    """判定時刻と記録時刻を一致させる（計数の入力と判定の窓がずれないようにする）。"""
    engine = engine_for(actions={"post": {"mode": "auto"}})
    at = FIXED_NOW - timedelta(hours=5)

    engine.check(PolicyRequest(action="post", requested_at=at))

    assert decisions.list(kind="policy_check")[0].timestamp == at


def test_requested_by_and_task_id_are_carried_into_the_record(
    engine_for: Any, decisions: DecisionRepository, conn: sqlite3.Connection
) -> None:
    """`task_id` は既存の Task を指す必要がある（`decisions.task_id` は外部キー。L-1）。"""
    engine = engine_for(actions={"post": {"mode": "auto"}})
    task = TaskRepository(conn).add(agent="content", type="agent_run", input={})

    engine.check(
        PolicyRequest(action="post", requested_by="content-agent", task_id=task.task_id)
    )

    row = decisions.list(kind="policy_check")[0]
    assert row.agent == "content-agent"
    assert row.task_id == task.task_id


@pytest.mark.parametrize(
    "request_kwargs",
    [
        {"action": "post"},
        {"action": "follow"},
        {"action": "like"},
        {"action": "post", "topic": "crypto"},
        {"action": ""},
    ],
)
def test_check_never_raises(engine_for: Any, request_kwargs: dict[str, Any]) -> None:
    """判定は必ず `PolicyDecision` で表現する（詳細設計 10.6）。"""
    engine = engine_for(
        actions={"post": {"mode": "auto"}}, limits={"forbidden_topics": ["crypto"]}
    )

    decision = engine.check(PolicyRequest(**request_kwargs))

    assert decision.outcome in set(PolicyOutcome)
    assert isinstance(decision.detail, dict)
    assert decision.message
