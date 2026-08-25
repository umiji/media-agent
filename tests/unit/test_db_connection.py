"""`core/db/connection.py` の単体テスト（詳細設計 6.3 / 6.5 / 12.4）。"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from media_agent.core.config.models import Config
from media_agent.core.db.connection import (
    connect,
    ensure_project_db,
    open_project_db,
)
from media_agent.core.db.migrations import SCHEMA_VERSION, schema_version
from media_agent.core.db.repositories import ProjectRepository
from media_agent.errors import DatabaseError, DatabaseVersionError
from media_agent.project.layout import layout_for


def _config(name: str = "sample-project") -> Config:
    return Config.model_validate({"version": 1, "project": {"name": name}})


def test_connect_creates_the_parent_directory(tmp_path: Path) -> None:
    """親ディレクトリが無ければ作る（詳細設計 6.3）。"""
    db_path = tmp_path / "nested" / "data" / "media-agent.db"

    conn = connect(db_path)

    assert db_path.is_file()
    conn.close()


def test_connect_applies_the_designed_pragmas(tmp_path: Path) -> None:
    """外部キーが**黙って効かない**状態を作らない（罠 T-2）。"""
    conn = connect(tmp_path / "media-agent.db")

    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    assert conn.row_factory is sqlite3.Row


def test_foreign_keys_are_enforced(tmp_path: Path) -> None:
    """宣言した外部キーが実際に効く（詳細設計 6.2）。"""
    conn = open_project_db(layout_for(tmp_path))

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO performances"
            " (performance_id, post_id, collected_at) VALUES ('p1','missing','ts')"
        )
    conn.close()


def test_open_project_db_prepares_the_schema(tmp_path: Path) -> None:
    """接続と同時にスキーマを最新にする（詳細設計 6.3）。"""
    conn = open_project_db(layout_for(tmp_path))

    assert schema_version(conn) == SCHEMA_VERSION
    conn.close()


def test_open_project_db_syncs_the_project_row_when_config_is_given(
    tmp_path: Path,
) -> None:
    """`config` を渡したときだけ `projects` を同期する（詳細設計 6.5）。"""
    layout = layout_for(tmp_path)

    without_config = open_project_db(layout)
    assert ProjectRepository(without_config).get() is None
    without_config.close()

    with_config = open_project_db(layout, _config("with-config"))
    row = ProjectRepository(with_config).get()
    assert row is not None
    assert row.name == "with-config"
    with_config.close()


def test_ensure_project_db_creates_the_file_and_closes(tmp_path: Path) -> None:
    """`init` の接続点。DB を用意して閉じる（詳細設計 12.4）。"""
    layout = layout_for(tmp_path)

    db_path = ensure_project_db(layout, _config())

    assert db_path == layout.db_path
    assert db_path.is_file()
    # 接続が閉じられていれば WAL の副産物は残らない
    assert not (layout.db_path.parent / "media-agent.db-wal").exists()


def test_databases_are_isolated_per_project(tmp_path: Path) -> None:
    """**Memory は他プロジェクトと完全分離する**（要件定義書5.4節 / 完了条件2）。"""
    first = tmp_path / "alpha"
    second = tmp_path / "beta"
    first.mkdir()
    second.mkdir()

    first_layout = layout_for(first)
    second_layout = layout_for(second)
    ensure_project_db(first_layout, _config("alpha"))
    ensure_project_db(second_layout, _config("beta"))

    assert first_layout.db_path != second_layout.db_path
    assert first_layout.db_path.is_file()
    assert second_layout.db_path.is_file()

    first_conn = connect(first_layout.db_path)
    second_conn = connect(second_layout.db_path)
    first_row = ProjectRepository(first_conn).get()
    second_row = ProjectRepository(second_conn).get()
    assert first_row is not None and first_row.name == "alpha"
    assert second_row is not None and second_row.name == "beta"
    assert first_row.project_id != second_row.project_id
    first_conn.close()
    second_conn.close()


def test_layout_satisfies_the_project_paths_protocol(tmp_path: Path) -> None:
    """`core/` は `ProjectLayout` を**構造的に**受け取る（方式設計 5.2 / 詳細設計 4.1）。"""
    from media_agent.core.db.connection import ProjectPaths

    assert isinstance(layout_for(tmp_path), ProjectPaths)


# --- 例外の包み込み（詳細設計 6.3 / 17.4 の R-1。T-014） ---------------------------------


def test_connect_wraps_a_file_that_is_not_sqlite(tmp_path: Path) -> None:
    """SQLite でないファイルは `DatabaseError`（終了コード 1）になる。

    **素の `sqlite3.Error` を CLI 層へ通さない**（品質基準 Q8）。通すと終了コード
    70（内部エラー）で終わる（T-009 / RV-1）。安定文字列は絶対パスと `SQLite`、
    Hint の `退避` と `media-agent init`（詳細設計 17.3 / 17.4.3）。
    """
    db_path = tmp_path / "media-agent.db"
    db_path.write_text("これは SQLite データベースではありません\n", encoding="utf-8")

    with pytest.raises(DatabaseError) as excinfo:
        connect(db_path)

    assert str(db_path) in excinfo.value.message
    assert "SQLite" in excinfo.value.message
    assert "退避" in (excinfo.value.hint or "")
    assert "media-agent init" in (excinfo.value.hint or "")
    assert excinfo.value.exit_code == 1


def test_connect_keeps_the_original_reason_as_a_detail(tmp_path: Path) -> None:
    """元の例外は1行の `details` として残す（詳細設計 17.4.3）。"""
    db_path = tmp_path / "media-agent.db"
    db_path.write_text("SQLite ではない\n", encoding="utf-8")

    with pytest.raises(DatabaseError) as excinfo:
        connect(db_path)

    assert excinfo.value.details
    assert "\n" not in excinfo.value.details[0]


def test_connect_wraps_a_parent_that_is_a_regular_file(tmp_path: Path) -> None:
    """親（`data/`）が通常ファイルなら `OSError` を包む（詳細設計 6.3）。"""
    data_dir = tmp_path / "data"
    data_dir.write_text("これはディレクトリではありません\n", encoding="utf-8")

    with pytest.raises(DatabaseError):
        connect(data_dir / "media-agent.db")


def test_connect_does_not_leak_a_connection_when_it_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """失敗した接続を握ったままにしない（`sqlite3.connect` は遅延して開く）。

    中身が SQLite でないことは PRAGMA の適用まで判明しない。そこで失敗したときに
    接続を閉じないと、開いたままの接続が積もる。
    """
    db_path = tmp_path / "media-agent.db"
    db_path.write_text("SQLite ではない\n", encoding="utf-8")
    opened: list[sqlite3.Connection] = []
    original = sqlite3.connect

    def _spy(*args: Any, **kwargs: Any) -> sqlite3.Connection:
        conn = original(*args, **kwargs)
        opened.append(conn)
        return conn

    monkeypatch.setattr(sqlite3, "connect", _spy)

    with pytest.raises(DatabaseError):
        connect(db_path)

    assert opened, "接続そのものは作られている（失敗するのは PRAGMA の適用）"
    for conn in opened:
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")


def test_open_project_db_wraps_failures_too(tmp_path: Path) -> None:
    """`open_project_db` も素の外部例外を出さない（詳細設計 6.3）。"""
    layout = layout_for(tmp_path)
    layout.db_path.parent.mkdir(parents=True)
    layout.db_path.write_text("SQLite ではない\n", encoding="utf-8")

    with pytest.raises(DatabaseError):
        open_project_db(layout)


def test_database_version_error_is_not_rewrapped(tmp_path: Path) -> None:
    """版数が新しすぎる DB は `DatabaseVersionError` のまま通す（詳細設計 7.2）。

    `MediaAgentError` の階層に属する例外を、`DatabaseError` で包み直さない。
    """
    layout = layout_for(tmp_path)
    conn = connect(layout.db_path)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.close()

    with pytest.raises(DatabaseVersionError):
        open_project_db(layout)


def test_ensure_project_db_wraps_failures(tmp_path: Path) -> None:
    """`init` の接続点（詳細設計 12.4）も同じ扱いにする。"""
    layout = layout_for(tmp_path)
    layout.db_path.parent.mkdir(parents=True)
    layout.db_path.write_text("SQLite ではない\n", encoding="utf-8")

    with pytest.raises(DatabaseError):
        ensure_project_db(layout)
