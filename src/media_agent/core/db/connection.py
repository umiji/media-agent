"""SQLite への接続とプロジェクト DB の初期化（詳細設計 6.3 / 12.4）。

**`core/` は `.media-agent` というパスを組み立てない**（品質基準 Q7）。DB の場所は
`ProjectPaths`（`project/layout.py` の `ProjectLayout` が構造的に満たす）か `Path` で受け取る。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from media_agent.core.db.migrations import ensure_schema

if TYPE_CHECKING:  # pragma: no cover - 型注釈のためだけの参照
    from media_agent.core.config.models import Config

__all__ = ["PRAGMAS", "ProjectPaths", "connect", "ensure_project_db", "open_project_db"]

#: 接続ごとに適用する PRAGMA（詳細設計 6.3）。
#:
#: - `foreign_keys`: SQLite の既定は OFF。外部キーが黙って効かない（罠 T-2）
#: - `journal_mode` / `synchronous`: 読み書きの競合を減らす標準的な組み合わせ
#: - `busy_timeout`: 別プロセスが書き込み中でも即座に失敗させない
PRAGMAS: tuple[tuple[str, str], ...] = (
    ("foreign_keys", "ON"),
    ("journal_mode", "WAL"),
    ("synchronous", "NORMAL"),
    ("busy_timeout", "5000"),
)


@runtime_checkable
class ProjectPaths(Protocol):
    """DB の置き場所を知っているオブジェクト（`ProjectLayout` が満たす）。

    `core/` から `project/` を import しないために、構造的な型で受け取る
    （方式設計 5.2 の依存の向き / 詳細設計 4.1）。
    """

    @property
    def db_path(self) -> Path: ...


def connect(db_path: Path) -> sqlite3.Connection:
    """親ディレクトリを作成し、接続し、`PRAGMAS` を適用する（詳細設計 6.3）。

    - `row_factory = sqlite3.Row`（列名でアクセスする。位置参照を書かない）
    - **`detect_types` を使わない。** 時刻は 6.2 の文字列として扱い、変換は Repository が行う
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    for name, value in PRAGMAS:
        conn.execute(f"PRAGMA {name} = {value}")
    return conn


def open_project_db(
    paths: ProjectPaths, config: Config | None = None
) -> sqlite3.Connection:
    """プロジェクトの DB を開き、スキーマを最新にする（詳細設計 6.3）。

    `config` を渡した場合は `projects` 行も同期する（6.5）。**`doctor` は渡さない**
    （副作用を持たないため。13.1）。
    """
    conn = connect(paths.db_path)
    try:
        ensure_schema(conn)
        if config is not None:
            from media_agent.core.db.repositories import ProjectRepository

            with conn:
                ProjectRepository(conn).sync(config)
    except Exception:
        conn.close()
        raise
    return conn


def ensure_project_db(paths: ProjectPaths, config: Config | None = None) -> Path:
    """DB ファイルを用意して閉じ、そのパスを返す（詳細設計 12.4。`init` の接続点）。

    `open_project_db` と同じことを行い、接続を持ち帰らない。`init` は DB を使わず、
    **存在させるだけ**であるため。
    """
    conn = open_project_db(paths, config)
    conn.close()
    return paths.db_path
