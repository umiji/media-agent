"""DB 層（詳細設計6章・7章）。

- 方式: SQLite（標準 `sqlite3`）+ 手書き SQL の Repository 層（方式設計 3.4）
- 版数は `PRAGMA user_version` が持つ。前進のみの Migration（詳細設計 7.1）
- **`sqlite3.Row` をこのパッケージの外へ出さない**（罠 D-T11）

主な公開物を再エクスポートする（申し送り K-1）。
"""

from __future__ import annotations

from media_agent.core.db.connection import connect, ensure_project_db, open_project_db
from media_agent.core.db.migrations import (
    MIGRATIONS,
    SCHEMA_VERSION,
    TABLE_NAMES,
    Migration,
    ensure_schema,
    schema_version,
)
from media_agent.core.db.models import (
    DecisionRow,
    PerformanceRow,
    PostRow,
    ProjectRow,
    SourceRow,
    TaskRow,
)
from media_agent.core.db.repositories import (
    DecisionRepository,
    PerformanceRepository,
    PostRepository,
    ProjectRepository,
    SourceRepository,
    TaskRepository,
)

__all__ = [
    "MIGRATIONS",
    "SCHEMA_VERSION",
    "TABLE_NAMES",
    "DecisionRepository",
    "DecisionRow",
    "Migration",
    "PerformanceRepository",
    "PerformanceRow",
    "PostRepository",
    "PostRow",
    "ProjectRepository",
    "ProjectRow",
    "SourceRepository",
    "SourceRow",
    "TaskRepository",
    "TaskRow",
    "connect",
    "ensure_project_db",
    "ensure_schema",
    "open_project_db",
    "schema_version",
]
