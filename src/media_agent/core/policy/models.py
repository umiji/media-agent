"""Policy の型（詳細設計 10.2）。

**`outcome` と `reason_code` は独立した2軸である**（用語集「PolicyDecision」）。
`outcome` は「どうするか」、`reason_code` は「なぜか」。`reason_code` から `outcome` は
一意に決まるが、逆は決まらない — 「禁止」と「上限超過」はどちらも `deny` であり、
`reason_code` でしか区別できない。
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "OUTCOME_OF_REASON",
    "PolicyDecision",
    "PolicyOutcome",
    "PolicyReasonCode",
    "PolicyRequest",
]

#: `PolicyRequest.requested_by` の既定（詳細設計 10.2）。監査記録の `agent` 項目になる。
DEFAULT_REQUESTED_BY = "policy-engine"


class PolicyOutcome(StrEnum):
    """判定の結果（詳細設計 10.2）。「どうするか」の軸。"""

    allow = "allow"
    require_approval = "require_approval"
    deny = "deny"


class PolicyReasonCode(StrEnum):
    """判定の理由（詳細設計 10.2）。「なぜか」の軸。"""

    mode_auto = "mode_auto"
    mode_approval = "mode_approval"
    global_approval_required = "global_approval_required"
    mode_disabled = "mode_disabled"
    limit_exceeded_per_day = "limit_exceeded_per_day"
    limit_exceeded_per_hour = "limit_exceeded_per_hour"
    topic_forbidden = "topic_forbidden"
    user_forbidden = "user_forbidden"
    unknown_action = "unknown_action"


#: `reason_code` → `outcome` の対応（詳細設計 10.2 の右側の注記）。
#: **この対応表を1箇所に持つことで、理由と結果の食い違いを構造的に防ぐ。**
OUTCOME_OF_REASON: dict[PolicyReasonCode, PolicyOutcome] = {
    PolicyReasonCode.mode_auto: PolicyOutcome.allow,
    PolicyReasonCode.mode_approval: PolicyOutcome.require_approval,
    PolicyReasonCode.global_approval_required: PolicyOutcome.require_approval,
    PolicyReasonCode.mode_disabled: PolicyOutcome.deny,
    PolicyReasonCode.limit_exceeded_per_day: PolicyOutcome.deny,
    PolicyReasonCode.limit_exceeded_per_hour: PolicyOutcome.deny,
    PolicyReasonCode.topic_forbidden: PolicyOutcome.deny,
    PolicyReasonCode.user_forbidden: PolicyOutcome.deny,
    PolicyReasonCode.unknown_action: PolicyOutcome.deny,
}


class PolicyRequest(BaseModel):
    """Policy Check の要求（詳細設計 10.2）。

    `action` は**未知の文字列も受け取る**。`ActionName` に縛ると、未知の Action が
    検証エラーになり、`unknown_action` として `deny` を返せなくなる（10.4 の1）。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: str
    topic: str | None = None
    target_user: str | None = None
    requested_by: str = DEFAULT_REQUESTED_BY
    task_id: str | None = None
    requested_at: datetime | None = None


class PolicyDecision(BaseModel):
    """Policy Check の判定（詳細設計 10.2）。

    `message` は人間向けであり、**テストの判定対象にしない**。判定は
    `(outcome, reason_code)` の組で行う。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: PolicyOutcome
    reason_code: PolicyReasonCode
    message: str
    detail: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def of(
        cls,
        reason_code: PolicyReasonCode,
        message: str,
        **detail: Any,
    ) -> PolicyDecision:
        """`reason_code` から `outcome` を導いて組み立てる。

        `outcome` を呼び出しのたびに手で指定すると、理由と結果が食い違う実装ミスが
        書けてしまう。導出を1箇所（`OUTCOME_OF_REASON`）に閉じる。
        """
        return cls(
            outcome=OUTCOME_OF_REASON[reason_code],
            reason_code=reason_code,
            message=message,
            detail=detail,
        )
