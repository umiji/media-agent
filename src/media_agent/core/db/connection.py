"""SQLite への接続とプロジェクト DB の初期化（詳細設計 6.3 / 12.4）。

**`core/` はプロジェクト配下のパスを組み立てない**（品質基準 Q7）。DB の場所は
`ProjectPaths`（`project/layout.py` の `ProjectLayout` が構造的に満たす）か `Path` で受け取る。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from media_agent.core.db.migrations import ensure_schema
from media_agent.errors import DatabaseError

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


def _database_error(db_path: Path, exc: BaseException) -> DatabaseError:
    """`sqlite3.Error` / `OSError` を `DatabaseError` へ包む（詳細設計 6.3 / 17.4 の R-1）。

    包まないと、DB が SQLite でない場合や `data/` が通常ファイルの場合に
    **終了コード 70（内部エラー）**で終わる（T-009 / RV-1）。**この層から素の外部例外を
    出さない**（品質基準 Q8）。

    メッセージは**受け取った `Path` だけ**で組み立てる。`.media-agent` という文字列を
    `core/` に書かない（品質基準 Q7）。文面は 17.4.3 が規範。
    """
    return DatabaseError(
        f"{db_path} を SQLite データベースとして開けません",
        details=[_one_line(exc)],
        hint=(
            "このファイルを退避してから media-agent init を実行してください"
            "（init は既存ファイルを削除しません）"
        ),
    )


def _one_line(exc: BaseException) -> str:
    """元の例外を1行にする（詳細設計 17.4.3 の `details`）。"""
    return " ".join(str(exc).splitlines()).strip() or type(exc).__name__


def connect(db_path: Path) -> sqlite3.Connection:
    """親ディレクトリを作成し、接続し、`PRAGMAS` を適用する（詳細設計 6.3）。

    - `row_factory = sqlite3.Row`（列名でアクセスする。位置参照を書かない）
    - **`detect_types` を使わない。** 時刻は 6.2 の文字列として扱い、変換は Repository が行う
    - **`sqlite3.Error` / `OSError` を `DatabaseError`（終了コード 1）へ包む**（17.4 の R-1）
    """
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
    except (sqlite3.Error, OSError) as exc:
        raise _database_error(db_path, exc) from exc
    try:
        conn.row_factory = sqlite3.Row
        for name, value in PRAGMAS:
            # 中身が SQLite でなければ、ここでヘッダを読んで失敗する（`journal_mode`）。
            # 接続の生成自体は遅延するため、失敗は必ずこの位置に現れる。
            conn.execute(f"PRAGMA {name} = {value}")
    except (sqlite3.Error, OSError) as exc:
        conn.close()
        raise _database_error(db_path, exc) from exc
    except BaseException:
        conn.close()
        raise
    return conn


def open_project_db(
    paths: ProjectPaths, config: Config | None = None
) -> sqlite3.Connection:
    """プロジェクトの DB を開き、スキーマを最新にする（詳細設計 6.3）。

    `config` を渡した場合は `projects` 行も同期する（6.5）。**`doctor` は渡さない**
    （副作用を持たないため。13.1）。

    `connect` と同じく、**素の `sqlite3.Error` / `OSError` を外へ出さない**（17.4 の R-1）。
    `DatabaseVersionError` は `MediaAgentError` の階層に属するため、包み直さずそのまま通す。
    """
    conn = connect(paths.db_path)
    try:
        ensure_schema(conn)
        if config is not None:
            from media_agent.core.db.repositories import ProjectRepository

            with conn:
                ProjectRepository(conn).sync(config)
    except (sqlite3.Error, OSError) as exc:
        conn.close()
        raise _database_error(paths.db_path, exc) from exc
    except BaseException:
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
