"""`media-agent run` の枠（中身は T-007。詳細設計15章）。"""

from __future__ import annotations

import click

from media_agent.cli.commands._pending import not_implemented_yet
from media_agent.cli.context import CliContext, pass_cli_context


@click.command("run")
@click.option("--agent", "agent_name", default="echo", help="実行する Agent 名")
@click.option(
    "--input", "input_json", default=None, help="Agent へ渡す payload（JSON）"
)
@click.option("--json", "json_output", is_flag=True, help="機械可読な JSON で出力する")
@pass_cli_context
def run_command(
    cli_ctx: CliContext,
    agent_name: str,
    input_json: str | None,
    json_output: bool,
) -> None:
    """Media Agent の Workflow を実行する。"""
    cli_ctx.config()
    not_implemented_yet("run", "T-007")
