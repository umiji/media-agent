"""検証用の組み込み Agent `fail`（詳細設計 8.4）。

**`fail` を製品に同梱する理由**: 異常系（Task が `failed` になる、監査記録に `error` が
残る）を、**受け入れテストが製品コードを書かずに CLI から確認できる**ようにするため。

`fail` は `agent list` にも表示する。隠すと「登録されている Agent の一覧」が実体と食い違う。
"""

from __future__ import annotations

from typing import ClassVar

from media_agent.core.runtime.agent import Agent, AgentContext, AgentInput, AgentOutput

__all__ = ["AgentFailedForVerificationError", "FailAgent"]

#: `fail` が送出するメッセージ（詳細設計 8.4）。
FAIL_MESSAGE = "検証用 Agent 'fail' は常に失敗します"


class AgentFailedForVerificationError(RuntimeError):
    """`fail` が送出する例外。

    **`MediaAgentError` の派生ではなく `RuntimeError` の派生である**（詳細設計 8.4 / 17.1）。
    Runner が「Agent が投げた**任意の**例外」を扱えることを、組み込み Agent 自身で
    検証するため。`media_agent.errors` の階層に入れると、その検証にならない。
    """


class FailAgent(Agent):
    """常に失敗する（詳細設計 8.4）。"""

    name: ClassVar[str] = "fail"
    version: ClassVar[int] = 1
    description: ClassVar[str] = "常に失敗する検証用の組み込み Agent"

    def run(self, input: AgentInput, ctx: AgentContext) -> AgentOutput:
        """必ず送出する。**戻り値を返す経路を持たない。**"""
        raise AgentFailedForVerificationError(FAIL_MESSAGE)
