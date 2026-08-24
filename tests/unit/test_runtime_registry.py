"""`core/runtime/registry.py` の単体テスト（詳細設計 8.2）。

Registry は**登録の時点で**妥当性を確認する。`name` / `version` の欠落が実行時まで
判明しないのを避けるために ABC を選んだ（8.1 の却下案）以上、その検査がここにある。
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from media_agent.agents.builtin import EchoAgent, FailAgent, build_default_registry
from media_agent.core.runtime import (
    Agent,
    AgentContext,
    AgentInput,
    AgentOutput,
    AgentRegistry,
)
from media_agent.errors import (
    AgentNotFoundError,
    DuplicateAgentError,
    InvalidAgentError,
)


class _Named(Agent):
    """テスト用の Agent。`name` だけを差し替えて使う。"""

    name: ClassVar[str] = "sample"
    version: ClassVar[int] = 1
    description: ClassVar[str] = "テスト用"

    def run(self, input: AgentInput, ctx: AgentContext) -> AgentOutput:
        return AgentOutput(decision="ok", reason="テスト用")


def _agent_named(agent_name: str) -> Agent:
    return type("Generated", (_Named,), {"name": agent_name})()


def test_register_and_get() -> None:
    registry = AgentRegistry()
    agent = EchoAgent()

    registry.register(agent)

    assert registry.get("echo") is agent
    assert "echo" in registry
    assert len(registry) == 1


def test_names_and_all_are_sorted() -> None:
    """名前の昇順（詳細設計 8.2）。表示順が登録順に依存しないようにする。"""
    registry = AgentRegistry()
    registry.register(FailAgent())
    registry.register(EchoAgent())

    assert registry.names() == ["echo", "fail"]
    assert [agent.name for agent in registry.all()] == ["echo", "fail"]


def test_get_unknown_names_the_registered_agents() -> None:
    """未登録の名前は `AgentNotFoundError`。安定文字列は要求名と登録済み一覧（17.3）。"""
    registry = build_default_registry()

    with pytest.raises(AgentNotFoundError) as excinfo:
        registry.get("no-such-agent")

    message = str(excinfo.value)
    assert "no-such-agent" in message
    assert "echo" in message
    assert "fail" in message


def test_get_from_an_empty_registry_still_explains_itself() -> None:
    with pytest.raises(AgentNotFoundError, match="echo|なし"):
        AgentRegistry().get("echo")


def test_duplicate_registration_is_rejected() -> None:
    registry = AgentRegistry()
    registry.register(EchoAgent())

    with pytest.raises(DuplicateAgentError, match="echo"):
        registry.register(EchoAgent())


def test_registering_a_non_agent_is_rejected() -> None:
    """`Agent` の派生でないものを渡したら登録時に弾く（詳細設計 8.2）。"""
    registry = AgentRegistry()

    with pytest.raises(InvalidAgentError):
        registry.register(object())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "agent_name",
    ["", "Echo", "1echo", "echo_agent", "echo agent", "e" * 33, "エコー"],
)
def test_invalid_names_are_rejected(agent_name: str) -> None:
    """命名規則 `^[a-z][a-z0-9-]{0,31}$` に合わない名前は登録できない（詳細設計 8.1）。"""
    registry = AgentRegistry()

    with pytest.raises(InvalidAgentError):
        registry.register(_agent_named(agent_name))


@pytest.mark.parametrize("agent_name", ["e", "echo", "echo-agent", "e" * 32, "a1-2"])
def test_valid_names_are_accepted(agent_name: str) -> None:
    registry = AgentRegistry()

    registry.register(_agent_named(agent_name))

    assert registry.names() == [agent_name]


@pytest.mark.parametrize("version", [0, -1, "1", 1.0, True, None])
def test_invalid_versions_are_rejected(version: object) -> None:
    """`version` は 1 以上の整数（詳細設計 8.1。再現性のため実装が変わったら上げる）。"""
    registry = AgentRegistry()
    agent = type("Generated", (_Named,), {"version": version})()

    with pytest.raises(InvalidAgentError):
        registry.register(agent)


def test_missing_description_is_rejected() -> None:
    """`description` は `agent list` の表示に要る（詳細設計 16.1）。"""
    registry = AgentRegistry()
    agent = type("Generated", (_Named,), {"description": None})()

    with pytest.raises(InvalidAgentError):
        registry.register(agent)


def test_a_rejected_registration_leaves_the_registry_unchanged() -> None:
    registry = AgentRegistry()
    registry.register(EchoAgent())

    with pytest.raises(InvalidAgentError):
        registry.register(_agent_named("Bad"))

    assert registry.names() == ["echo"]
