"""Policy Engine（要件定義書5.3節・13節 / 詳細設計10章）。

**Stage 0 に Action の実行先は存在しない。** ここにあるのは要件定義書2.4節
「Agent Decision → Policy Check → Action → External Service」の **Policy Check だけ**である。

`PolicyDeniedError`（終了コード 6）は `media_agent.errors` に定義されているが、
Stage 0 には Action の実行経路が無いため送出箇所を持たない（詳細設計 10.6）。

主な公開物（申し送り K-1 により、ここで再エクスポートする）。
"""

from __future__ import annotations

from media_agent.core.policy.engine import PolicyEngine
from media_agent.core.policy.models import (
    OUTCOME_OF_REASON,
    PolicyDecision,
    PolicyOutcome,
    PolicyReasonCode,
    PolicyRequest,
)

__all__ = [
    "OUTCOME_OF_REASON",
    "PolicyDecision",
    "PolicyEngine",
    "PolicyOutcome",
    "PolicyReasonCode",
    "PolicyRequest",
]
