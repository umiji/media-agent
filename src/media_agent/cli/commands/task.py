"""`media-agent task list`（詳細設計 16.2）。

**読み取り専用**である。`task cancel` 等の書き込み系サブコマンドは Stage 0 では作らない
（方式設計 6.4）。DB を読むため Config が要る（詳細設計 17.2 の注記）。
"""

from __future__ import annotations

import click

from media_agent.cli.context import CliContext, pass_cli_context
from media_agent.cli.rendering import emit_json, render_table, task_as_json
from media_agent.cli.session import open_session
from media_agent.core.task import TaskStatus

#: 表のヘッダ（安定文字列。詳細設計 16.2）。
HEADERS = ("TASK_ID", "AGENT", "TYPE", "STATUS", "CREATED_AT", "COMPLETED_AT")

#: 0件のときの表示（安定文字列。詳細設計 16.2）。
NO_TASKS = "(タスクはありません)"

#: `--limit` の既定（詳細設計 16.2）。
DEFAULT_LIMIT = 20

#: `--limit` の下限（詳細設計 16.2 の値域表。**上限は設けない**）。
MINIMUM_LIMIT = 1


@click.group("task")
def task_group() -> None:
    """記録された Task を確認する。"""


@task_group.command("list")
@click.option("--status", "status", default=None, help="この状態の Task だけを表示する")
@click.option(
    "--limit", "limit", type=int, default=DEFAULT_LIMIT, help="表示する最大件数"
)
@click.option("--json", "json_output", is_flag=True, help="機械可読な JSON で出力する")
@pass_cli_context
def task_list_command(
    cli_ctx: CliContext, status: str | None, limit: int, json_output: bool
) -> None:
    """記録された Task の一覧と状態を表示する。"""
    with open_session(cli_ctx) as session:
        # **値域の検査はプロジェクトを開いた後**（詳細設計 16.2 の「検査の場所と順序」）。
        # 未初期化（3）と構造破損（1）を、使い方の誤り（2）より先に返すためである。
        # 両方が不正なら `--status` を先に報告する。
        selected = _parse_status(status)
        _verify_limit(limit)
        tasks = [
            task_as_json(task)
            for task in session.tasks.list(status=selected, limit=limit)
        ]
        if cli_ctx.wants_json(json_output):
            emit_json({"tasks": tasks})
            return
        rows = [
            (
                task["task_id"],
                task["agent"],
                task["type"],
                task["status"],
                str(task["created_at"]),
                str(task["completed_at"] or "-"),
            )
            for task in tasks
        ]
        # **ヘッダは0件でも出す**（詳細設計 16.2）。
        for line in render_table(HEADERS, rows):
            click.echo(line)
        if not rows:
            click.echo(NO_TASKS)


def _parse_status(status: str | None) -> TaskStatus | None:
    """`--status` の値域を検査する（詳細設計 16.2）。

    Raises:
        click.UsageError: 5つの状態名以外を指定した（終了コード 2）。
    """
    if status is None:
        return None
    try:
        return TaskStatus(status)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in TaskStatus)
        raise click.UsageError(
            f"--status は次のいずれかで指定してください（{allowed}）: {status}"
        ) from exc


def _verify_limit(limit: int) -> None:
    """`--limit` の値域を検査する（詳細設計 16.2 の値域表。T-012 / D-3）。

    **1 以上の整数。上限は設けない。** `0` 以下は `--status` と同じく `click.UsageError`
    （終了コード 2）にする。

    却下案（16.2）: `click.IntRange(min=1)` を使う → 検査が Click の型変換の段で起き、
    **未初期化ディレクトリでも 2 が返って 17.2 の1行目と食い違う**。
    整数に解釈できない値（`abc`）だけは、その型変換が先に処理する。

    Raises:
        click.UsageError: `0` 以下を指定した（終了コード 2）。安定文字列は `--limit`。
    """
    if limit < MINIMUM_LIMIT:
        raise click.UsageError(
            f"--limit は {MINIMUM_LIMIT} 以上の整数で指定してください: {limit}"
        )
