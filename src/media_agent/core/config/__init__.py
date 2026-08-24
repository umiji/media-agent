"""Config のモデルと読み込み・検証（詳細設計5章）。

主な公開物を再エクスポートする（申し送り K-1）。
"""

from __future__ import annotations

from media_agent.core.config.loader import CONFIG_SCHEMA_VERSION, load_config
from media_agent.core.config.models import (
    ActionMode,
    ActionName,
    ActionPolicyConfig,
    AutomationConfig,
    Config,
    ContentConfig,
    LimitsConfig,
    LoggingConfig,
    LogLevel,
    MediaConfig,
    ProjectConfig,
)

__all__ = [
    "CONFIG_SCHEMA_VERSION",
    "ActionMode",
    "ActionName",
    "ActionPolicyConfig",
    "AutomationConfig",
    "Config",
    "ContentConfig",
    "LimitsConfig",
    "LogLevel",
    "LoggingConfig",
    "MediaConfig",
    "ProjectConfig",
    "load_config",
]
