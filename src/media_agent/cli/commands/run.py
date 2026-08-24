"""`media-agent run`（詳細設計15章）。

**Stage 0 の `run` は、組み込み Agent を1本実行し、Task と Audit を残して終わる**（15.1）。
存在しない Workflow を装わない。

**Policy Check を呼ばない**（15.4）。Stage 0 の `run` は Action を1つも発行せず、
Action の無い場所に関門を置くと「何も守っていない通過記録」が積もるためである。
"""

from __future__ import annotations

import json
from typing import Any

import click

from media_agent.cli.context import CliContext, pass_cli_context
from media_agent.cli.rendering import (
    RUN_LABEL_WIDTH,
    compact_json,
    emit_json,
    labelled,
)
from media_agent.cli.session import open_session
from media_agent.core.runtime import TaskRunResult
from media_agent.core.task import TaskStatus
from media_agent.errors import AgentExecutionFailedError

#: `--agent` の既定（詳細設計 15.1）。
DEFAULT_AGENT = "echo"

#: `--input` の既定（詳細設計 15.1）。
DEFAULT_INPUT: dict[str, Any] = {"message": "hello"}


@click.command("run")
@click.option("--agent", "agent_name", default=DEFAULT_AGENT, help="実行する Agent 名")
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
    with open_session(cli_ctx) as session:
        # 未初期化（3）と設定エラー（4）を、利用方法の誤り（2）より先に返す
        # （詳細設計 17.2 のコマンド × 状況の一覧）。
        payload = _parse_input(input_json)
        result = session.runner().run(agent_name, payload)
        rendered = _payload(str(session.layout.root), agent_name, result)

        # **失敗時にも標準出力へ JSON を出す**（契約 K-3）。`error` キーを持たせた
        # 以上、失敗したときに出ないなら意味が無い。
        if cli_ctx.wants_json(json_output):
            emit_json(rendered)
        else:
            _render_text(rendered)

        if result.task.status is TaskStatus.failed:
            raise AgentExecutionFailedError(
                f"Agent の実行が失敗しました (task={result.task.task_id})",
                details=[result.error] if result.error else [],
                hint="media-agent task list で記録された Task を確認できます",
            )


def _parse_input(input_json: str | None) -> dict[str, Any]:
    """`--input` を payload にする（詳細設計 15.1）。

    Raises:
        click.UsageError: JSON として壊れている、または JSON オブジェクトでない
            （終了コード 2）。
    """
    if input_json is None:
        return dict(DEFAULT_INPUT)
    try:
        parsed = json.loads(input_json)
    except json.JSONDecodeError as exc:
        raise click.UsageError(f"--input を JSON として読めません: {exc}") from exc
    if not isinstance(parsed, dict):
        raise click.UsageError(
            f"--input は JSON オブジェクトで指定してください: {type(parsed).__name__}"
        )
    return parsed


def _payload(
    project_root: str, agent_name: str, result: TaskRunResult
) -> dict[str, Any]:
    """テキストと JSON の両方の元になる辞書（詳細設計 15.3）。"""
    task = result.task
    return {
        "project_root": project_root,
        "agent": agent_name,
        "task_id": task.task_id,
        "status": task.status.value,
        "output": None if result.output is None else result.output.payload,
        "error": result.error,
        "created_at": _iso(task.created_at),
        "started_at": _iso(task.started_at),
        "completed_at": _iso(task.completed_at),
    }


def _iso(value: Any) -> str | None:
    from media_agent.core.clock import to_iso

    return None if value is None else to_iso(value)


def _render_text(payload: dict[str, Any]) -> None:
    """人間向け出力（詳細設計 15.2）。安定文字列は行ラベルと `status` の値。"""
    click.echo(f"Media Agent run — {payload['project_root']}")
    click.echo(labelled("agent", str(payload["agent"]), RUN_LABEL_WIDTH))
    click.echo(labelled("task", str(payload["task_id"]), RUN_LABEL_WIDTH))
    click.echo(labelled("status", str(payload["status"]), RUN_LABEL_WIDTH))
    if payload["output"] is not None:
        click.echo(labelled("output", compact_json(payload["output"]), RUN_LABEL_WIDTH))
    if payload["error"] is not None:
        click.echo(labelled("error", str(payload["error"]), RUN_LABEL_WIDTH))
