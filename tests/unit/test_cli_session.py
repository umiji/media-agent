"""`cli/session.py` の単体テスト（詳細設計 14章 / 15.1 の手順1〜5）。

準備の**順序**と後片付けを対象にする。順序（ルート解決 → Config → ログ → DB）は
終了コードの優先順位そのものであり、入れ替わると 3/4 の区別が壊れる。
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from media_agent.cli.context import CliContext
from media_agent.cli.session import open_session
from media_agent.core.observability.log import ROOT_LOGGER_NAME, setup_logging
from media_agent.core.runtime import AgentRunner
from media_agent.errors import ConfigError, ProjectNotInitializedError
from media_agent.project.scaffold import init_project


@pytest.fixture(autouse=True)
def _reset_logging() -> None:
    """テスト間でロガーの構成を持ち越さない。"""
    setup_logging()


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    target = tmp_path / "sample-project"
    target.mkdir()
    init_project(target)
    return target


def _context(project: Path) -> CliContext:
    return CliContext(project_dir=project, cwd=project)


def test_session_opens_and_closes_the_connection(project: Path) -> None:
    """接続は必ず閉じる（終了時にプロジェクトの DB を掴んだままにしない）。"""
    with open_session(_context(project)) as session:
        conn = session.conn
        assert conn.execute("SELECT 1").fetchone()[0] == 1

    with pytest.raises(Exception):  # noqa: B017 - sqlite3.ProgrammingError を含む
        conn.execute("SELECT 1")


def test_session_creates_the_database_when_missing(project: Path) -> None:
    """`status` / `run` は DB が無ければ作る（詳細設計14章。`doctor` との非対称）。"""
    layout_db = project / ".media-agent" / "data" / "media-agent.db"
    layout_db.unlink()

    with open_session(_context(project)) as session:
        assert session.layout.db_path.is_file()


def test_session_adds_the_file_log_handler(project: Path) -> None:
    """プロジェクト解決**後**にファイルハンドラを足す（罠 D-T16 / 申し送り L-7）。"""
    with open_session(_context(project)) as session:
        assert session.layout.log_path.is_file()

    handlers = logging.getLogger(ROOT_LOGGER_NAME).handlers
    assert any(getattr(handler, "baseFilename", None) for handler in handlers)


def test_uninitialized_project_is_reported_before_reading_the_config(
    tmp_path: Path,
) -> None:
    """未初期化は Config より先に判定する（終了コード 3 が 4 に隠れない）。"""
    empty = tmp_path / "workspace"
    empty.mkdir()

    with pytest.raises(ProjectNotInitializedError):
        with open_session(CliContext(project_dir=empty, cwd=empty)):
            pass  # pragma: no cover - 例外で到達しない


def test_broken_config_stops_before_the_database_is_touched(project: Path) -> None:
    """Config が読めなければ DB を開く前に止まる（詳細設計 15.1 の手順2 → 4）。"""
    (project / ".media-agent" / "config.yaml").write_text(
        "version: 1\nproject:\n  description: 名前が無い\n", encoding="utf-8"
    )

    with pytest.raises(ConfigError):
        with open_session(_context(project)):
            pass  # pragma: no cover - 例外で到達しない


def test_session_builds_a_runner_from_its_own_parts(project: Path) -> None:
    """`AgentRunner` は Session が持つ Task / Audit から組み立てる（詳細設計 8.3）。"""
    with open_session(_context(project)) as session:
        runner = session.runner()

        assert isinstance(runner, AgentRunner)
        result = runner.run("echo", {"message": "hi"})
        assert result.output is not None
        assert result.output.payload == {"message": "hi"}


def test_run_is_committed_before_the_session_closes(project: Path) -> None:
    """別接続からも実行結果が見える（契約 K-5）。CLI 側で確定を足さない（申し送り M-7）。"""
    import sqlite3

    with open_session(_context(project)) as session:
        task_id = session.runner().run("echo").task.task_id

    conn = sqlite3.connect(str(project / ".media-agent" / "data" / "media-agent.db"))
    try:
        rows = conn.execute(
            "SELECT status FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchall()
    finally:
        conn.close()
    assert rows == [("completed",)]
