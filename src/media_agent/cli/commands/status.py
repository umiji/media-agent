"""`media-agent status`（詳細設計14章）。

現在の Agent / Task の状態を出す（要件定義書10節）。

**`status` は DB が無ければ作る。** `doctor`（副作用なし）との非対称は意図されたもので、
状態を見るには DB が要るためである（14章）。
"""

from __future__ import annotations

from typing import Any

import click

from media_agent.cli.context import CliContext, pass_cli_context
from media_agent.cli.rendering import (
    agent_as_json,
    emit_json,
    labelled,
    task_as_json,
)
from media_agent.cli.session import ProjectSession, open_session
from media_agent.core.db.migrations import schema_version
from media_agent.core.task import TaskStatus

#: `recent tasks` に出す最大件数（詳細設計14章）。
RECENT_LIMIT = 5

#: タスクが1件も無いときの表示（安定文字列。詳細設計14章）。
NO_TASKS = "(タスクはありません)"


@click.command("status")
@click.option("--json", "json_output", is_flag=True, help="機械可読な JSON で出力する")
@pass_cli_context
def status_command(cli_ctx: CliContext, json_output: bool) -> None:
    """現在の Agent / Task の状態を確認する。"""
    with open_session(cli_ctx) as session:
        payload = _payload(session)
        if cli_ctx.wants_json(json_output):
            emit_json(payload)
        else:
            _render_text(payload)


def _payload(session: ProjectSession) -> dict[str, Any]:
    """テキストと JSON の**両方**がこの1つの辞書から作られる（表示のずれを作らない）。"""
    config = session.config
    counts = session.tasks.counts()
    recent = session.tasks.list(limit=RECENT_LIMIT)
    return {
        "project_root": str(session.layout.root),
        "project_name": config.project.name,
        "config": {
            "version": config.version,
            "primary_platform": config.media.primary_platform,
            "posts_per_day": config.content.posts_per_day,
            "require_approval": config.automation.require_approval,
            "actions": {
                name.value: policy.mode.value for name, policy in config.actions.items()
            },
        },
        "database": {
            "path": session.layout.relative(session.layout.db_path),
            "schema_version": schema_version(session.conn),
        },
        "agents": [agent_as_json(agent) for agent in session.registry.all()],
        "tasks": {
            "total": sum(counts.values()),
            # **5状態すべてのキーを出す**（件数 0 でも省略しない。14章）。
            "by_status": {status.value: counts[status] for status in TaskStatus},
        },
        "recent_tasks": [task_as_json(task) for task in recent],
    }


def _render_text(payload: dict[str, Any]) -> None:
    """人間向け出力（詳細設計14章）。**ラベル名が安定文字列である。**"""
    config = payload["config"]
    database = payload["database"]
    agents = payload["agents"]
    tasks = payload["tasks"]

    click.echo(f"Media Agent status — {payload['project_root']}")
    click.echo(labelled("project", str(payload["project_name"])))
    click.echo(
        labelled(
            "config",
            f"version {config['version']} / platform {config['primary_platform']}"
            f" / posts_per_day {config['posts_per_day']}",
        )
    )
    modes = " ".join(f"{name}={mode}" for name, mode in config["actions"].items())
    click.echo(
        labelled(
            "automation",
            f"require_approval={str(config['require_approval']).lower()}  {modes}",
        )
    )
    click.echo(
        labelled(
            "database", f"{database['path']} (schema {database['schema_version']})"
        )
    )
    names = ", ".join(agent["name"] for agent in agents)
    click.echo(labelled("agents", f"{len(agents)} registered — {names}"))
    by_status = " / ".join(
        f"{status} {count}" for status, count in tasks["by_status"].items()
    )
    click.echo(labelled("tasks", f"total {tasks['total']} — {by_status}"))
    click.echo(labelled("recent tasks"))
    if not payload["recent_tasks"]:
        click.echo(f"  {NO_TASKS}")
        return
    for task in payload["recent_tasks"]:
        click.echo(
            f"  {task['created_at']}  {task['status']:<10} "
            f"{task['agent']}  {task['task_id']}"
        )
