"""`media-agent task list` の枠（中身は T-007。詳細設計 16.2）。

`task list` は DB を読むため Config が要る（詳細設計 17.2 の注記）。
"""

from __future__ import annotations

import click

from media_agent.cli.commands._pending import not_implemented_yet
from media_agent.cli.context import CliContext, pass_cli_context


@click.group("task")
def task_group() -> None:
    """記録された Task を確認する。"""


@task_group.command("list")
@click.option("--status", "status", default=None, help="この状態の Task だけを表示する")
@click.option("--limit", "limit", type=int, default=20, help="表示する最大件数")
@click.option("--json", "json_output", is_flag=True, help="機械可読な JSON で出力する")
@pass_cli_context
def task_list_command(
    cli_ctx: CliContext, status: str | None, limit: int, json_output: bool
) -> None:
    """記録された Task の一覧と状態を表示する。"""
    cli_ctx.config()
    not_implemented_yet("task list", "T-007")
