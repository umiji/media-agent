"""`media-agent agent list`（詳細設計 16.1）。

**読み取り専用**であり、**Config を読まない**（詳細設計 17.2 の注記）。Registry は
組み込みのみで設定に依存しないため、`config.yaml` が壊れていても一覧は出せる。
未初期化のときだけ終了コード 3 で終わる。
"""

from __future__ import annotations

import click

from media_agent.agents.builtin import build_default_registry
from media_agent.cli.context import CliContext, pass_cli_context
from media_agent.cli.rendering import agent_as_json, emit_json, render_table

#: 表のヘッダ（安定文字列。詳細設計 16.1）。
HEADERS = ("NAME", "VERSION", "DESCRIPTION")


@click.group("agent")
def agent_group() -> None:
    """登録された Agent を確認する。"""


@agent_group.command("list")
@click.option("--json", "json_output", is_flag=True, help="機械可読な JSON で出力する")
@pass_cli_context
def agent_list_command(cli_ctx: CliContext, json_output: bool) -> None:
    """Registry に登録された Agent の一覧を表示する。"""
    cli_ctx.project_root()
    agents = [agent_as_json(agent) for agent in build_default_registry().all()]
    if cli_ctx.wants_json(json_output):
        emit_json({"agents": agents})
        return
    rows = [
        (agent["name"], str(agent["version"]), agent["description"]) for agent in agents
    ]
    for line in render_table(HEADERS, rows):
        click.echo(line)
