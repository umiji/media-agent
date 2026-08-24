"""Agent の実行（詳細設計 8.3）。

**Runner だけが「Agent を実行し、Task を進め、監査へ記録する」**。Agent 自身は
永続化しない（要件2.4 / 品質基準 Q9）。

Agent が失敗しても**例外を外へ漏らさない**（T-006 完了条件2）。呼び出し側が毎回
try/except を書く設計にすると、書き忘れた経路で Task が `running` のまま残る（8.3 の却下案）。
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from media_agent.core.clock import utcnow
from media_agent.core.runtime.agent import AgentContext, AgentInput, AgentOutput
from media_agent.core.runtime.registry import AgentRegistry
from media_agent.core.task import Task, TaskService, TaskStatus

if TYPE_CHECKING:  # pragma: no cover - 型注釈のためだけの参照
    from media_agent.core.config.models import Config
    from media_agent.core.observability.audit import AuditRecorder

__all__ = ["DEFAULT_TASK_TYPE", "AgentRunner", "TaskRunResult"]

#: Stage 0 の Task 種別（詳細設計 9.1）。
DEFAULT_TASK_TYPE = "agent_run"

#: 失敗時に `decision` へ入れる値（詳細設計 11.3 の種別ごとの値の入れ方）。
ERROR_DECISION = "error"


@dataclass(frozen=True)
class TaskRunResult:
    """1回の実行の結果（詳細設計 8.3）。"""

    task: Task
    output: AgentOutput | None
    error: str | None


class AgentRunner:
    """Agent Runtime の実行部（詳細設計 8.3）。

    `TaskService` と `AuditRecorder` は**引数で受け取る。自分で作らない**（D-O6）。
    偽の記録先を差し込めるようにしておくことが、単体テストの前提になっている。
    """

    def __init__(
        self,
        *,
        registry: AgentRegistry,
        tasks: TaskService,
        audit: AuditRecorder,
        logger: logging.Logger,
        config: Config,
        project_root: Path,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._registry = registry
        self._tasks = tasks
        self._audit = audit
        self._logger = logger
        self._config = config
        self._project_root = project_root
        self._clock = clock

    def run(
        self,
        agent_name: str,
        payload: dict[str, Any] | None = None,
        *,
        task_type: str = DEFAULT_TASK_TYPE,
    ) -> TaskRunResult:
        """Agent を1回実行する（詳細設計 8.3 の手順1〜8）。

        **この順序が S-F / S-H の期待値である。**

        1. Registry から引く（未登録なら例外。**Task は作らない**）
        2. Task を作る（`pending`）
        3. `running` へ遷移する
        4. Agent を呼ぶ
        5. 結果に応じて `completed` / `failed` へ遷移し、**そのあと**監査へ記録する

        Raises:
            AgentNotFoundError: 未登録の Agent 名（手順1）。
        """
        agent = self._registry.get(agent_name)
        input_payload = dict(payload or {})

        task = self._tasks.create(agent=agent_name, type=task_type, input=input_payload)
        task = self._tasks.transition(task.task_id, TaskStatus.running)
        self._logger.info("agent=%s task=%s started", agent_name, task.task_id)
        started_at = self._clock()

        ctx = AgentContext(
            project_root=self._project_root,
            config=self._config,
            task_id=task.task_id,
            logger=self._logger,
        )
        try:
            output = agent.run(AgentInput(payload=input_payload), ctx)
        except Exception as exc:
            # `BaseException`（KeyboardInterrupt / SystemExit）は捕捉しない。
            # 利用者の中断を握り潰さないため（詳細設計 8.3）。
            return self._finish_failed(task, agent_name, input_payload, exc, started_at)
        return self._finish_completed(
            task, agent_name, input_payload, output, started_at
        )

    def _finish_completed(
        self,
        task: Task,
        agent_name: str,
        input_payload: dict[str, Any],
        output: AgentOutput,
        started_at: datetime,
    ) -> TaskRunResult:
        """正常終了（詳細設計 8.3 の手順6）。"""
        completed = self._tasks.transition(
            task.task_id, TaskStatus.completed, output=output.payload
        )
        self._audit.record_agent_run(
            agent=agent_name,
            task_id=task.task_id,
            input=input_payload,
            decision=output.decision,
            reason=output.reason,
            result=output.payload,
            error=None,
        )
        self._logger.info(
            "agent=%s task=%s completed elapsed=%.3fs",
            agent_name,
            task.task_id,
            self._elapsed(started_at),
        )
        return TaskRunResult(task=completed, output=output, error=None)

    def _finish_failed(
        self,
        task: Task,
        agent_name: str,
        input_payload: dict[str, Any],
        exc: Exception,
        started_at: datetime,
    ) -> TaskRunResult:
        """異常終了（詳細設計 8.3 の手順7）。**例外を再送出しない。**"""
        message = format_error(exc)
        failed = self._tasks.transition(task.task_id, TaskStatus.failed, error=message)
        self._audit.record_agent_run(
            agent=agent_name,
            task_id=task.task_id,
            input=input_payload,
            decision=ERROR_DECISION,
            reason=message,
            result=None,
            error=message,
        )
        # トレースバックは**運用ログにだけ**出す。監査記録は1行の `error` のみ（11.1）。
        self._logger.error(
            "agent=%s task=%s failed elapsed=%.3fs error=%s",
            agent_name,
            task.task_id,
            self._elapsed(started_at),
            message,
            exc_info=exc,
        )
        return TaskRunResult(task=failed, output=None, error=message)

    def _elapsed(self, started_at: datetime) -> float:
        return (self._clock() - started_at).total_seconds()


def format_error(exc: BaseException) -> str:
    """例外を `"<例外クラス名>: <メッセージ>"` の**1行**にする（詳細設計 8.3）。

    Task の `error` 列と監査記録の `error` は同じ1行である。トレースバックを含めない。
    """
    text = " ".join(str(exc).splitlines()).strip()
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__
