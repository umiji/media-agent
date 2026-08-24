"""`media-agent agent list` の枠（中身は T-007。詳細設計 16.1）。

**`agent list` は Config を読まない**（詳細設計 17.2 の注記）。Registry は組み込みのみで、
設定に依存しないため。未初期化のときだけ終了コード 3 で終わる。
"""

from __future__ import annotations

import click

from media_agent.cli.commands._pending import not_implemented_yet
from media_agent.cli.context import CliContext, pass_cli_context


@click.group("agent")
def agent_group() -> None:
    """登録された Agent を確認する。"""


@agent_group.command("list")
@click.option("--json", "json_output", is_flag=True, help="機械可読な JSON で出力する")
@pass_cli_context
def agent_list_command(cli_ctx: CliContext, json_output: bool) -> None:
    """Registry に登録された Agent の一覧を表示する。"""
    cli_ctx.project_root()
    not_implemented_yet("agent list", "T-007")
