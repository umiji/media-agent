"""Config のモデル定義（詳細設計 5.1〜5.3）。

- **全モデルで `extra="forbid"`**（罠 D-T10。打ち間違いを黙って無視しない）
- `Config` は不変（`frozen=True`）。Stage 0 に設定を書き戻す機能は無い
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: この実装が対応する設定スキーマ版数（詳細設計 5.2）。
CONFIG_SCHEMA_VERSION = 1


class ActionMode(StrEnum):
    """Action の実行方式（詳細設計 5.2.5）。"""

    AUTO = "auto"
    APPROVAL = "approval"
    DISABLED = "disabled"


class ActionName(StrEnum):
    """Stage 0 が扱う Action（詳細設計 5.2.5）。"""

    POST = "post"
    REPLY = "reply"
    REPOST = "repost"
    LIKE = "like"


class LogLevel(StrEnum):
    """運用ログの出力レベル（詳細設計 5.2.7）。監査記録には影響しない。"""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class _StrictModel(BaseModel):
    """未知のキーを拒否する不変モデル（詳細設計 5.1）。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProjectConfig(_StrictModel):
    """`project`（詳細設計 5.2.1）。**`name` が唯一の必須項目である。**"""

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)

    @model_validator(mode="before")
    @classmethod
    def _strip_name(cls, data: Any) -> Any:
        """`name` の前後空白を除去してから長さを検査する（詳細設計 5.2.1）。"""
        if isinstance(data, dict) and isinstance(data.get("name"), str):
            data = {**data, "name": data["name"].strip()}
        return data


class MediaConfig(_StrictModel):
    """`media`（詳細設計 5.2.2）。"""

    primary_platform: str = Field(default="x", pattern="^x$")


class ContentConfig(_StrictModel):
    """`content`（詳細設計 5.2.3）。目標値であり、Policy の上限ではない。"""

    posts_per_day: int = Field(default=3, ge=0, le=100)


class AutomationConfig(_StrictModel):
    """`automation`（詳細設計 5.2.4）。"""

    require_approval: bool = False


class ActionPolicyConfig(_StrictModel):
    """`actions.<action>`（詳細設計 5.2.5）。

    `mode` は**そのアクションのキーを書いた場合は必須**。省略時に安全でない既定
    （`auto`）へ倒れないようにするため。
    """

    mode: ActionMode
    max_per_day: int | None = Field(default=None, ge=0)
    max_per_hour: int | None = Field(default=None, ge=0)


class LimitsConfig(_StrictModel):
    """`limits`（詳細設計 5.2.6）。"""

    max_actions_per_hour: int | None = Field(default=10, ge=0)
    forbidden_topics: list[str] = Field(default_factory=list)
    forbidden_users: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_entries(self) -> LimitsConfig:
        """各要素は 1〜100 文字（詳細設計 5.2.6）。"""
        for field_name in ("forbidden_topics", "forbidden_users"):
            for entry in getattr(self, field_name):
                if not 1 <= len(entry.strip()) <= 100:
                    raise ValueError(
                        f"{field_name} の要素は 1〜100 文字にしてください: {entry!r}"
                    )
        return self


class LoggingConfig(_StrictModel):
    """`logging`（詳細設計 5.2.7）。"""

    level: LogLevel = LogLevel.INFO


#: `actions` が省略された Action に適用する既定（詳細設計 5.2.5 の既定表）。
DEFAULT_ACTIONS: dict[str, dict[str, Any]] = {
    ActionName.POST.value: {"mode": ActionMode.AUTO.value, "max_per_day": 3},
    ActionName.REPLY.value: {"mode": ActionMode.APPROVAL.value},
    ActionName.REPOST.value: {"mode": ActionMode.APPROVAL.value},
    ActionName.LIKE.value: {"mode": ActionMode.DISABLED.value},
}


def default_actions() -> dict[ActionName, ActionPolicyConfig]:
    """既定表を検証済みモデルにして返す。"""
    return {
        ActionName(name): ActionPolicyConfig.model_validate(values)
        for name, values in DEFAULT_ACTIONS.items()
    }


class Config(_StrictModel):
    """`config.yaml` 全体（詳細設計 5.3）。"""

    version: int = Field(default=CONFIG_SCHEMA_VERSION, ge=1, le=CONFIG_SCHEMA_VERSION)
    project: ProjectConfig
    media: MediaConfig = MediaConfig()
    content: ContentConfig = ContentConfig()
    automation: AutomationConfig = AutomationConfig()
    actions: dict[ActionName, ActionPolicyConfig] = Field(
        default_factory=default_actions
    )
    limits: LimitsConfig = LimitsConfig()
    logging: LoggingConfig = LoggingConfig()

    @model_validator(mode="before")
    @classmethod
    def _fill_missing_actions(cls, data: Any) -> Any:
        """書かれていない Action **だけ**を既定表で補う（詳細設計 5.3）。

        書かれている Action は既定とマージしない（`mode` が必須なので欠落しない）。
        """
        if not isinstance(data, dict):
            return data
        actions = data.get("actions", None)
        if actions is None:
            return {**data, "actions": {k: dict(v) for k, v in DEFAULT_ACTIONS.items()}}
        if not isinstance(actions, dict):
            return data
        merged = {k: dict(v) for k, v in DEFAULT_ACTIONS.items() if k not in actions}
        merged.update(actions)
        return {**data, "actions": merged}
