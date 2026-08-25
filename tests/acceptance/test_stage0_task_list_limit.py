"""S-J（T-012 / 19.1）: `task list --limit` の値域（D-3）。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-013 完了条件1 / 詳細設計 19.1 の S-J 行 |
| 期待値の正典 | 詳細設計 16.2 の `--limit` の値域表 / 17.3 の `--limit` 行 |
| 由来 | T-009 の指摘 RV-6。`--limit -1` が SQLite の `LIMIT -1`（無制限）になり、`--limit 0` は行があるのに `(タスクはありません)` と出ていた |
| 判定の軸 | 終了コードと安定文字列 `--limit` だけ。文面全体は判定しない |

**記号の衝突についての注記**: 詳細設計 19.1 は本シナリオを `S-J` と呼ぶが、T-008 が
`S-J`（プロジェクト分離・`test_stage0_project_isolation.py`）を先に使っている。
**別物である。** 本ファイルが指すのは 19.1 の S-J（`--limit` の値域）である。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.acceptance.expectations import (
    EXIT_NOT_INITIALIZED,
    EXIT_OK,
    EXIT_USAGE,
    MSG_LIMIT_OPTION,
    MSG_STATUS_OPTION,
    CliInvoke,
    parse_json,
)

pytestmark = pytest.mark.acceptance

#: 値域の外（詳細設計 16.2: `0` 以下の整数）。
OUT_OF_RANGE: tuple[str, ...] = ("0", "-1", "-20")


@pytest.fixture()
def project_with_two_tasks(initialized_project: Path, cli: CliInvoke) -> Path:
    """Task が2件ある初期化済みプロジェクト（`--limit` の効き目を判定するため）。"""
    for _ in range(2):
        assert (
            cli("run", "--agent", "echo", project=initialized_project).exit_code
            == EXIT_OK
        )
    return initialized_project


@pytest.mark.parametrize("value", OUT_OF_RANGE)
def test_limit_below_one_is_a_usage_error(
    project_with_two_tasks: Path, cli: CliInvoke, value: str
) -> None:
    """`--limit` が 1 未満なら終了コード 2（詳細設計 16.2 の値域表）。

    `--status` と扱いを揃える。**行があるのに `(タスクはありません)` と出す挙動や、
    負値を「無制限」として受け付ける挙動は仕様ではない**（RV-6）。
    """
    result = cli("task", "list", "--limit", value, project=project_with_two_tasks)

    assert result.exit_code == EXIT_USAGE, result.output
    assert MSG_LIMIT_OPTION in result.stderr


@pytest.mark.parametrize("value", OUT_OF_RANGE)
def test_out_of_range_limit_prints_no_task_table(
    project_with_two_tasks: Path, cli: CliInvoke, value: str
) -> None:
    """値域違反のときは一覧を出さない（利用者が「Task が無い」と読む状態を作らない）。"""
    result = cli("task", "list", "--limit", value, project=project_with_two_tasks)

    assert result.stdout.strip() == "", result.output


def test_limit_one_returns_exactly_one_row(
    project_with_two_tasks: Path, cli: CliInvoke
) -> None:
    """`--limit 1` は 0 で終わり、1件だけ返す（詳細設計 16.2）。"""
    result = cli(
        "task", "list", "--limit", "1", "--json", project=project_with_two_tasks
    )

    assert result.exit_code == EXIT_OK, result.output
    assert len(parse_json(result.stdout)["tasks"]) == 1


def test_no_upper_bound_is_imposed_on_limit(
    project_with_two_tasks: Path, cli: CliInvoke
) -> None:
    """**上限は設けない**（詳細設計 16.2）。大きな値も 0 で受け付ける。"""
    result = cli(
        "task", "list", "--limit", "100000", "--json", project=project_with_two_tasks
    )

    assert result.exit_code == EXIT_OK, result.output
    assert len(parse_json(result.stdout)["tasks"]) == 2


def test_uninitialized_project_is_reported_before_the_limit_range(
    project_dir: Path, cli: CliInvoke
) -> None:
    """未初期化なら値域より先に 3（詳細設計 16.2 の「検査の場所と順序」/ 17.4 の R-7）。

    値域の検査は `open_session` でプロジェクトを開いた**後**に行う。したがって
    17.2 の1行目（未初期化 = 3）と食い違わない。
    """
    result = cli("task", "list", "--limit", "0", project=project_dir)

    assert result.exit_code == EXIT_NOT_INITIALIZED, result.output


@pytest.mark.parametrize("value", ("abc", "1.5"))
def test_non_integer_limit_is_handled_by_click(
    project_dir: Path, cli: CliInvoke, value: str
) -> None:
    """整数に解釈できない値は Click の型変換が処理する（詳細設計 16.2）。

    型変換だけはプロジェクトの解決より前に起きるため、**未初期化でも 2** になる。
    これは Click の既定であり、本設計はそれに従う。
    """
    result = cli("task", "list", "--limit", value, project=project_dir)

    assert result.exit_code == EXIT_USAGE, result.output


def test_invalid_status_is_reported_before_invalid_limit(
    project_with_two_tasks: Path, cli: CliInvoke
) -> None:
    """`--status` と `--limit` が両方不正なら `--status` を先に報告する（詳細設計 16.2）。"""
    result = cli(
        "task",
        "list",
        "--status",
        "nope",
        "--limit",
        "0",
        project=project_with_two_tasks,
    )

    assert result.exit_code == EXIT_USAGE, result.output
    assert MSG_STATUS_OPTION in result.stderr
    assert MSG_LIMIT_OPTION not in result.stderr
