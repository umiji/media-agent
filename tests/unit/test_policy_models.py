"""`core/policy/models.py` の単体テスト（詳細設計 10.2）。

**`outcome` と `reason_code` は独立した2軸である。** `reason_code` から `outcome` は
一意に決まるが、逆は決まらない。この一方向の対応が崩れると、「禁止」と「上限超過」を
`reason_code` で区別する根拠（10.3 の注記）が失われる。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from media_agent.core.policy import (
    OUTCOME_OF_REASON,
    PolicyDecision,
    PolicyOutcome,
    PolicyReasonCode,
    PolicyRequest,
)


def test_every_reason_code_maps_to_an_outcome() -> None:
    """理由から結果が必ず導ける（対応表に欠けがない）。"""
    assert set(OUTCOME_OF_REASON) == set(PolicyReasonCode)


def test_outcome_is_not_derivable_from_reason_in_reverse() -> None:
    """`deny` に複数の理由がある。だから2要素にしてある（詳細設計 10.2 / 10.3）。"""
    deny_reasons = {
        reason
        for reason, outcome in OUTCOME_OF_REASON.items()
        if outcome is PolicyOutcome.deny
    }
    assert {
        PolicyReasonCode.mode_disabled,
        PolicyReasonCode.limit_exceeded_per_day,
    } <= deny_reasons


def test_decision_of_derives_the_outcome() -> None:
    decision = PolicyDecision.of(
        PolicyReasonCode.limit_exceeded_per_day, "上限", limit=1, observed=1
    )

    assert decision.outcome is PolicyOutcome.deny
    assert decision.reason_code is PolicyReasonCode.limit_exceeded_per_day
    assert decision.detail == {"limit": 1, "observed": 1}


def test_decision_detail_defaults_to_an_empty_dict() -> None:
    assert PolicyDecision.of(PolicyReasonCode.mode_auto, "許可").detail == {}


def test_decision_is_frozen() -> None:
    decision = PolicyDecision.of(PolicyReasonCode.mode_auto, "許可")

    with pytest.raises(ValidationError):
        decision.outcome = PolicyOutcome.deny  # type: ignore[misc]


def test_request_defaults() -> None:
    """`requested_by` の既定は監査記録の `agent` 項目になる（詳細設計 11.3）。"""
    request = PolicyRequest(action="post")

    assert request.requested_by == "policy-engine"
    assert request.topic is None
    assert request.target_user is None
    assert request.task_id is None
    assert request.requested_at is None


def test_request_accepts_an_unknown_action_string() -> None:
    """未知の Action も**受け取れる**（`ActionName` に縛らない。詳細設計 10.2）。

    縛ると検証エラーになり、`unknown_action` として `deny` を返せなくなる。
    """
    assert PolicyRequest(action="follow").action == "follow"


def test_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        PolicyRequest(action="post", topics="ai")  # type: ignore[call-arg]


def test_request_is_frozen() -> None:
    request = PolicyRequest(action="post", requested_at=datetime.now(UTC))

    with pytest.raises(ValidationError):
        request.action = "reply"  # type: ignore[misc]
