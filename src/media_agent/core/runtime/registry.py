"""Agent の登録簿（詳細設計 8.2）。

Registry は**名前と Agent の対応だけ**を持つ。どこから Agent を集めてくるかは
知らない（Custom Agent 置き場の走査は Project 層の責務。方式設計9章。`core/` は
プロジェクト配下のディレクトリ名を知らない — 品質基準 Q7）。
**Custom Agent は Stage 0 では読み込まない**（T-006 完了条件7）。
"""

from __future__ import annotations

import re

from media_agent.core.runtime.agent import AGENT_NAME_PATTERN, Agent
from media_agent.errors import (
    AgentNotFoundError,
    DuplicateAgentError,
    InvalidAgentError,
)

__all__ = ["AgentRegistry"]

_NAME_RE = re.compile(AGENT_NAME_PATTERN)


class AgentRegistry:
    """名前から Agent を引く登録簿（詳細設計 8.2）。"""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        """1件登録する。

        Raises:
            InvalidAgentError: `Agent` の派生でない、または `name` / `version` /
                `description` が要件を満たさない。**登録の時点で弾く**（8.1 の理由）。
            DuplicateAgentError: 同じ名前が既に登録されている。
        """
        if not isinstance(agent, Agent):
            raise InvalidAgentError(
                f"Agent の派生ではありません: {type(agent).__name__}",
                details=[f"{Agent.__module__}.Agent を継承してください"],
            )
        name = self._validated_name(agent)
        self._validate_version(agent, name)
        if name in self._agents:
            raise DuplicateAgentError(
                f"同じ名前の Agent が既に登録されています: {name}",
                details=[f"登録済み: {', '.join(self.names())}"],
            )
        self._agents[name] = agent

    def get(self, name: str) -> Agent:
        """名前で引く。

        Raises:
            AgentNotFoundError: 未登録。**要求した名前と登録済みの名前一覧**を
                メッセージに含める（安定文字列。詳細設計 17.3）。
        """
        agent = self._agents.get(name)
        if agent is None:
            registered = ", ".join(self.names()) if self._agents else "（なし）"
            # **安定文字列は要約行に置く。** `details` は CLI が整形して表示するもので
            # あり、`str(exc)` には現れない（`MediaAgentError.__init__`）。
            raise AgentNotFoundError(
                f"Agent が登録されていません: {name}（登録済みの Agent: {registered}）",
                hint="media-agent agent list で登録済みの Agent を確認できます",
            )
        return agent

    def names(self) -> list[str]:
        """登録済みの名前を昇順で返す（詳細設計 8.2）。"""
        return sorted(self._agents)

    def all(self) -> list[Agent]:
        """登録済みの Agent を名前の昇順で返す（詳細設計 8.2）。"""
        return [self._agents[name] for name in self.names()]

    def __contains__(self, name: object) -> bool:
        return name in self._agents

    def __len__(self) -> int:
        return len(self._agents)

    @staticmethod
    def _validated_name(agent: Agent) -> str:
        name = getattr(type(agent), "name", None)
        if not isinstance(name, str) or not _NAME_RE.match(name):
            raise InvalidAgentError(
                f"Agent の name が命名規則に合いません: {name!r}"
                f"（{type(agent).__name__}）",
                details=[f"命名規則: {AGENT_NAME_PATTERN}"],
            )
        return name

    @staticmethod
    def _validate_version(agent: Agent, name: str) -> None:
        version = getattr(type(agent), "version", None)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise InvalidAgentError(
                f"Agent の version は 1 以上の整数にしてください: {name} -> {version!r}"
            )
        if not isinstance(getattr(type(agent), "description", None), str):
            raise InvalidAgentError(f"Agent の description がありません: {name}")
