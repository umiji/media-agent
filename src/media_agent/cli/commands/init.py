"""`media-agent init`（詳細設計12章）。"""

from __future__ import annotations

import click

from media_agent.cli.context import CliContext, pass_cli_context
from media_agent.project.scaffold import init_project


@click.command("init")
@click.option(
    "--force",
    is_flag=True,
    help="テンプレート由来の4ファイル（config.yaml / strategy.md / rules.md / .gitignore）を上書きする",
)
@pass_cli_context
def init_command(cli_ctx: CliContext, force: bool) -> None:
    """現在のプロジェクトに Media Agent を導入する。"""
    result = init_project(cli_ctx.target_dir(), force=force)
    if cli_ctx.quiet:
        return
    for entry in result.entries:
        click.echo(f"{entry.action}  {entry.relative}")
    click.echo(f"Media Agent を初期化しました: {result.layout.root}")
