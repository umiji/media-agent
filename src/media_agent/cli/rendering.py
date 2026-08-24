"""CLI の出力の組み立て（詳細設計 13.3 / 14章 / 15.2 / 15.3 / 16章）。

**安定文字列はここに集める。** 受け入れテストが判定してよいのは check id・ラベル名・
表のヘッダ・終了コードだけであり（詳細設計 17.3）、それらを1箇所で持つ。

`click.echo` で出すのは**標準出力**である。エラーは例外として送出し、`cli/app.py` が
標準エラーへ整形する（品質基準 Q8）。
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from datetime import datetime
from typing import Any

import click

from media_agent.core.clock import to_iso
from media_agent.core.runtime import Agent
from media_agent.core.task import Task

__all__ = [
    "STATUS_LABEL_WIDTH",
    "agent_as_json",
    "compact_json",
    "emit_json",
    "labelled",
    "render_table",
    "task_as_json",
]

#: `status` のラベル幅（詳細設計14章: 左詰め13文字 + `: `）。
STATUS_LABEL_WIDTH = 13

#: `run` のラベル幅（詳細設計 15.2）。
RUN_LABEL_WIDTH = 8


def emit_json(payload: Any) -> None:
    """機械可読出力を標準出力へ1つだけ出す（詳細設計 6.2 / 15.3）。"""
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def compact_json(payload: Any) -> str:
    """テキスト出力の1行に埋め込む JSON（詳細設計 15.2 の `output` 行）。"""
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def labelled(label: str, value: str = "", width: int = STATUS_LABEL_WIDTH) -> str:
    """`ラベル : 値` の1行を作る。**ラベル名が安定文字列である**（詳細設計14章）。"""
    return f"{label:<{width}}: {value}".rstrip()


def render_table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    """ヘッダ付きの表を作る（詳細設計 16.1 / 16.2）。

    **ヘッダ行は行が0件でも必ず出す。** 「列が何か」は件数に依存しないため。
    """
    materialized = [list(row) for row in rows]
    widths = [len(header) for header in headers]
    for row in materialized:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    lines = [_row(headers, widths)]
    lines.extend(_row(row, widths) for row in materialized)
    return lines


def _row(cells: Sequence[str], widths: Sequence[int]) -> str:
    """最後の列は右側を詰めない（末尾に空白を残さない）。"""
    padded = [
        cell if index == len(cells) - 1 else f"{cell:<{widths[index]}}"
        for index, cell in enumerate(cells)
    ]
    return "  ".join(padded).rstrip()


def task_as_json(task: Task) -> dict[str, Any]:
    """Task の機械可読表現（詳細設計14章 `recent_tasks` / 16.2）。

    時刻は 6.2 の文字列にする。**キーを省略しない**（無い値は `null`）。
    """
    return {
        "task_id": task.task_id,
        "agent": task.agent,
        "type": task.type,
        "status": task.status.value,
        "created_at": _iso(task.created_at),
        "started_at": _iso(task.started_at),
        "completed_at": _iso(task.completed_at),
    }


def agent_as_json(agent: Agent) -> dict[str, Any]:
    """Agent の機械可読表現（詳細設計 14章 `agents` / 16.1）。"""
    return {
        "name": agent.name,
        "version": agent.version,
        "description": agent.description,
    }


def _iso(value: datetime | None) -> str | None:
    return None if value is None else to_iso(value)
