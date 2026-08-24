"""`core/runtime/agent.py` の単体テスト（詳細設計 8.1）。

`decision` / `reason` を**必須**にしていることが、監査記録の必須項目（要件5.5節）を
Runner が推測で埋めない根拠である。ここが緩むと Audit の項目が Agent 依存になる。
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from media_agent.core.config.models import Config
from media_agent.core.runtime import Agent, AgentContext, AgentInput, AgentOutput


def _config() -> Config:
    return Config.model_validate({"version": 1, "project": {"name": "sample-project"}})


def test_agent_input_defaults_to_an_empty_payload() -> None:
    assert AgentInput().payload == {}


def test_agent_input_is_frozen() -> None:
    agent_input = AgentInput(payload={"message": "hi"})

    with pytest.raises(ValidationError):
        agent_input.payload = {}  # type: ignore[misc]


def test_agent_input_rejects_unknown_fields() -> None:
    """`extra="forbid"`。渡し間違いを黙って捨てない。"""
    with pytest.raises(ValidationError):
        AgentInput(payloads={})  # type: ignore[call-arg]


def test_agent_output_requires_decision_and_reason() -> None:
    """`decision` / `reason` が空の出力は作れない（詳細設計 8.1）。"""
    with pytest.raises(ValidationError):
        AgentOutput(decision="", reason="理由")
    with pytest.raises(ValidationError):
        AgentOutput(decision="判断", reason="")
    with pytest.raises(ValidationError):
        AgentOutput(payload={})  # type: ignore[call-arg]


def test_agent_output_decision_is_one_short_line() -> None:
    """`decision` は1行・120文字以内（詳細設計 8.1）。一覧性を保つため。"""
    with pytest.raises(ValidationError):
        AgentOutput(decision="1行目\n2行目", reason="理由")
    with pytest.raises(ValidationError):
        AgentOutput(decision="a" * 121, reason="理由")

    assert AgentOutput(decision="a" * 120, reason="理由").decision == "a" * 120


def test_agent_context_carries_the_project_root_only(tmp_path: Path) -> None:
    """`ProjectLayout` ではなく `root` だけを渡す（品質基準 Q7）。"""
    ctx = AgentContext(
        project_root=tmp_path,
        config=_config(),
        task_id="t-1",
        logger=logging.getLogger("test"),
    )

    assert ctx.project_root == tmp_path
    assert not hasattr(ctx, "layout")
    assert not hasattr(ctx, "conn")
    assert not hasattr(ctx, "audit")


def test_agent_context_is_frozen(tmp_path: Path) -> None:
    ctx = AgentContext(
        project_root=tmp_path,
        config=_config(),
        task_id="t-1",
        logger=logging.getLogger("test"),
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.task_id = "t-2"  # type: ignore[misc]


def test_agent_cannot_be_instantiated_without_run() -> None:
    """`run` を実装しない Agent は**生成できない**（ABC を選んだ理由。詳細設計 8.1）。"""

    class Incomplete(Agent):
        name = "incomplete"
        version = 1
        description = "run を実装していない"

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]
