"""S-E: Agent を Runtime へ登録し、Input を渡して実行し、Output を取得できる。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-003 完了条件3 S-E / 要件定義書5.1節（Agent Runtime） |
| 期待値の正典 | 詳細設計 19章 S-E 行 → 詳細設計 8.1〜8.4 / 15.1〜15.3 |
| 使う Agent | 設計の組み込み Agent `echo` / `fail`（詳細設計 8.4）。テスト用の Agent を新たに書かない |
| 経路 | 公開 API と CLI の両方（前提 D-P6 / 申し送り N-2） |
"""

from __future__ import annotations

from pathlib import Path

import pytest
from media_agent.agents.builtin import EchoAgent, build_default_registry
from media_agent.core.runtime import AgentInput, AgentRegistry
from media_agent.errors import AgentNotFoundError

from tests.acceptance.expectations import (
    BUILTIN_AGENTS,
    EXIT_OK,
    EXIT_RUNTIME_ERROR,
    EXIT_USAGE,
    CliInvoke,
    RuntimeStack,
    parse_json,
    parse_labelled_output,
)

pytestmark = pytest.mark.acceptance


def test_default_registry_contains_builtin_agents() -> None:
    """`build_default_registry()` は組み込み Agent を返す（詳細設計 8.2 / 8.4）。"""
    registry = build_default_registry()

    assert registry.names() == sorted(BUILTIN_AGENTS)
    assert "echo" in registry
    assert registry.get("echo").name == "echo"


def test_agent_can_be_registered_into_a_registry() -> None:
    """Agent を Registry へ登録し、名前で引ける（詳細設計 8.2）。"""
    registry = AgentRegistry()

    registry.register(EchoAgent())

    assert registry.names() == ["echo"]
    assert len(registry) == 1


def test_unknown_agent_lookup_names_the_registered_agents() -> None:
    """未登録の名前を引くと `AgentNotFoundError`（詳細設計 8.2 / 17.3）。

    安定文字列は「要求した名前」と「登録済みの名前一覧」。
    """
    registry = build_default_registry()

    with pytest.raises(AgentNotFoundError) as excinfo:
        registry.get("no-such-agent")

    message = str(excinfo.value)
    assert "no-such-agent" in message
    for name in BUILTIN_AGENTS:
        assert name in message


def test_runner_returns_agent_output(runtime_stack: RuntimeStack) -> None:
    """Input を渡して実行し、Output を取得できる（詳細設計 8.3 / 19章 S-E 行）。"""
    result = runtime_stack.runner.run("echo", {"message": "hi"})

    assert result.output is not None
    assert result.output.payload == {"message": "hi"}
    assert result.output.decision != ""
    assert result.output.reason != ""
    assert result.error is None


def test_echo_agent_returns_its_input(runtime_stack: RuntimeStack) -> None:
    """組み込み `echo` は入力をそのまま返す（詳細設計 8.4）。"""
    agent = runtime_stack.registry.get("echo")
    payload = {"message": "hi", "n": 1}

    output = runtime_stack.runner.run("echo", payload).output

    assert agent.version >= 1
    assert output is not None
    assert output.payload == payload


def test_agent_input_defaults_to_empty_payload(runtime_stack: RuntimeStack) -> None:
    """`AgentInput` の `payload` は既定で空（詳細設計 8.1）。"""
    assert AgentInput().payload == {}

    output = runtime_stack.runner.run("echo").output

    assert output is not None
    assert output.payload == {}


def test_run_command_executes_echo_agent(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """CLI 経由でも Agent を実行し、Output を取得できる（詳細設計 15.1 / 15.3）。"""
    result = cli(
        "run",
        "--agent",
        "echo",
        "--input",
        '{"message":"hi"}',
        "--json",
        project=initialized_project,
    )

    assert result.exit_code == EXIT_OK, result.output
    payload = parse_json(result.stdout)
    assert payload["agent"] == "echo"
    assert payload["status"] == "completed"
    assert payload["output"] == {"message": "hi"}
    assert payload["error"] is None
    assert payload["task_id"]


def test_run_command_text_output_uses_stable_labels(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """テキスト出力の安定文字列は行ラベルと `status` の値（詳細設計 15.2）。"""
    result = cli("run", project=initialized_project)

    assert result.exit_code == EXIT_OK, result.output
    labels = parse_labelled_output(result.stdout)
    for label in ("agent", "task", "status", "output"):
        assert label in labels, f"ラベル {label} が出力にない: {result.stdout}"
    assert labels["status"] == "completed"
    assert labels["agent"] == "echo"


def test_run_command_with_unknown_agent_fails(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """未登録の Agent を指定すると終了コード 1（詳細設計 15.1 / 17.1）。"""
    result = cli("run", "--agent", "no-such-agent", project=initialized_project)

    assert result.exit_code == EXIT_RUNTIME_ERROR
    assert "no-such-agent" in result.stderr
    assert "echo" in result.stderr


def test_run_command_with_broken_input_is_a_usage_error(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`--input` が JSON として壊れていれば終了コード 2（詳細設計 15.1）。"""
    result = cli("run", "--input", "{not json", project=initialized_project)

    assert result.exit_code == EXIT_USAGE


def test_agent_list_shows_builtin_agents(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`agent list` は登録済み Agent を名前の昇順で出す（詳細設計 16.1）。"""
    result = cli("agent", "list", project=initialized_project)

    assert result.exit_code == EXIT_OK, result.output
    for header in ("NAME", "VERSION", "DESCRIPTION"):
        assert header in result.stdout
    for name in BUILTIN_AGENTS:
        assert name in result.stdout

    payload = parse_json(
        cli("agent", "list", "--json", project=initialized_project).stdout
    )
    assert [agent["name"] for agent in payload["agents"]] == sorted(BUILTIN_AGENTS)
