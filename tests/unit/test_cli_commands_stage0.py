"""`doctor` / `status` / `run` / `agent list` / `task list` の単体テスト。

受け入れテスト（S-B / S-C / S-E / S-F / S-I）が見ているのは**シナリオ**である。
ここでは CLI 層固有の分岐、すなわち受け入れテストが踏まない引数の検査・出力の形・
グローバル `--json` の解釈を対象にする。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from click.testing import CliRunner

from media_agent.cli.app import main
from media_agent.cli.commands.run import DEFAULT_AGENT, DEFAULT_INPUT
from media_agent.cli.commands.task import NO_TASKS
from media_agent.core.observability.log import setup_logging
from media_agent.project.scaffold import init_project

#: `--limit` の安定文字列（詳細設計 17.3）。
MSG_LIMIT = "--limit"

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


# -- task list --limit の値域（詳細設計 16.2。T-014 / D-3） ---------------------------


@pytest.mark.parametrize("value", ("0", "-1", "-20"))
def test_task_list_rejects_a_limit_below_one(
    runner: CliRunner, project: Path, value: str
) -> None:
    """`0` 以下は `UsageError`（終了コード 2）。安定文字列は `--limit`（詳細設計 17.3）。"""
    result = _invoke(runner, project, "task", "list", "--limit", value)

    assert result.exit_code == EXIT_USAGE
    assert MSG_LIMIT in result.stderr
    assert result.stdout.strip() == ""


def test_task_list_accepts_the_lower_bound(runner: CliRunner, project: Path) -> None:
    """下限そのもの（`1`）は通る。**上限は設けない**（詳細設計 16.2）。"""
    assert _invoke(runner, project, "task", "list", "--limit", "1").exit_code == EXIT_OK
    assert (
        _invoke(runner, project, "task", "list", "--limit", "100000").exit_code
        == EXIT_OK
    )


def test_task_list_reports_status_before_limit(
    runner: CliRunner, project: Path
) -> None:
    """両方が不正なら `--status` を先に報告する（詳細設計 16.2 の検査の順序）。"""
    result = _invoke(
        runner, project, "task", "list", "--status", "nope", "--limit", "0"
    )

    assert result.exit_code == EXIT_USAGE
    assert "--status" in result.stderr
    assert MSG_LIMIT not in result.stderr


def test_task_list_reports_a_broken_structure_before_the_limit_range(
    runner: CliRunner, project: Path
) -> None:
    """構造破損（1）は値域（2）より先（詳細設計 17.4 の R-7 の順序）。"""
    logs = project / ".media-agent" / "logs"
    shutil.rmtree(logs)
    logs.write_text("これはディレクトリではありません\n", encoding="utf-8")

    result = _invoke(runner, project, "task", "list", "--limit", "0")

    assert result.exit_code == EXIT_RUNTIME_ERROR


# -- open_session の構造検査（詳細設計 15.1 の手順2 / 17.4 の R-4。T-014） -------------


@pytest.mark.parametrize("command", (("status",), ("run",), ("task", "list")))
@pytest.mark.parametrize("name", ("data", "logs"))
def test_runtime_commands_stop_on_a_broken_structure(
    runner: CliRunner, project: Path, command: tuple[str, ...], name: str
) -> None:
    """`data/` `logs/` が通常ファイルなら終了コード 1（**70 ではない**）。"""
    target = project / ".media-agent" / name
    shutil.rmtree(target)
    target.write_text("これはディレクトリではありません\n", encoding="utf-8")

    result = _invoke(runner, project, *command)

    assert result.exit_code == EXIT_RUNTIME_ERROR
    assert "ディレクトリではありません" in result.stderr
    assert "退避" in result.stderr


@pytest.mark.parametrize("command", (("status",), ("run",), ("task", "list")))
@pytest.mark.parametrize("name", ("agents", "memory"))
def test_runtime_commands_ignore_directories_they_do_not_read(
    runner: CliRunner, project: Path, command: tuple[str, ...], name: str
) -> None:
    """`agents/` `memory/` は実行経路が読まないため止まらない（詳細設計 17.4 の R-4）。"""
    target = project / ".media-agent" / name
    shutil.rmtree(target)
    target.write_text("これはディレクトリではありません\n", encoding="utf-8")

    assert _invoke(runner, project, *command).exit_code == EXIT_OK


def test_runtime_commands_do_not_create_the_log_file_when_broken(
    runner: CliRunner, project: Path
) -> None:
    """構造検査は**ログの構成より前**に行う（`logs/` が壊れた状態で開かない）。"""
    logs = project / ".media-agent" / "logs"
    shutil.rmtree(logs)
    logs.write_text("これはディレクトリではありません\n", encoding="utf-8")

    result = _invoke(runner, project, "status")

    assert result.exit_code == EXIT_RUNTIME_ERROR
    assert logs.read_text(encoding="utf-8") == "これはディレクトリではありません\n"


def test_a_database_that_is_not_sqlite_is_reported_as_exit_code_one(
    runner: CliRunner, project: Path
) -> None:
    """種別2（DB が SQLite でない）も終了コード 1（詳細設計 17.4 の R-1）。"""
    db = project / ".media-agent" / "data" / "media-agent.db"
    db.write_text("これは SQLite ではありません\n", encoding="utf-8")

    result = _invoke(runner, project, "status")

    assert result.exit_code == EXIT_RUNTIME_ERROR
    assert "SQLite" in result.stderr
    assert "退避" in result.stderr
