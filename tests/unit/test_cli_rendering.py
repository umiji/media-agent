"""`cli/rendering.py` の単体テスト（詳細設計 13.3 / 14章 / 15.2 / 16章）。

**安定文字列の形**（ラベル・表のヘッダ・時刻の書式）を対象にする。表示の内容そのものは
受け入れテストが判定するため、ここでは組み立ての規則だけを見る。
"""

from __future__ import annotations

from datetime import UTC, datetime

from media_agent.agents.builtin import EchoAgent
from media_agent.cli.rendering import (
    STATUS_LABEL_WIDTH,
    agent_as_json,
    compact_json,
    labelled,
    render_table,
    task_as_json,
)
from media_agent.core.task import Task, TaskStatus

_NOW = datetime(2026, 8, 23, 10, 0, 0, 123456, tzinfo=UTC)


def _task(**overrides: object) -> Task:
    values: dict[str, object] = {
        "task_id": "0a1b2c3d",
        "agent": "echo",
        "type": "agent_run",
        "status": TaskStatus.completed,
        "input": {},
        "output": {"message": "hi"},
        "created_at": _NOW,
        "started_at": _NOW,
        "completed_at": _NOW,
    }
    values.update(overrides)
    return Task(**values)  # type: ignore[arg-type]


def test_label_is_left_aligned_to_the_designed_width() -> None:
    """ラベルは左詰め13文字 + `: `（詳細設計14章）。"""
    line = labelled("project", "sample")

    assert line == "project      : sample"
    assert line.index(":") == STATUS_LABEL_WIDTH


def test_label_without_a_value_has_no_trailing_space() -> None:
    """値の無いラベル行（`recent tasks`）は末尾に空白を残さない。"""
    assert labelled("recent tasks") == "recent tasks :"


def test_table_prints_the_header_even_with_no_rows() -> None:
    """行が0件でもヘッダは出す（詳細設計 16.1 / 16.2）。"""
    lines = render_table(("NAME", "VERSION"), [])

    assert lines == ["NAME  VERSION"]


def test_table_columns_are_aligned_to_the_widest_cell() -> None:
    """列幅は最も広いセルに合わせる。最後の列は右を詰めない。"""
    lines = render_table(("NAME", "VERSION"), [("echo", "1"), ("longer-name", "10")])

    assert lines[1].startswith("echo         ")
    assert not any(line.endswith(" ") for line in lines)


def test_compact_json_has_no_spaces() -> None:
    """テキスト出力の1行に埋める JSON は空白を含まない（詳細設計 15.2）。"""
    assert compact_json({"message": "hi", "n": 1}) == '{"message":"hi","n":1}'


def test_compact_json_keeps_non_ascii_readable() -> None:
    """日本語をエスケープしない（人間向けの行に出すため）。"""
    assert compact_json({"m": "こんにちは"}) == '{"m":"こんにちは"}'


def test_task_json_uses_the_designed_timestamp_format() -> None:
    """時刻は 6.2 の形式（UTC・マイクロ秒・末尾 `Z`）にする。"""
    payload = task_as_json(_task())

    assert payload["created_at"] == "2026-08-23T10:00:00.123456Z"


def test_task_json_keeps_every_key_even_when_unset() -> None:
    """**キーを省略しない。** 値が無い場合は `null`（詳細設計 11.3 と同じ考え方）。"""
    payload = task_as_json(
        _task(status=TaskStatus.pending, started_at=None, completed_at=None)
    )

    assert set(payload) == {
        "task_id",
        "agent",
        "type",
        "status",
        "created_at",
        "started_at",
        "completed_at",
    }
    assert payload["started_at"] is None
    assert payload["completed_at"] is None


def test_agent_json_reports_name_version_and_description() -> None:
    """`agent list` / `status` が使う3項目（詳細設計 16.1）。"""
    payload = agent_as_json(EchoAgent())

    assert payload["name"] == "echo"
    assert payload["version"] == EchoAgent.version
    assert payload["description"]
