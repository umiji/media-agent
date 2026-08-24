"""Agent Runtime（要件定義書5.1節 / 詳細設計8章）。

Agent の登録・実行・状態管理・エラー処理・実行ログをここに置く。

- **Agent は外部副作用を持たない**（品質基準 Q9）。永続化と監査は `AgentRunner` の責務
- **`core/runtime` は `agents/` を import しない**（方式設計 5.2 の依存の向き）。
  組み込み Agent（`media_agent.agents.builtin`）は Registry へ**外から**登録される

主な公開物（申し送り K-1 により、ここで再エクスポートする）。
"""

from __future__ import annotations

from media_agent.core.runtime.agent import (
    AGENT_NAME_PATTERN,
    Agent,
    AgentContext,
    AgentInput,
    AgentOutput,
)
from media_agent.core.runtime.registry import AgentRegistry
from media_agent.core.runtime.runner import AgentRunner, TaskRunResult

__all__ = [
    "AGENT_NAME_PATTERN",
    "Agent",
    "AgentContext",
    "AgentInput",
    "AgentOutput",
    "AgentRegistry",
    "AgentRunner",
    "TaskRunResult",
]
