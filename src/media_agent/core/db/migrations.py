"""スキーマ版数と Migration（詳細設計7章。DDL は 6.4）。

**`PRAGMA user_version` が版数の唯一の保持先である。**（7.1）
前進のみの連番 Migration をこのモジュールの一覧で管理する。

満たす性質（7.3）:

- 版数が一致していれば SQL を1つも実行しない。**`CREATE TABLE IF NOT EXISTS` に頼らない**
- Migration ごとに1トランザクション。失敗したら版数も更新されない
- 版数は DB 自身が持つ。設定ファイルにも Python の版数にも依存しない
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from media_agent.errors import DatabaseVersionError

__all__ = [
    "MIGRATIONS",
    "SCHEMA_VERSION",
    "Migration",
    "ensure_schema",
    "schema_version",
]

#: この実装が期待する DB スキーマ版数（詳細設計 7.1）。`config.version` とも
#: パッケージ版数とも独立である（用語集「スキーマ版数」）。
SCHEMA_VERSION = 1

#: 版数 1 が作るテーブル（要件定義書16節の6 Entity）。`doctor` の `db.schema` 検査が使う。
TABLE_NAMES: tuple[str, ...] = (
    "projects",
    "sources",
    "posts",
    "performances",
    "tasks",
    "decisions",
)


@dataclass(frozen=True)
class Migration:
    """1回分の前進 Migration（詳細設計 7.1）。"""

    version: int
    description: str
    statements: tuple[str, ...]


_V1_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE projects (
        project_id    TEXT PRIMARY KEY,
        name          TEXT NOT NULL,
        configuration TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        updated_at    TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE sources (
        source_id    TEXT PRIMARY KEY,
        title        TEXT NOT NULL,
        url          TEXT,
        source_type  TEXT NOT NULL,
        content      TEXT,
        collected_at TEXT NOT NULL,
        score        REAL
    )
    """,
    "CREATE INDEX idx_sources_collected_at ON sources (collected_at)",
    "CREATE INDEX idx_sources_url          ON sources (url)",
    """
    CREATE TABLE posts (
        post_id      TEXT PRIMARY KEY,
        content      TEXT NOT NULL,
        topic        TEXT,
        source_id    TEXT REFERENCES sources (source_id),
        status       TEXT NOT NULL
            CHECK (status IN ('draft','approved','scheduled','published','rejected','failed')),
        created_at   TEXT NOT NULL,
        scheduled_at TEXT,
        published_at TEXT
    )
    """,
    "CREATE INDEX idx_posts_status       ON posts (status)",
    "CREATE INDEX idx_posts_created_at   ON posts (created_at)",
    "CREATE INDEX idx_posts_published_at ON posts (published_at)",
    """
    CREATE TABLE performances (
        performance_id TEXT PRIMARY KEY,
        post_id        TEXT NOT NULL REFERENCES posts (post_id),
        impressions    INTEGER,
        likes          INTEGER,
        replies        INTEGER,
        reposts        INTEGER,
        collected_at   TEXT NOT NULL,
        UNIQUE (post_id, collected_at)
    )
    """,
    "CREATE INDEX idx_performances_post_id ON performances (post_id)",
    """
    CREATE TABLE tasks (
        task_id      TEXT PRIMARY KEY,
        agent        TEXT NOT NULL,
        type         TEXT NOT NULL,
        status       TEXT NOT NULL
            CHECK (status IN ('pending','running','completed','failed','cancelled')),
        input        TEXT NOT NULL,
        output       TEXT,
        error        TEXT,
        created_at   TEXT NOT NULL,
        started_at   TEXT,
        completed_at TEXT
    )
    """,
    "CREATE INDEX idx_tasks_status     ON tasks (status)",
    "CREATE INDEX idx_tasks_created_at ON tasks (created_at)",
    "CREATE INDEX idx_tasks_agent      ON tasks (agent)",
    """
    CREATE TABLE decisions (
        decision_id TEXT PRIMARY KEY,
        kind        TEXT NOT NULL
            CHECK (kind IN ('agent_run','policy_check')),
        agent       TEXT NOT NULL,
        task_id     TEXT REFERENCES tasks (task_id),
        input       TEXT NOT NULL,
        decision    TEXT NOT NULL,
        reason      TEXT NOT NULL,
        action      TEXT,
        result      TEXT,
        error       TEXT,
        timestamp   TEXT NOT NULL
    )
    """,
    "CREATE INDEX idx_decisions_timestamp ON decisions (timestamp)",
    "CREATE INDEX idx_decisions_task_id   ON decisions (task_id)",
    "CREATE INDEX idx_decisions_kind_action_ts ON decisions (kind, action, timestamp)",
)

#: 適用順の Migration 一覧。**過去の要素を書き換えない。** 既存の DB は適用済みであり、
#: 書き換えても再実行されないため、実体とコードが食い違う（変更は新しい version を足す）。
MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version=1,
        description="Stage 0 の6 Entity を作成する",
        statements=_V1_STATEMENTS,
    ),
)


def schema_version(conn: sqlite3.Connection) -> int:
    """現在の `PRAGMA user_version`（新規ファイルは 0）。"""
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0])


def ensure_schema(conn: sqlite3.Connection) -> int:
    """未適用の Migration を順に適用し、適用後の版数を返す（詳細設計 7.2）。

    **何度呼んでも壊れない。** 版数が `SCHEMA_VERSION` に一致していれば SQL を実行しない。

    Raises:
        DatabaseVersionError: DB の版数が実装より新しい（新しい DB を古い実装で開いた）。
            **壊さずに止める。**
    """
    current = schema_version(conn)
    if current > SCHEMA_VERSION:
        raise DatabaseVersionError(
            f"DB のスキーマ版数 {current} は、この実装（対応版数 {SCHEMA_VERSION}）では扱えません",
            hint="Media Agent を更新してください",
        )
    for migration in MIGRATIONS:
        if migration.version <= current:
            continue
        _apply(conn, migration)
        current = migration.version
    return current


def _apply(conn: sqlite3.Connection, migration: Migration) -> None:
    """1つの Migration を1トランザクションで適用する（詳細設計 7.2 の3）。

    `sqlite3` は DDL では暗黙のトランザクションを開始しないため、明示的に `BEGIN` する。
    版数の更新まで含めて1つの単位にしないと、部分適用が残る。
    """
    conn.execute("BEGIN")
    try:
        for statement in migration.statements:
            conn.execute(statement)
        # PRAGMA はプレースホルダを取れない。`version` は int のみを許す型注釈で守る。
        conn.execute(f"PRAGMA user_version = {int(migration.version)}")
    except Exception:
        conn.rollback()
        raise
    conn.commit()
