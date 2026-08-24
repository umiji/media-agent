"""`doctor` / `status` / `run` / `agent list` / `task list` の単体テスト。

受け入れテスト（S-B / S-C / S-E / S-F / S-I）が見ているのは**シナリオ**である。
ここでは CLI 層固有の分岐、すなわち受け入れテストが踏まない引数の検査・出力の形・
グローバル `--json` の解釈を対象にする。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from media_agent.cli.app import main
from media_agent.cli.commands.run import DEFAULT_AGENT, DEFAULT_INPUT
from media_agent.cli.commands.task import NO_TASKS
from media_agent.core.observability.log import setup_logging
from media_agent.project.scaffold import init_project

EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_USAGE = 2
EXIT_DOCTOR_FAILED = 5


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    setup_logging()


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    target = tmp_path / "sample-project"
    target.mkdir()
    init_project(target)
    return target


def _invoke(runner: CliRunner, project: Path, *args: str) -> object:
    return runner.invoke(main, ["-C", str(project), *args], catch_exceptions=False)


# -- doctor --------------------------------------------------------------------------


def test_doctor_prints_a_hint_line_under_each_failure(
    runner: CliRunner, project: Path
) -> None:
    """`fail` の行の直後に対処を出す（詳細設計 13.3）。"""
    (project / ".media-agent" / ".gitignore").write_text("# 消した\n", encoding="utf-8")

    result = _invoke(runner, project, "doctor")

    assert result.exit_code == EXIT_DOCTOR_FAILED
    lines = result.stdout.splitlines()
    index = next(i for i, line in enumerate(lines) if "security.gitignore" in line)
    assert lines[index + 1].strip().startswith("→ 対処:")


def test_doctor_does_not_write_the_operational_log(
    runner: CliRunner, project: Path
) -> None:
    """`doctor` は運用ログのファイルも作らない（詳細設計 13.1: 副作用を持たない）。"""
    result = _invoke(runner, project, "doctor")

    assert result.exit_code == EXIT_OK
    assert not (project / ".media-agent" / "logs" / "media-agent.log").exists()


def test_global_json_flag_works_without_the_command_option(
    runner: CliRunner, project: Path
) -> None:
    """`--json` はグローバルにも置ける（方式設計 6.2 / 詳細設計 15.3）。"""
    result = runner.invoke(
        main, ["-C", str(project), "--json", "doctor"], catch_exceptions=False
    )

    assert result.exit_code == EXIT_OK
    assert json.loads(result.stdout)["overall"] == "ok"


# -- status --------------------------------------------------------------------------


def test_status_text_and_json_report_the_same_task_total(
    runner: CliRunner, project: Path
) -> None:
    """テキストと JSON は同じ集計から作る（表示のずれを作らない）。"""
    assert _invoke(runner, project, "run").exit_code == EXIT_OK

    text = _invoke(runner, project, "status").stdout
    payload = json.loads(_invoke(runner, project, "status", "--json").stdout)

    assert f"total {payload['tasks']['total']}" in text


# -- run -----------------------------------------------------------------------------


def test_run_defaults_to_the_echo_agent_and_the_default_payload(
    runner: CliRunner, project: Path
) -> None:
    """既定は `echo` と `{"message": "hello"}`（詳細設計 15.1 のオプション表）。"""
    result = _invoke(runner, project, "run", "--json")

    payload = json.loads(result.stdout)
    assert payload["agent"] == DEFAULT_AGENT
    assert payload["output"] == DEFAULT_INPUT


@pytest.mark.parametrize("bad", ["{not json", "[1, 2]", '"text"', "3"])
def test_run_rejects_input_that_is_not_a_json_object(
    runner: CliRunner, project: Path, bad: str
) -> None:
    """`--input` は JSON オブジェクトに限る。壊れていれば終了コード 2（詳細設計 15.1）。"""
    result = _invoke(runner, project, "run", "--input", bad)

    assert result.exit_code == EXIT_USAGE


def test_run_reports_the_config_error_before_the_usage_error(
    runner: CliRunner, project: Path
) -> None:
    """設定エラー（4）は利用方法の誤り（2）より先に返す（詳細設計 17.2）。"""
    (project / ".media-agent" / "config.yaml").write_text(
        "version: 1\nproject: {}\n", encoding="utf-8"
    )

    result = _invoke(runner, project, "run", "--input", "{not json")

    assert result.exit_code == 4


def test_failed_run_still_prints_json_to_stdout(
    runner: CliRunner, project: Path
) -> None:
    """**失敗時にも標準出力へ JSON を出す**（契約 K-3）。"""
    result = _invoke(runner, project, "run", "--agent", "fail", "--json")

    assert result.exit_code == EXIT_RUNTIME_ERROR
    payload = json.loads(result.stdout)
    assert payload["status"] == "failed"
    assert payload["error"]
    assert payload["output"] is None


def test_failed_run_names_the_task_in_the_error(
    runner: CliRunner, project: Path
) -> None:
    """エラーの要約に `task_id` を含める（記録を引ける形にする）。"""
    result = _invoke(runner, project, "run", "--agent", "fail", "--json")

    assert json.loads(result.stdout)["task_id"] in result.stderr


def test_run_does_not_record_a_policy_check(runner: CliRunner, project: Path) -> None:
    """`run` は Policy Check を呼ばない（詳細設計 15.4 / 申し送り L-9）。"""
    import sqlite3

    assert _invoke(runner, project, "run").exit_code == EXIT_OK

    conn = sqlite3.connect(str(project / ".media-agent" / "data" / "media-agent.db"))
    try:
        kinds = conn.execute("SELECT kind FROM decisions").fetchall()
    finally:
        conn.close()
    assert kinds == [("agent_run",)]


# -- agent list / task list ----------------------------------------------------------


def test_agent_list_does_not_read_the_config(runner: CliRunner, project: Path) -> None:
    """Registry は設定に依存しない（詳細設計 17.2 の注記）。壊れていても一覧は出る。"""
    (project / ".media-agent" / "config.yaml").write_text(":\n:\n", encoding="utf-8")

    result = _invoke(runner, project, "agent", "list")

    assert result.exit_code == EXIT_OK
    assert "echo" in result.stdout


def test_agent_list_does_not_create_the_database(
    runner: CliRunner, project: Path
) -> None:
    """`agent list` は読み取り専用であり、DB を必要としない（詳細設計 16.1）。"""
    db = project / ".media-agent" / "data" / "media-agent.db"
    db.unlink()

    assert _invoke(runner, project, "agent", "list").exit_code == EXIT_OK
    assert not db.exists()


def test_task_list_prints_the_header_and_a_placeholder_when_empty(
    runner: CliRunner, project: Path
) -> None:
    """0件でもヘッダを出し、`(タスクはありません)` を添える（詳細設計 16.2）。"""
    result = _invoke(runner, project, "task", "list")

    assert result.exit_code == EXIT_OK
    assert "TASK_ID" in result.stdout
    assert NO_TASKS in result.stdout


@pytest.mark.parametrize("bad", ["done", "COMPLETED", ""])
def test_task_list_rejects_an_unknown_status(
    runner: CliRunner, project: Path, bad: str
) -> None:
    """`--status` は5つの状態名のいずれか。他は終了コード 2（詳細設計 16.2 / J-10）。"""
    result = _invoke(runner, project, "task", "list", "--status", bad)

    assert result.exit_code == EXIT_USAGE


def test_task_list_honours_the_limit(runner: CliRunner, project: Path) -> None:
    """`--limit` は件数を絞る（既定 20。詳細設計 16.2）。"""
    for _ in range(3):
        assert _invoke(runner, project, "run").exit_code == EXIT_OK

    payload = json.loads(
        _invoke(runner, project, "task", "list", "--limit", "2", "--json").stdout
    )

    assert len(payload["tasks"]) == 2
