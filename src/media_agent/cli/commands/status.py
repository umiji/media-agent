"""`media-agent status` の枠（中身は T-007。詳細設計14章）。"""

from __future__ import annotations

import click

from media_agent.cli.commands._pending import not_implemented_yet
from media_agent.cli.context import CliContext, pass_cli_context


@click.command("status")
@click.option("--json", "json_output", is_flag=True, help="機械可読な JSON で出力する")
@pass_cli_context
def status_command(cli_ctx: CliContext, json_output: bool) -> None:
    """現在の Agent / Task の状態を確認する。"""
    cli_ctx.config()
    not_implemented_yet("status", "T-007")
