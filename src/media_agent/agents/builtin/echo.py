"""検証用の組み込み Agent `echo`（詳細設計 8.4）。

**AI を呼ばない・ネットワークへ出ない・ファイルを書かない**（PO 制約 C-1〜C-3、
品質基準 Q6・Q9）。Runtime が動くことを示すためだけに存在する。
"""

from __future__ import annotations

from typing import ClassVar

from media_agent.core.runtime.agent import Agent, AgentContext, AgentInput, AgentOutput

__all__ = ["EchoAgent"]


class EchoAgent(Agent):
    """入力をそのまま返す（詳細設計 8.4）。"""

    name: ClassVar[str] = "echo"
    version: ClassVar[int] = 1
    description: ClassVar[str] = "入力をそのまま返す検証用の組み込み Agent"

    def run(self, input: AgentInput, ctx: AgentContext) -> AgentOutput:
        return AgentOutput(
            payload=dict(input.payload),
            decision="echo",
            reason="組み込みの検証用 Agent のため、入力をそのまま返した",
        )
