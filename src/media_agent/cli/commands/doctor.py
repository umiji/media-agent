"""`media-agent doctor` の枠（中身は T-007。詳細設計13章）。

`doctor` は **Config の読み込みで例外を送出しない**（罠 D-T15）。設定の不備は検査結果
`fail` として列挙し、終了コード 5 で終わる。したがってこの枠でも `config()` を呼ばない。
"""

from __future__ import annotations

import click

from media_agent.cli.commands._pending import not_implemented_yet
from media_agent.cli.context import CliContext, pass_cli_context


@click.command("doctor")
@click.option("--json", "json_output", is_flag=True, help="機械可読な JSON で出力する")
@pass_cli_context
def doctor_command(cli_ctx: CliContext, json_output: bool) -> None:
    """設定・構造・依存関係を検証する。"""
    cli_ctx.project_root()
    not_implemented_yet("doctor", "T-007")
