"""`agents/builtin/` の単体テスト（詳細設計 8.4）。

組み込み Agent は **AI を呼ばない・ネットワークへ出ない・ファイルを書かない**
（PO 制約 C-1〜C-3、品質基準 Q6・Q9）。外向きの接続は `tests/conftest.py` の
`block_network`（autouse）が例外にする。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from media_agent.agents.builtin import (
    AgentFailedForVerificationError,
    EchoAgent,
    FailAgent,
    build_default_registry,
)
from media_agent.core.config.models import Config
from media_agent.core.runtime import Agent, AgentContext, AgentInput
from media_agent.errors import MediaAgentError


@pytest.fixture()
def ctx(tmp_path: Path) -> AgentContext:
    return AgentContext(
        project_root=tmp_path,
        config=Config.model_validate(
            {"version": 1, "project": {"name": "sample-project"}}
        ),
        task_id="t-1",
        logger=logging.getLogger("test.builtin"),
    )


def test_default_registry_holds_the_builtin_agents() -> None:
    """`fail` も一覧に出す。隠すと一覧が実体と食い違う（詳細設計 8.4）。"""
    registry = build_default_registry()

    assert registry.names() == ["echo", "fail"]


def test_default_registry_is_not_shared_between_calls() -> None:
    """呼ぶたびに新しい Registry を返す（登録が別の呼び出しへ漏れない）。"""
    first = build_default_registry()
    second = build_default_registry()

    assert first is not second
    assert first.get("echo") is not second.get("echo")


def test_custom_agents_are_not_loaded_in_stage_0(tmp_path: Path) -> None:
    """`.media-agent/agents/` は**読み込まない**（T-006 完了条件7 / 方式設計9章）。

    `init` がディレクトリを作るところまでが Stage 0 の範囲である。
    """
    agents_dir = tmp_path / ".media-agent" / "agents"
    agents_dir.mkdir(parents=True)
    (agents_dir / "protein-expert.md").write_text("---\nname: protein\n---\n", "utf-8")

    assert build_default_registry().names() == ["echo", "fail"]


def test_echo_returns_its_input(ctx: AgentContext) -> None:
    output = EchoAgent().run(AgentInput(payload={"message": "hi", "n": 1}), ctx)

    assert output.payload == {"message": "hi", "n": 1}
    assert output.decision == "echo"
    assert output.reason


def test_echo_does_not_alias_the_input_payload(ctx: AgentContext) -> None:
    """入力の辞書をそのまま返さない（呼び出し側の書き換えが出力へ波及しない）。"""
    agent_input = AgentInput(payload={"message": "hi"})

    output = EchoAgent().run(agent_input, ctx)

    assert output.payload is not agent_input.payload


def test_echo_writes_nothing(ctx: AgentContext) -> None:
    """ファイルを書かない（品質基準 Q9。Agent は外部副作用を持たない）。"""
    before = set(ctx.project_root.rglob("*"))

    EchoAgent().run(AgentInput(), ctx)

    assert set(ctx.project_root.rglob("*")) == before


def test_fail_always_raises(ctx: AgentContext) -> None:
    with pytest.raises(AgentFailedForVerificationError) as excinfo:
        FailAgent().run(AgentInput(), ctx)

    assert "fail" in str(excinfo.value)


def test_fail_raises_outside_the_media_agent_hierarchy(ctx: AgentContext) -> None:
    """`RuntimeError` の派生である（詳細設計 8.4 / 17.1）。

    Runner が「Agent が投げた**任意の**例外」を扱えることを検証するための Agent
    なので、`MediaAgentError` の階層に入れるとその検証にならない。
    """
    assert issubclass(AgentFailedForVerificationError, RuntimeError)
    assert not issubclass(AgentFailedForVerificationError, MediaAgentError)


@pytest.mark.parametrize("agent_class", [EchoAgent, FailAgent])
def test_builtin_agents_declare_their_identity(agent_class: type[Agent]) -> None:
    """`name` / `version` / `description` を持つ（`agent list` の表示に使う）。"""
    assert isinstance(agent_class.name, str)
    assert agent_class.version >= 1
    assert agent_class.description
