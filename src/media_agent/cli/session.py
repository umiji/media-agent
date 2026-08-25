"""プロジェクトを開いてから閉じるまでの手順を1箇所にまとめる（詳細設計 14章 / 15.1）。

`status` / `run` / `task list` は、いずれも次の順で準備する。**順序に意味がある。**

1. プロジェクトルートの解決（未初期化なら終了コード 3）
2. `load_config()`（不正なら終了コード 4）
3. `setup_logging()` にファイルハンドラを追加する（**ルート解決後**。罠 D-T16）
4. `open_project_db()`（無ければ作る。`projects` 行も同期する）

`doctor` はこの経路を通らない。**副作用を持たない**（13.1）ため、DB を作らず
運用ログのファイルも作らない。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from logging import Logger
from pathlib import Path

from media_agent.agents.builtin import build_default_registry
from media_agent.cli.context import CliContext
from media_agent.core.config.loader import load_config
from media_agent.core.config.models import Config, LogLevel
from media_agent.core.db.connection import open_project_db
from media_agent.core.db.repositories import DecisionRepository, TaskRepository
from media_agent.core.observability.audit import AuditRecorder
from media_agent.core.observability.log import get_logger, setup_logging
from media_agent.core.runtime import AgentRegistry, AgentRunner
from media_agent.core.task import TaskService
from media_agent.project.layout import (
    ProjectLayout,
    verify_not_a_directory,
    verify_project_structure,
)

__all__ = ["ProjectSession", "open_session", "setup_cli_logging", "verify_structure"]


@dataclass(frozen=True)
class ProjectSession:
    """1回のコマンド実行が使う、組み立て済みのプロジェクト一式。"""

    layout: ProjectLayout
    config: Config
    conn: sqlite3.Connection
    logger: Logger
    registry: AgentRegistry
    tasks: TaskService
    decisions: DecisionRepository
    audit: AuditRecorder

    def runner(self) -> AgentRunner:
        """`AgentRunner` を組み立てる（詳細設計 8.3）。

        Runner は `TaskService` と `AuditRecorder` を**受け取る**。ここが唯一の
        組み立て場所であり、CLI 側で Task の確定（commit）を追加しない
        （申し送り M-7。`AuditRecorder` の記録が Task の更新も一緒に確定させる）。
        """
        return AgentRunner(
            registry=self.registry,
            tasks=self.tasks,
            audit=self.audit,
            logger=self.logger,
            config=self.config,
            project_root=self.layout.root,
        )


def setup_cli_logging(
    cli_ctx: CliContext,
    *,
    log_path: Path | None,
    level: LogLevel = LogLevel.INFO,
) -> None:
    """運用ログを構成する（詳細設計 11.2）。

    `log_path` が `None` のときはファイルへ出さない。**`doctor` がこれを使う** —
    運用ログのファイルを作ること自体が副作用になるため（13.1）。
    """
    setup_logging(
        level=level,
        log_path=log_path,
        verbose=cli_ctx.verbose,
        quiet=cli_ctx.quiet,
    )


def verify_structure(layout: ProjectLayout) -> None:
    """このコマンド群が必要とする構造だけを検査する（詳細設計 17.4 の R-4 / 15.1 の手順2）。

    検査対象は **`data/`・`logs/`・`db_path` の3つ**である。`agents/` `memory/` は
    Stage 0 の実行経路が読まないため、壊れていても止めない（17.2 の最終行）。

    **`run` だけの検査にしない**（15.1）。`status` / `run` / `task list` が同じ経路を通ることで、
    3コマンドの終了コードが 17.2 の1行に揃う。
    """
    verify_project_structure(layout, paths=(layout.data_dir, layout.logs_dir))
    verify_not_a_directory(layout.db_path)


@contextmanager
def open_session(cli_ctx: CliContext) -> Iterator[ProjectSession]:
    """プロジェクトを開き、終了時に必ず接続を閉じる。

    **異常の優先順位は検査の順序で固定する**（詳細設計 17.4 の R-7）:
    未初期化（3） → 構造破損（1） → 設定エラー（4） → オプションの値域（2）。
    値域の検査は呼び出し側（`task list`）が `with` の内側で行う。

    Raises:
        ProjectNotInitializedError: 未初期化（終了コード 3）
        ProjectStructureError: 構造破損の種別1（終了コード 1）
        DatabaseError: 構造破損の種別2（終了コード 1）
        ConfigError: `config.yaml` が読めない（終了コード 4）
    """
    layout = cli_ctx.layout()
    # **設定の読み込みとログの構成より前に検査する。** `logs/` が通常ファイルの状態で
    # ファイルハンドラを開くと、素の `OSError` が 70 へ落ちる（17.4 の R-1）。
    verify_structure(layout)
    config = load_config(layout.config_path)
    setup_cli_logging(cli_ctx, log_path=layout.log_path, level=config.logging.level)
    logger = get_logger("cli")
    conn = open_project_db(layout, config)
    try:
        decisions = DecisionRepository(conn)
        yield ProjectSession(
            layout=layout,
            config=config,
            conn=conn,
            logger=logger,
            registry=build_default_registry(),
            tasks=TaskService(TaskRepository(conn)),
            decisions=decisions,
            audit=AuditRecorder(
                decisions=decisions,
                audit_path=layout.audit_path,
                logger=logger,
            ),
        )
    finally:
        conn.close()
