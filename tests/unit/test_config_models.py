"""Config モデルの単体テスト（詳細設計 5.1〜5.3）。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from media_agent.core.config.models import (
    CONFIG_SCHEMA_VERSION,
    ActionMode,
    ActionName,
    Config,
    LogLevel,
    default_actions,
)


def _minimal() -> dict[str, object]:
    """検証を通る最小の設定（必須は `project.name` だけ）。"""
    return {"project": {"name": "sample"}}


def test_only_project_name_is_required() -> None:
    """`project.name` 以外は既定値で成立する（詳細設計 5.2.1）。"""
    config = Config.model_validate(_minimal())

    assert config.project.name == "sample"
    assert config.project.description == ""
    assert config.version == CONFIG_SCHEMA_VERSION
    assert config.media.primary_platform == "x"
    assert config.content.posts_per_day == 3
    assert config.automation.require_approval is False
    assert config.limits.max_actions_per_hour == 10
    assert config.limits.forbidden_topics == []
    assert config.logging.level is LogLevel.INFO


def test_actions_default_table() -> None:
    """`actions` 省略時の既定表（詳細設計 5.2.5）。"""
    actions = Config.model_validate(_minimal()).actions

    assert set(actions) == set(ActionName)
    assert actions[ActionName.POST].mode is ActionMode.AUTO
    assert actions[ActionName.POST].max_per_day == 3
    assert actions[ActionName.REPLY].mode is ActionMode.APPROVAL
    assert actions[ActionName.REPOST].mode is ActionMode.APPROVAL
    assert actions[ActionName.LIKE].mode is ActionMode.DISABLED
    assert actions[ActionName.REPLY].max_per_day is None


def test_partial_actions_are_merged_only_for_missing_entries() -> None:
    """書かれた Action は既定とマージしない。書かれていない Action だけ補う（5.3）。"""
    raw = _minimal() | {"actions": {"post": {"mode": "approval"}}}

    actions = Config.model_validate(raw).actions

    assert actions[ActionName.POST].mode is ActionMode.APPROVAL
    assert actions[ActionName.POST].max_per_day is None, "既定の 3 を引き継がないこと"
    assert actions[ActionName.LIKE].mode is ActionMode.DISABLED


def test_action_mode_is_required_when_the_action_is_written() -> None:
    """`post: {}` を黙って `auto` にしない（詳細設計 5.2.5）。"""
    with pytest.raises(ValidationError) as caught:
        Config.model_validate(_minimal() | {"actions": {"post": {}}})

    assert caught.value.errors()[0]["loc"] == ("actions", "post", "mode")


def test_unknown_keys_are_rejected() -> None:
    """`extra="forbid"`（罠 D-T10）。"""
    with pytest.raises(ValidationError) as caught:
        Config.model_validate(_minimal() | {"projet": {}})

    assert caught.value.errors()[0]["type"] == "extra_forbidden"


def test_unknown_action_name_is_rejected() -> None:
    """`actions` のキーは4種のみ（詳細設計 5.2.5）。"""
    with pytest.raises(ValidationError):
        Config.model_validate(_minimal() | {"actions": {"boost": {"mode": "auto"}}})


def test_project_name_is_stripped_and_bounded() -> None:
    """前後空白を除去して 1〜100 文字（詳細設計 5.2.1）。"""
    assert (
        Config.model_validate({"project": {"name": "  name  "}}).project.name == "name"
    )

    with pytest.raises(ValidationError):
        Config.model_validate({"project": {"name": "   "}})
    with pytest.raises(ValidationError):
        Config.model_validate({"project": {"name": "x" * 101}})


@pytest.mark.parametrize(
    "raw",
    [
        {"media": {"primary_platform": "bluesky"}},
        {"content": {"posts_per_day": -1}},
        {"content": {"posts_per_day": 101}},
        {"limits": {"max_actions_per_hour": -1}},
        {"limits": {"forbidden_topics": [""]}},
        {"logging": {"level": "INFO"}},
        {"actions": {"post": {"mode": "autoo"}}},
        {"actions": {"post": {"mode": "auto", "max_per_day": -1}}},
        {"version": 0},
    ],
    ids=[
        "platform",
        "posts_per_day-low",
        "posts_per_day-high",
        "max_actions_per_hour",
        "empty-forbidden-topic",
        "uppercase-log-level",
        "invalid-mode",
        "negative-max_per_day",
        "version-zero",
    ],
)
def test_value_domain_violations(raw: dict[str, object]) -> None:
    """値域・列挙の違反は検証エラーになる（詳細設計 5.2）。"""
    with pytest.raises(ValidationError):
        Config.model_validate(_minimal() | raw)


def test_config_is_frozen() -> None:
    """`Config` は不変（詳細設計 5.3）。設定を書き戻す経路を作らない。"""
    config = Config.model_validate(_minimal())

    with pytest.raises(ValidationError):
        config.version = 1


def test_default_actions_helper_matches_the_table() -> None:
    """既定表のヘルパは検証済みモデルを返す。"""
    assert default_actions()[ActionName.POST].mode is ActionMode.AUTO
