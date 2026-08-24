"""組み込み Agent だけを登録した Registry（詳細設計 8.2 / 8.4）。

**Custom Agent（`.media-agent/agents/*.md`）は Stage 0 では読み込まない**
（方式設計9章、T-006 完了条件7。`init` がディレクトリを作るところまでが Stage 0 の範囲）。
将来 Project 層がこの Registry へ追加登録する（拡張点 E-6）。
"""

from __future__ import annotations

from media_agent.agents.builtin.echo import EchoAgent
from media_agent.agents.builtin.fail import FailAgent
from media_agent.core.runtime.registry import AgentRegistry

__all__ = ["BUILTIN_AGENTS", "build_default_registry"]

#: 同梱する組み込み Agent（詳細設計 8.4）。**`fail` も一覧に出す。**
#: 隠すと「登録されている Agent の一覧」が実体と食い違う。
BUILTIN_AGENTS: tuple[type[EchoAgent] | type[FailAgent], ...] = (EchoAgent, FailAgent)


def build_default_registry() -> AgentRegistry:
    """組み込み Agent だけを登録した Registry を返す（詳細設計 8.2）。

    **呼ぶたびに新しい Registry を返す。** モジュール変数で共有すると、テストが
    登録した Agent が別のテストへ漏れる。
    """
    registry = AgentRegistry()
    for agent_class in BUILTIN_AGENTS:
        registry.register(agent_class())
    return registry
