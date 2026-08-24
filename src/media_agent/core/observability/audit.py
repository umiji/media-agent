"""監査記録（詳細設計 11.1・11.3・11.4）。

**`AuditRecorder` が監査記録の唯一の書き込み口である**（用語集「AuditRecorder」）。
`decisions` テーブル（正本）と `audit.jsonl`（写し）へ、**この順で**書く。

運用ログとの違い（詳細設計 11.1）:

- **`logging.level` で抑制されない。常に全件記録する**
- 欠落を許容しない。DB への書き込みが失敗したら例外を送出し、記録できない実行を進めない
- トレースバックを出さない（1行の `error` のみ）
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from media_agent.core.clock import to_iso, utcnow
from media_agent.core.db.repositories import new_id
from media_agent.core.observability.masking import mask_mapping

if TYPE_CHECKING:  # pragma: no cover - 型注釈のためだけの参照
    from media_agent.core.db.repositories import DecisionRepository

__all__ = [
    "AUDIT_SCHEMA_VERSION",
    "AUDIT_KEYS",
    "AuditKind",
    "AuditRecord",
    "AuditRecorder",
]

#: JSONL の各行が持つメタ情報 `schema_version` の値。監査記録の形が変わったら上げる。
AUDIT_SCHEMA_VERSION = 1

#: 要件定義書5.5節の9項目（詳細設計 11.3 の対応表）。**JSONL は必ず全キーを持つ。**
AUDIT_KEYS: tuple[str, ...] = (
    "timestamp",
    "agent",
    "task",
    "input",
    "decision",
    "reason",
    "action",
    "result",
    "error",
)

AuditKind = Literal["agent_run", "policy_check"]


class PolicyRequestLike(Protocol):
    """`PolicyRequest`（詳細設計 10.2、実装は T-006）を構造的に受け取る。

    `core/observability` から `core/policy` を import しないのは、監査が Runtime・Policy より
    **先に存在する**ため（順序制約 O-4 / D-O5）。型は構造で受ける。
    """

    @property
    def action(self) -> str: ...
    @property
    def topic(self) -> str | None: ...
    @property
    def target_user(self) -> str | None: ...
    @property
    def requested_by(self) -> str: ...
    @property
    def task_id(self) -> str | None: ...
    @property
    def requested_at(self) -> datetime | None: ...


class _HasValue(Protocol):
    @property
    def value(self) -> str: ...


class PolicyDecisionLike(Protocol):
    """`PolicyDecision`（詳細設計 10.2、実装は T-006）を構造的に受け取る。"""

    @property
    def outcome(self) -> _HasValue: ...
    @property
    def reason_code(self) -> _HasValue: ...
    @property
    def message(self) -> str: ...
    @property
    def detail(self) -> dict[str, Any]: ...


class AuditRecord(BaseModel):
    """監査記録の1件（詳細設計 11.3）。

    要件定義書5.5節の9項目に、種別（`kind`）と識別子（`decision_id`）を加えたもの。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    timestamp: datetime
    agent: str
    task: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    decision: str
    reason: str
    action: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    kind: AuditKind
    decision_id: str = Field(default_factory=new_id)

    def to_jsonl_payload(self) -> dict[str, Any]:
        """JSONL の1行にする辞書（詳細設計 11.3）。

        **9キーを必ず全て持つ**（値が無い場合は `null`）。キーを省略すると、
        「キーが無い」と「値が null」を読み手が区別できなくなる。
        """
        return {
            "timestamp": to_iso(self.timestamp),
            "agent": self.agent,
            "task": self.task,
            "input": self.input,
            "decision": self.decision,
            "reason": self.reason,
            "action": self.action,
            "result": self.result,
            "error": self.error,
            "kind": self.kind,
            "decision_id": self.decision_id,
            "schema_version": AUDIT_SCHEMA_VERSION,
        }


class AuditRecorder:
    """監査記録の唯一の書き込み口（詳細設計 11.3）。

    書き込み順序と失敗時の扱い:

    1. `decisions` テーブルへ INSERT し、**コミットする**（正本）
    2. `audit.jsonl` へ1行 append する
    3. 2 が失敗したら運用ログへ `ERROR` を出すが**例外にしない**（正本は残っている）
    4. 1 が失敗したら例外を送出する（記録できない実行を進めない）
    """

    def __init__(
        self,
        *,
        decisions: DecisionRepository,
        audit_path: Path,
        logger: logging.Logger,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self._decisions = decisions
        self._audit_path = audit_path
        self._logger = logger
        self._clock = clock

    def record(self, record: AuditRecord) -> AuditRecord:
        """1件記録する。**監査記録が通る道はこのメソッドだけである。**

        秘密値のマスクと `error` / `reason` の1行化は、ここで一度だけ行う。
        """
        prepared = record.model_copy(
            update={
                "input": mask_mapping(record.input) or {},
                "result": mask_mapping(record.result),
                "reason": _one_line(record.reason),
                "error": None if record.error is None else _one_line(record.error),
            }
        )
        self._decisions.add(prepared)
        self._append_jsonl(prepared)
        return prepared

    def record_agent_run(
        self,
        *,
        agent: str,
        task_id: str,
        input: dict[str, Any],
        decision: str,
        reason: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> AuditRecord:
        """Agent の実行を記録する（詳細設計 11.3 の `kind="agent_run"`）。"""
        return self.record(
            AuditRecord(
                timestamp=self._clock(),
                agent=agent,
                task=task_id,
                input=input,
                decision=decision,
                reason=reason,
                action=None,
                result=result,
                error=error,
                kind="agent_run",
            )
        )

    def record_policy_check(
        self, *, request: PolicyRequestLike, decision: PolicyDecisionLike
    ) -> AuditRecord:
        """Policy の判定を記録する（詳細設計 11.3 の `kind="policy_check"`）。

        `reason` は **`"<reason_code>: <message>"` の形**である（先頭が reason_code であること）。
        """
        return self.record(
            AuditRecord(
                timestamp=request.requested_at or self._clock(),
                agent=request.requested_by,
                task=request.task_id,
                input={
                    "action": request.action,
                    "topic": request.topic,
                    "target_user": request.target_user,
                },
                decision=decision.outcome.value,
                reason=f"{decision.reason_code.value}: {decision.message}",
                action=request.action,
                result=dict(decision.detail),
                error=None,
                kind="policy_check",
            )
        )

    def _append_jsonl(self, record: AuditRecord) -> None:
        """写しを1行追記する（詳細設計 11.3 の手順2・3）。

        `ensure_ascii=False` / `sort_keys=True`（罠 D-T12）。回転させない（追記専用）。
        """
        line = json.dumps(record.to_jsonl_payload(), ensure_ascii=False, sort_keys=True)
        try:
            self._audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self._audit_path.open("a", encoding="utf-8") as stream:
                stream.write(line + "\n")
        except OSError as exc:
            # 正本は DB に残っている。写しが書けないことで実行を止めない。
            self._logger.error(
                "audit_jsonl_write_failed path=%s decision=%s error=%s",
                self._audit_path,
                record.decision_id,
                exc,
            )


def _one_line(text: str) -> str:
    """改行を除いて1行にする（監査記録にトレースバックを出さない。詳細設計 11.1）。"""
    return " ".join(text.splitlines()).strip()
