"""Agent の登録簿（詳細設計 8.2）。

**「設定ファイル」ではなく実行時のオブジェクト登録簿である**（用語集「AgentRegistry」）。
Custom Agent（`.media-agent/agents/*.md`）は **Stage 0 では読み込まない**（方式設計9章。
要件定義書19節の表で Stage 0 は「設計」）。将来 Project 層がこの Registry へ追加登録する（拡張点 E-6）。
"""

from __future__ import annotations

from media_agent.core.runtime.agent import AGENT_NAME_PATTERN, Agent
from media_agent.errors import AgentNotFoundError, DuplicateAgentError, InvalidAgentError

__all__ = ["AgentRegistry"]


class AgentRegistry:
    """名前から Agent を引く登録簿（詳細設計 8.2）。"""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        """Agent を登録する。

        Raises:
            InvalidAgentError: `Agent` の派生でない、または `name` / `version` が
                詳細設計 8.1 の制約を満たさない。
            DuplicateAgentError: 同じ名前が既に登録されている。
        """
        if not isinstance(agent, Agent):
            raise InvalidAgentError(
                f"Agent の派生ではないものは登録できません: {type(agent).__name__}"
            )
        name = getattr(agent, "name", None)
        if not isinstance(name, str) or AGENT_NAME_PATTERN.match(name) is None:
            raise InvalidAgentError(
                f"Agent の名前が命名規則に合いません: {name!r}",
                details=[f"使える形: {AGENT_NAME_PATTERN.pattern}"],
            )
        version = getattr(agent, "version", None)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise InvalidAgentError(
                f"Agent の version は 1 以上の整数にしてください: {name} ({version!r})"
            )
        if name in self._agents:
            raise DuplicateAgentError(f"Agent が二重に登録されています: {name}")
        self._agents[name] = agent

    def get(self, name: str) -> Agent:
        """名前で引く。

        Raises:
            AgentNotFoundError: 未登録の名前。**メッセージに要求した名前と
                登録済みの名前一覧を含める**（詳細設計 8.2 / 17.3 の安定文字列）。
        """
        agent = self._agents.get(name)
        if agent is None:
            registered = ", ".join(self.names()) or "（登録されている Agent はありません）"
            raise AgentNotFoundError(
                f"Agent が登録されていません: {name} (登録済み: {registered})",
                hint="media-agent agent list で登録済みの Agent を確認できます",
            )
        return agent

    def names(self) -> list[str]:
        """登録済みの名前を昇順で返す（詳細設計 8.2 / 16.1）。"""
        return sorted(self._agents)

    def all(self) -> list[Agent]:
        """登録済みの Agent を名前の昇順で返す。"""
        return [self._agents[name] for name in self.names()]

    def __contains__(self, name: object) -> bool:
        return name in self._agents

    def __len__(self) -> int:
        return len(self._agents)
