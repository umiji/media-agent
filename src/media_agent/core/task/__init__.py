"""Task Model（要件定義書5.2節 / 詳細設計9章）。

**Task の状態を変えてよい経路は `TaskService.transition` だけである**（罠 D-T13）。
`TaskRepository.update_status` は遷移の可否を判定しない。遷移表（9.2）を迂回させないため、
Repository の呼び出しは `TaskService` の内側に閉じている。

主な公開物（申し送り K-1 により、ここで再エクスポートする）:

- `TaskStatus` — 5状態
- `Task` — 1件の Task（不変）
- `ALLOWED_TRANSITIONS` — 9.2 の表そのもの。**判定はこの1箇所だけで行う**
- `TaskService` — 生成・遷移・取得・一覧・集計
"""

from __future__ import annotations

from media_agent.core.task.models import (
    ALLOWED_TRANSITIONS,
    TERMINAL_STATUSES,
    Task,
    TaskStatus,
)
from media_agent.core.task.service import TaskService

__all__ = [
    "ALLOWED_TRANSITIONS",
    "TERMINAL_STATUSES",
    "Task",
    "TaskService",
    "TaskStatus",
]
