"""Agent Interface（要件定義書5.1節 / 詳細設計 8.1）。

**`decision` と `reason` を戻り値に含めるのが本設計の要点である。** 要件定義書5.5節が
監査記録に `decision` / `reason` を要求している以上、それを知っているのは Agent 自身
しかない。戻り値に無いと、Runner が推測で埋めるか、空欄になる。

**Agent は自分で永続化しない**（要件2.4「Decision と Action を分離」/ 品質基準 Q9）。
`AgentContext` に DB 接続・Repository・`AuditRecorder` を渡さないのはそのためである。
記録するのは `AgentRunner` の責務。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

if TYPE_CHECKING:  # pragma: no cover - 型注釈のためだけの参照
    from media_agent.core.config.models import Config

__all__ = [
    "AGENT_NAME_PATTERN",
    "Agent",
    "AgentContext",
    "AgentInput",
    "AgentOutput",
]

#: Agent 名の命名規則（詳細設計 8.1）。Registry が登録時に検査する。
AGENT_NAME_PATTERN = r"^[a-z][a-z0-9-]{0,31}$"

#: `AgentOutput.decision` の最大長（詳細設計 8.1「1行、120文字以内」）。
DECISION_MAX_LENGTH = 120


class AgentInput(BaseModel):
    """Agent への入力（詳細設計 8.1）。**JSON 化できる値のみ**を入れる。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    payload: dict[str, Any] = Field(default_factory=dict)


class AgentOutput(BaseModel):
    """Agent の出力（詳細設計 8.1）。

    `decision` / `reason` は**必須**である。監査記録の必須項目（要件5.5節）を
    Runner が推測で埋めないようにするため。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    payload: dict[str, Any] = Field(default_factory=dict)
    decision: str = Field(min_length=1, max_length=DECISION_MAX_LENGTH)
    reason: str = Field(min_length=1)

    @field_validator("decision")
    @classmethod
    def _single_line(cls, value: str) -> str:
        """`decision` は1行（詳細設計 8.1）。監査記録の一覧性を保つ。"""
        if "\n" in value or "\r" in value:
            raise ValueError("decision は1行にしてください")
        return value


@dataclass(frozen=True)
class AgentContext:
    """Agent の実行文脈（詳細設計 8.1）。

    `ProjectLayout` ではなく `project_root` だけを渡す（品質基準 Q7）。Stage 0 の
    組み込み Agent はこれを使わない。Stage 1 以降で `memory/` 等を読むための足場である。
    """

    project_root: Path
    config: Config
    task_id: str
    logger: logging.Logger


class Agent(ABC):
    """Agent の基底（詳細設計 8.1）。

    却下案: `typing.Protocol` による構造的部分型 → 登録時に「Agent として妥当か」を
    確認できず、`name` / `version` の欠落が実行時まで判明しない。ABC なら
    `isinstance` と抽象メソッドで登録時に弾ける（8.2）。
    """

    #: Agent 名。`AGENT_NAME_PATTERN` に従う。Registry のキーになる
    name: ClassVar[str]
    #: 実装の版数。1 以上。**実装が変わったら上げる**（要件20.5 の再現性）
    version: ClassVar[int]
    #: `agent list` に出す1行の説明
    description: ClassVar[str]

    @abstractmethod
    def run(self, input: AgentInput, ctx: AgentContext) -> AgentOutput:
        """Agent の本体。**外部副作用を持たない**（品質基準 Q9）。"""
