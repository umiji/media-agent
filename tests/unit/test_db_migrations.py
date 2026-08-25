"""`core/db/migrations.py` の単体テスト（詳細設計7章）。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from media_agent.core.db.connection import connect
from media_agent.core.db.migrations import (
    MIGRATIONS,
    SCHEMA_VERSION,
    TABLE_NAMES,
    ensure_schema,
    schema_version,
)
from media_agent.errors import DatabaseVersionError


def _tables(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    return {str(row["name"]) for row in rows}


def test_creates_all_six_entities(tmp_path: Path) -> None:
    """要件定義書16節の6 Entity をすべて作る（詳細設計 6.1 / 完了条件1）。"""
    conn = connect(tmp_path / "db" / "media-agent.db")

    assert ensure_schema(conn) == SCHEMA_VERSION
    assert set(TABLE_NAMES) <= _tables(conn)
    assert len(TABLE_NAMES) == 6


def test_records_the_version_in_user_version(tmp_path: Path) -> None:
    """版数の保持先は `PRAGMA user_version` である（詳細設計 7.1）。"""
    conn = connect(tmp_path / "media-agent.db")
    assert schema_version(conn) == 0

    ensure_schema(conn)

    assert schema_version(conn) == SCHEMA_VERSION


def test_is_idempotent_and_executes_nothing_when_up_to_date(tmp_path: Path) -> None:
    """**2回以上実行しても壊れない**（完了条件3 / 詳細設計 7.3）。

    版数が一致していれば SQL を1つも実行しない。`CREATE TABLE IF NOT EXISTS` に頼らない。
    """
    db_path = tmp_path / "media-agent.db"
    conn = connect(db_path)
    ensure_schema(conn)
    conn.execute("INSERT INTO sources VALUES ('s1','t',NULL,'manual',NULL,'ts',NULL)")
    conn.commit()

    assert ensure_schema(conn) == SCHEMA_VERSION
    assert ensure_schema(conn) == SCHEMA_VERSION

    # 既存データが残っていること（破壊的な再適用が起きていないこと）
    assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1


def test_idempotent_across_new_connections(tmp_path: Path) -> None:
    """別の接続で開き直しても同じ（`init` を2回実行した場合に相当する）。"""
    db_path = tmp_path / "media-agent.db"
    first = connect(db_path)
    ensure_schema(first)
    first.close()

    second = connect(db_path)

    assert ensure_schema(second) == SCHEMA_VERSION
    assert set(TABLE_NAMES) <= _tables(second)


def test_refuses_a_newer_database(tmp_path: Path) -> None:
    """実装より新しい DB は**壊さずに止める**（詳細設計 7.2 の2）。"""
    conn = connect(tmp_path / "media-agent.db")
    ensure_schema(conn)
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")

    with pytest.raises(DatabaseVersionError):
        ensure_schema(conn)

    # 版数も内容も書き換えられていない
    assert schema_version(conn) == SCHEMA_VERSION + 1


def test_migrations_are_sequential_and_end_at_schema_version() -> None:
    """一覧は 1 から連番で、末尾が `SCHEMA_VERSION` である（詳細設計 7.1）。"""
    versions = [migration.version for migration in MIGRATIONS]

    assert versions == list(range(1, SCHEMA_VERSION + 1))
    assert all(migration.statements for migration in MIGRATIONS)


def test_a_failing_migration_leaves_no_partial_state(tmp_path: Path) -> None:
    """途中で失敗した Migration は版数もテーブルも残さない（詳細設計 7.3）。"""
    from media_agent.core.db import migrations as module

    broken = module.Migration(
        version=1,
        description="壊れた Migration",
        statements=("CREATE TABLE ok (id TEXT)", "THIS IS NOT SQL"),
    )
    conn = connect(tmp_path / "media-agent.db")

    with pytest.raises(sqlite3.Error):
        module._apply(conn, broken)

    assert schema_version(conn) == 0
    assert "ok" not in _tables(conn)


# --- 版数 2（詳細設計 6.4 / 7.1・7.3。T-012 の D-2） -------------------------------------


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row["name"]) for row in conn.execute(f"PRAGMA table_info({table})")}


def test_version_two_adds_agent_version_to_decisions(tmp_path: Path) -> None:
    """`decisions.agent_version` が要件20.5（再現性）の受け皿である（詳細設計 6.4）。"""
    conn = connect(tmp_path / "db" / "media-agent.db")

    ensure_schema(conn)

    assert "agent_version" in _columns(conn, "decisions")
    conn.close()


def test_a_version_one_database_is_migrated_forward(tmp_path: Path) -> None:
    """版数1 の既存 DB は、次に開いた時点で 2 へ上がる（詳細設計 7.2 の手順3）。

    **Stage 0 の間に Migration の連鎖（0→1→2）が実際に1度走る**（7.3 の副産物）。
    """
    db_path = tmp_path / "db" / "media-agent.db"
    conn = connect(db_path)
    for statement in MIGRATIONS[0].statements:
        conn.execute(statement)
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    assert "agent_version" not in _columns(conn, "decisions")

    assert ensure_schema(conn) == SCHEMA_VERSION

    assert schema_version(conn) == 2
    assert "agent_version" in _columns(conn, "decisions")
    conn.close()


def test_migrating_forward_keeps_existing_rows(tmp_path: Path) -> None:
    """版数 2 は**追加のみ**であり、既存行を書き換えない（共通の停止条件 S-2 の判定）。"""
    db_path = tmp_path / "db" / "media-agent.db"
    conn = connect(db_path)
    for statement in MIGRATIONS[0].statements:
        conn.execute(statement)
    conn.execute("PRAGMA user_version = 1")
    conn.execute(
        "INSERT INTO decisions"
        " (decision_id, kind, agent, task_id, input, decision, reason, action,"
        "  result, error, timestamp)"
        " VALUES ('d1','agent_run','echo',NULL,'{}','completed','理由',"
        "         NULL,NULL,NULL,'2026-01-01T00:00:00.000000Z')"
    )
    conn.commit()

    ensure_schema(conn)

    row = conn.execute("SELECT * FROM decisions WHERE decision_id = 'd1'").fetchone()
    assert row["decision"] == "completed"
    # 既存行は列が増えただけで、値は `NULL`（追加のみ・NULL 可）。
    assert row["agent_version"] is None
    conn.close()
