"""`load_config()` の単体テスト（詳細設計 5.4 の C-1〜C-7）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from media_agent.core.config.loader import load_config
from media_agent.errors import (
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
    ConfigVersionError,
)

MINIMAL = "version: 1\nproject:\n  name: sample\n"


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_loads_a_minimal_config(tmp_path: Path) -> None:
    config = load_config(_write(tmp_path, MINIMAL))

    assert config.project.name == "sample"


def test_c1_missing_file(tmp_path: Path) -> None:
    """C-1: ファイルが無い。安定文字列は `config.yaml` と絶対パス。"""
    path = tmp_path / "config.yaml"

    with pytest.raises(ConfigNotFoundError) as caught:
        load_config(path)

    assert "config.yaml" in caught.value.message
    assert str(path) in caught.value.message


def test_c2_broken_yaml_reports_line_number(tmp_path: Path) -> None:
    """C-2: YAML として解析できない。`構文` と行番号を出す。"""
    path = _write(tmp_path, 'version: 1\nproject:\n  name: "unclosed\n   - [\n')

    with pytest.raises(ConfigParseError) as caught:
        load_config(path)

    assert "config.yaml" in caught.value.message
    assert "構文" in caught.value.message
    assert any("行" in detail for detail in caught.value.details)


@pytest.mark.parametrize(
    "text", ["- a\n- b\n", "42\n", "", "\n"], ids=["list", "scalar", "empty", "blank"]
)
def test_c3_top_level_must_be_a_mapping(tmp_path: Path, text: str) -> None:
    """C-3: トップレベルが mapping でない。"""
    with pytest.raises(ConfigParseError) as caught:
        load_config(_write(tmp_path, text))

    assert "構文" in caught.value.message


def test_c4_missing_required_key_reports_the_key_path(tmp_path: Path) -> None:
    """C-4: 必須項目の欠落。キーパスを必ず含める。"""
    with pytest.raises(ConfigValidationError) as caught:
        load_config(_write(tmp_path, "version: 1\nproject:\n  description: x\n"))

    assert any(detail.startswith("project.name:") for detail in caught.value.details)


def test_c5_enum_violation_reports_the_key_path(tmp_path: Path) -> None:
    """C-5: 列挙違反。"""
    text = MINIMAL + "actions:\n  post:\n    mode: autoo\n"

    with pytest.raises(ConfigValidationError) as caught:
        load_config(_write(tmp_path, text))

    assert any(d.startswith("actions.post.mode:") for d in caught.value.details)


def test_c6_unknown_key_reports_the_key_path(tmp_path: Path) -> None:
    """C-6: 未知のキー。"""
    with pytest.raises(ConfigValidationError) as caught:
        load_config(_write(tmp_path, MINIMAL + "projet:\n  name: typo\n"))

    assert any(d.startswith("projet:") for d in caught.value.details)


def test_c6_unknown_action_key_reports_the_key_path(tmp_path: Path) -> None:
    """未知の Action 名も、キーパスが読める形で報告する。"""
    text = MINIMAL + "actions:\n  boost:\n    mode: auto\n"

    with pytest.raises(ConfigValidationError) as caught:
        load_config(_write(tmp_path, text))

    assert any("actions.boost" in detail for detail in caught.value.details)


def test_c7_unsupported_version(tmp_path: Path) -> None:
    """C-7: `version >= 2`。`version` / 実際の版数 / `1` を含める。"""
    with pytest.raises(ConfigVersionError) as caught:
        load_config(_write(tmp_path, "version: 2\nproject:\n  name: sample\n"))

    assert "version" in caught.value.message
    assert "2" in caught.value.message
    assert "1" in caught.value.message


def test_version_zero_is_a_validation_error(tmp_path: Path) -> None:
    """`version <= 0` は版数エラーではなく範囲エラー（詳細設計 5.2）。"""
    with pytest.raises(ConfigValidationError):
        load_config(_write(tmp_path, "version: 0\nproject:\n  name: sample\n"))


def test_all_violations_are_reported_together(tmp_path: Path) -> None:
    """1件目で打ち切らない（詳細設計 5.4）。"""
    text = (
        "version: 1\nproject:\n  description: ''\nactions:\n  post:\n    mode: autoo\n"
    )

    with pytest.raises(ConfigValidationError) as caught:
        load_config(_write(tmp_path, text))

    assert len(caught.value.details) == 2
    assert "(2 件)" in caught.value.message


def test_hint_is_attached_to_validation_errors(tmp_path: Path) -> None:
    """まとめて確認する手段（`doctor`）を Hint で示す（詳細設計 5.4）。"""
    with pytest.raises(ConfigValidationError) as caught:
        load_config(_write(tmp_path, "version: 1\nproject: {}\n"))

    assert caught.value.hint is not None
    assert "doctor" in caught.value.hint


def test_yaml_load_is_safe(tmp_path: Path) -> None:
    """`yaml.safe_load` のみを使う（罠 T-6）。任意オブジェクトを構築させない。"""
    text = "version: 1\nproject:\n  name: !!python/object/apply:os.system ['echo x']\n"

    with pytest.raises(ConfigParseError):
        load_config(_write(tmp_path, text))


def test_enum_candidates_are_listed_with_slashes(tmp_path: Path) -> None:
    """列挙の候補は `auto / approval / disabled` の形で示す（詳細設計 5.4 の例）。"""
    text = MINIMAL + "actions:\n  post:\n    mode: autoo\n"

    with pytest.raises(ConfigValidationError) as caught:
        load_config(_write(tmp_path, text))

    assert "auto / approval / disabled" in caught.value.details[0]
