"""`core/db/connection.py` の単体テスト（詳細設計 6.3 / 6.5 / 12.4）。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from media_agent.core.config.models import Config
from media_agent.core.db.connection import (
    connect,
    ensure_project_db,
    open_project_db,
)
from media_agent.core.db.migrations import SCHEMA_VERSION, schema_version
from media_agent.core.db.repositories import ProjectRepository
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
