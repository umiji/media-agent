"""Agent Interface（要件定義書5.1節 / 詳細設計 8.1）。

**`decision` と `reason` を戻り値に含めるのがこの設計の要点である。** 要件定義書5.5節が
監査記録に「何を判断したか」「なぜそう判断したか」を要求している以上、それを知っているのは
Agent 自身しかない。戻り値に無いと、Runner が推測で埋めるか、空欄になる。

**`AgentContext` に DB 接続・Repository・AuditRecorder を渡さない。** Agent は自分で
永続化しない（要件定義書2.4節「Decision と Action を分離」、品質基準 Q9）。記録は Runner の責務。
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from media_agent.core.config.models import Config

__all__ = [
    "AGENT_NAME_PATTERN",
    "Agent",
    "AgentContext",
    "AgentInput",
    "AgentOutput",
]

#: Agent 名の命名規則（詳細設計 8.1）。CLI の `--agent` へそのまま書ける形に限る。
AGENT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9-]{0,31}$")


class AgentInput(BaseModel):
    """Agent への入力（詳細設計 8.1）。`payload` は JSON 化できる値のみ。"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    payload: dict[str, Any] = Field(default_factory=dict)


class AgentOutput(BaseModel):
    """Agent からの出力（詳細設計 8.1）。

    `decision` / `reason` は**必須**である。監査記録の同名項目になる（詳細設計 11.3）。
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    payload: dict[str, Any] = Field(default_factory=dict)
    decision: str = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1)


@dataclass(frozen=True)
class AgentContext:
    """Agent の実行時に渡す文脈（詳細設計 8.1）。

    `ProjectLayout` ではなく `project_root` だけを渡す。`core/` が `.media-agent` 配下の
    構造を知らないままでいるため（品質基準 Q7）。Stage 0 の組み込み Agent は使わない。
    """

    project_root: Path
    config: Config
    task_id: str
    logger: logging.Logger


class Agent(ABC):
    """Agent の基底（詳細設計 8.1）。

    `Protocol` ではなく ABC にした理由: 登録時に `issubclass` と抽象メソッドで弾けるため。
    構造的部分型では `name` / `version` の欠落が実行時まで判明しない。
    """

    #: Registry で引く名前（`AGENT_NAME_PATTERN` に一致すること）。
    name: ClassVar[str]
    #: 実装の版数。1 以上。挙動が変わったら上げる（要件定義書20.5節・再現性）。
    version: ClassVar[int]
    #: `agent list` に出す1行の説明（詳細設計 16.1）。
    description: ClassVar[str]

    @abstractmethod
    def run(self, input: AgentInput, ctx: AgentContext) -> AgentOutput:
        """Agent の本体。**外部副作用を持たないこと**（品質基準 Q9）。"""
