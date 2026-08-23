"""S-G: Policy Engine の判定。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-003 完了条件3 S-G / 要件定義書5.3節・13節 |
| 期待値の正典 | 詳細設計 19章 S-G 行 → 詳細設計 10.3（4通り）/ 10.4（判定順序）/ 10.5（上限の数え方） |
| 経路 | **公開 API**。Policy を観測する CLI コマンドは Stage 0 に無い（申し送り N-2 / 詳細設計 15.4） |
| 判定の軸 | `(outcome, reason_code)` の組。`message` は人間向けであり判定対象にしない（10.2） |
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from media_agent.core.policy import PolicyOutcome, PolicyReasonCode, PolicyRequest

from tests.acceptance.expectations import base_config, build_policy_engine, write_config

pytestmark = pytest.mark.acceptance

PolicyFor = Callable[..., Any]


@pytest.fixture()
def policy_for(initialized_project: Path) -> PolicyFor:
    """設定セクションを与えて `PolicyEngine` を組み立てる。

    テストごとに新しい一時プロジェクト（＝新しい DB）を使う。上限判定は同じ DB 内の
    履歴に依存するため、プロジェクトを共有すると実行順序に依存した期待値になる（19章の補足）。
    """

    def _build(**sections: Any) -> Any:
        config = base_config(initialized_project.name)
        config.update(sections)
        write_config(initialized_project, config)
        return build_policy_engine(initialized_project)

    return _build


def outcome_of(decision: Any) -> tuple[PolicyOutcome, PolicyReasonCode]:
    return (decision.outcome, decision.reason_code)


# --------------------------------------------------------------------------------------
# 10.3 の4通り（完了条件3 が「少なくとも」と定める最低限）
# --------------------------------------------------------------------------------------


def test_allow_when_mode_is_auto(policy_for: PolicyFor) -> None:
    """許可: `mode: auto` かつ上限未達（詳細設計 10.3 の1行目）。"""
    engine = policy_for(
        automation={"require_approval": False}, actions={"post": {"mode": "auto"}}
    )

    decision = engine.check(PolicyRequest(action="post"))

    assert outcome_of(decision) == (PolicyOutcome.allow, PolicyReasonCode.mode_auto)


def test_require_approval_when_mode_is_approval(policy_for: PolicyFor) -> None:
    """承認が必要: `mode: approval`（詳細設計 10.3 の2行目）。"""
    engine = policy_for(actions={"reply": {"mode": "approval"}})

    decision = engine.check(PolicyRequest(action="reply"))

    assert outcome_of(decision) == (
        PolicyOutcome.require_approval,
        PolicyReasonCode.mode_approval,
    )


def test_deny_when_mode_is_disabled(policy_for: PolicyFor) -> None:
    """禁止: `mode: disabled`（詳細設計 10.3 の3行目）。"""
    engine = policy_for(actions={"like": {"mode": "disabled"}})

    decision = engine.check(PolicyRequest(action="like"))

    assert outcome_of(decision) == (PolicyOutcome.deny, PolicyReasonCode.mode_disabled)


def test_deny_when_daily_limit_is_exceeded(policy_for: PolicyFor) -> None:
    """上限超過: `max_per_day: 1` に対して2回目が拒否される（詳細設計 10.3 の4行目 / 10.5）。

    `check()` は既定で判定を記録し、その記録が上限判定の入力になる（代理計数）。
    """
    engine = policy_for(actions={"post": {"mode": "auto", "max_per_day": 1}})

    first = engine.check(PolicyRequest(action="post"))
    second = engine.check(PolicyRequest(action="post"))

    assert outcome_of(first) == (PolicyOutcome.allow, PolicyReasonCode.mode_auto)
    assert outcome_of(second) == (
        PolicyOutcome.deny,
        PolicyReasonCode.limit_exceeded_per_day,
    )


def test_deny_and_limit_exceeded_are_distinguishable(policy_for: PolicyFor) -> None:
    """「禁止」と「上限超過」はどちらも `deny` であり、`reason_code` でのみ区別できる。

    出所: 詳細設計 10.3 の注記 / 用語集「PolicyDecision」。
    """
    engine = policy_for(
        actions={
            "post": {"mode": "auto", "max_per_day": 0},
            "like": {"mode": "disabled"},
        }
    )

    limited = engine.check(PolicyRequest(action="post"))
    disabled = engine.check(PolicyRequest(action="like"))

    assert limited.outcome == disabled.outcome == PolicyOutcome.deny
    assert limited.reason_code != disabled.reason_code


# --------------------------------------------------------------------------------------
# 19章 S-G 行が追加で求めるもの
# --------------------------------------------------------------------------------------


def test_global_approval_switch_overrides_auto(policy_for: PolicyFor) -> None:
    """`automation.require_approval: true` は `mode: auto` より優先する（詳細設計 5.2.4 / 10.4 の7）。"""
    engine = policy_for(
        automation={"require_approval": True}, actions={"post": {"mode": "auto"}}
    )

    decision = engine.check(PolicyRequest(action="post"))

    assert outcome_of(decision) == (
        PolicyOutcome.require_approval,
        PolicyReasonCode.global_approval_required,
    )


# --------------------------------------------------------------------------------------
# 判定順序と、そのほかの reason_code（詳細設計 10.4）
# --------------------------------------------------------------------------------------


def test_deny_unknown_action(policy_for: PolicyFor) -> None:
    """未知の Action は例外ではなく `deny` で返る（詳細設計 10.4 の1 / 10.6）。"""
    engine = policy_for(actions={"post": {"mode": "auto"}})

    decision = engine.check(PolicyRequest(action="follow"))

    assert outcome_of(decision) == (PolicyOutcome.deny, PolicyReasonCode.unknown_action)


def test_deny_forbidden_topic_case_insensitively(policy_for: PolicyFor) -> None:
    """禁止トピックは大文字小文字を無視した完全一致で拒否する（詳細設計 10.4 の3 / 5.2.6）。"""
    engine = policy_for(
        actions={"post": {"mode": "auto"}}, limits={"forbidden_topics": ["Crypto"]}
    )

    decision = engine.check(PolicyRequest(action="post", topic="crypto"))

    assert outcome_of(decision) == (
        PolicyOutcome.deny,
        PolicyReasonCode.topic_forbidden,
    )


def test_allow_topic_that_is_not_forbidden(policy_for: PolicyFor) -> None:
    """禁止トピックの完全一致でなければ通す（詳細設計 5.2.6 / D-X2）。"""
    engine = policy_for(
        actions={"post": {"mode": "auto"}}, limits={"forbidden_topics": ["Crypto"]}
    )

    decision = engine.check(PolicyRequest(action="post", topic="cryptography"))

    assert outcome_of(decision) == (PolicyOutcome.allow, PolicyReasonCode.mode_auto)


def test_deny_forbidden_user_ignoring_at_mark(policy_for: PolicyFor) -> None:
    """禁止ユーザーは先頭の `@` を除去して比較する（詳細設計 10.4 の4 / 5.2.6）。"""
    engine = policy_for(
        actions={"reply": {"mode": "auto"}}, limits={"forbidden_users": ["@Spammer"]}
    )

    decision = engine.check(PolicyRequest(action="reply", target_user="spammer"))

    assert outcome_of(decision) == (PolicyOutcome.deny, PolicyReasonCode.user_forbidden)


def test_deny_when_hourly_limit_is_exceeded(policy_for: PolicyFor) -> None:
    """全 Action 合計の1時間上限も拒否理由になる（詳細設計 10.4 の6 / 5.2.6）。"""
    engine = policy_for(
        actions={"post": {"mode": "auto"}}, limits={"max_actions_per_hour": 1}
    )

    first = engine.check(PolicyRequest(action="post"))
    second = engine.check(PolicyRequest(action="post"))

    assert outcome_of(first) == (PolicyOutcome.allow, PolicyReasonCode.mode_auto)
    assert outcome_of(second) == (
        PolicyOutcome.deny,
        PolicyReasonCode.limit_exceeded_per_hour,
    )


def test_prohibition_is_evaluated_before_approval(policy_for: PolicyFor) -> None:
    """禁止（2〜6）は承認（7〜8）より先に評価される（詳細設計 10.4 の注記）。

    「承認すれば禁止トピックも通る」設計になっていないことを確認する。
    """
    engine = policy_for(
        automation={"require_approval": True},
        actions={"post": {"mode": "auto"}},
        limits={"forbidden_topics": ["crypto"]},
    )

    decision = engine.check(PolicyRequest(action="post", topic="crypto"))

    assert outcome_of(decision) == (
        PolicyOutcome.deny,
        PolicyReasonCode.topic_forbidden,
    )


def test_check_without_record_does_not_consume_the_limit(policy_for: PolicyFor) -> None:
    """`record=False` は計数に影響しない（詳細設計 10.6 / 罠 D-T14）。"""
    engine = policy_for(actions={"post": {"mode": "auto", "max_per_day": 1}})

    for _ in range(3):
        probe = engine.check(PolicyRequest(action="post"), record=False)
        assert outcome_of(probe) == (PolicyOutcome.allow, PolicyReasonCode.mode_auto)

    recorded = engine.check(PolicyRequest(action="post"))

    assert outcome_of(recorded) == (PolicyOutcome.allow, PolicyReasonCode.mode_auto)


def test_policy_engine_does_not_raise_on_denial(policy_for: PolicyFor) -> None:
    """判定は必ず `PolicyDecision` で表現される。例外を投げない（詳細設計 10.6）。"""
    engine = policy_for(actions={"like": {"mode": "disabled"}})

    decision = engine.check(PolicyRequest(action="like"))

    assert decision.outcome == PolicyOutcome.deny
    assert isinstance(decision.detail, dict)
