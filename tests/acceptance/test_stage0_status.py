"""S-C: `media-agent status` の出力。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-003 完了条件2 S-C / 要件定義書18節 Stage 0 の検証条件・10節 |
| 期待値の正典 | 詳細設計 19章 S-C 行 → 詳細設計14章 |
| 判定の軸 | ラベル名（安定文字列）と `--json` のキー。表示値の文面では判定しない |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.acceptance.expectations import (
    BUILTIN_AGENTS,
    EXIT_OK,
    MSG_NO_TASKS,
    STATUS_LABELS,
    TASK_STATUSES,
    CliInvoke,
    db_path,
    parse_json,
    parse_labelled_output,
)

pytestmark = pytest.mark.acceptance


def test_status_prints_every_label(initialized_project: Path, cli: CliInvoke) -> None:
    """`init` 済みで `status` は終了コード 0 で、14章のラベルをすべて出す。"""
    result = cli("status", project=initialized_project)

    assert result.exit_code == EXIT_OK, result.output
    labels = parse_labelled_output(result.stdout)
    for label in STATUS_LABELS:
        assert label in labels, f"ラベル {label} が出力にない: {result.stdout}"
    assert labels["project"] == initialized_project.name


def test_status_json_reports_agents_and_all_task_statuses(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`--json` の `agents` に `echo` があり、`tasks.by_status` に5状態すべてのキーがある。

    出所: 詳細設計 19章 S-C 行 / 14章。
    """
    result = cli("status", "--json", project=initialized_project)

    assert result.exit_code == EXIT_OK, result.output
    payload = parse_json(result.stdout)
    assert payload["project_name"] == initialized_project.name
    assert {agent["name"] for agent in payload["agents"]} == set(BUILTIN_AGENTS)
    assert set(payload["tasks"]["by_status"]) == set(TASK_STATUSES)
    assert payload["tasks"]["total"] == 0
    assert payload["recent_tasks"] == []


def test_status_reports_schema_version_of_the_database(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`database.schema_version` が実装の `SCHEMA_VERSION` と一致する（詳細設計 6.4 / 7章）。"""
    from media_agent.core.db.migrations import SCHEMA_VERSION

    payload = parse_json(cli("status", "--json", project=initialized_project).stdout)

    assert payload["database"]["schema_version"] == SCHEMA_VERSION


def test_status_shows_placeholder_when_no_task_exists(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """タスクが0件のときは `(タスクはありません)` を出す（詳細設計14章）。"""
    result = cli("status", project=initialized_project)

    assert MSG_NO_TASKS in result.stdout


def test_status_reflects_executed_task(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`run` で実行した Task が `status` から観測できる（要件定義書10節）。"""
    assert (
        cli("run", "--agent", "echo", project=initialized_project).exit_code == EXIT_OK
    )

    payload = parse_json(cli("status", "--json", project=initialized_project).stdout)

    assert payload["tasks"]["total"] == 1
    assert payload["tasks"]["by_status"]["completed"] == 1
    assert payload["recent_tasks"][0]["agent"] == "echo"
    assert payload["recent_tasks"][0]["status"] == "completed"


def test_status_creates_the_database_when_missing(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`status` は `ensure_project_db` を呼ぶ。DB が無ければ作る（詳細設計14章）。

    `doctor`（副作用なし）との非対称は意図されたものである。
    """
    db_path(initialized_project).unlink(missing_ok=True)

    result = cli("status", project=initialized_project)

    assert result.exit_code == EXIT_OK, result.output
    assert db_path(initialized_project).is_file()
