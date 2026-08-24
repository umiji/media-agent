"""CLI のエントリポイントと、例外 → 終了コードの変換（方式設計 6.1・6.5）。

`main` は Click のグループそのものである。console script（`media-agent`）、
`python -m media_agent`、`click.testing.CliRunner` の3経路が**同じオブジェクト**へ落ちる。

終了コードの対応は `media_agent.errors` のクラス属性 `exit_code` が持つ。
ここに `isinstance` の分岐表を作らない（品質基準 Q8）。
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

import click

from media_agent import __version__
from media_agent.cli.commands import register_commands
from media_agent.cli.context import CliContext
from media_agent.errors import MediaAgentError

#: 想定外の内部エラー（方式設計 6.5）。
EXIT_INTERNAL_ERROR = 70


def render_error(exc: MediaAgentError) -> None:
    """エラーを標準エラーへ出す（詳細設計 17.3 の形）。"""
    click.echo(f"Error: {exc.message}", err=True)
    for detail in exc.details:
        click.echo(f"  - {detail}", err=True)
    if exc.hint:
        click.echo(f"Hint: {exc.hint}", err=True)


class MediaAgentGroup(click.Group):
    """例外を終了コードへ変換する唯一の場所（品質基準 Q8）。"""

    def invoke(self, ctx: click.Context) -> Any:
        try:
            return super().invoke(ctx)
        except MediaAgentError as exc:
            render_error(exc)
            ctx.exit(exc.exit_code)
        except (click.ClickException, click.exceptions.Exit, click.Abort):
            raise
        except Exception as exc:  # noqa: BLE001 - 想定外はここで 70 へ落とす
            click.echo(f"Error: 内部エラーが発生しました: {exc}", err=True)
            if _is_verbose(ctx):
                click.echo(traceback.format_exc(), err=True)
            else:
                click.echo("Hint: --verbose を付けると詳細が表示されます", err=True)
            ctx.exit(EXIT_INTERNAL_ERROR)


def _is_verbose(ctx: click.Context) -> bool:
    return isinstance(ctx.obj, CliContext) and ctx.obj.verbose


@click.group(cls=MediaAgentGroup, name="media-agent")
@click.option(
    "-C",
    "--project-dir",
    "project_dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    envvar="MEDIA_AGENT_PROJECT_DIR",
    default=None,
    help="対象プロジェクトのディレクトリ（既定: カレントディレクトリ）",
)
@click.option("-v", "--verbose", is_flag=True, help="運用ログを詳細レベルで出す")
@click.option("-q", "--quiet", is_flag=True, help="エラー以外の出力を抑制する")
@click.option("--json", "json_output", is_flag=True, help="機械可読な JSON で出力する")
@click.version_option(__version__, "--version", prog_name="media-agent")
@click.pass_context
def main(
    ctx: click.Context,
    project_dir: Path | None,
    verbose: bool,
    quiet: bool,
    json_output: bool,
) -> None:
    """メディア運用の汎用エージェント基盤。"""
    ctx.obj = CliContext(
        project_dir=project_dir,
        verbose=verbose,
        quiet=quiet,
        json_output=json_output,
        cwd=Path.cwd(),
    )


register_commands(main)
