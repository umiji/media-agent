"""`config.yaml` の読み込みと検証（詳細設計 5.1・5.4）。

- パーサは `yaml.safe_load` のみ（罠 T-6。任意オブジェクト構築を許さない）
- 検証エラーは**全件まとめて**報告する。1件目で打ち切らない（詳細設計 5.4）
- 例外はすべて `ConfigError` の派生（終了コード 4）。**終了コードへの変換は CLI 層が行う**
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from media_agent.core.config.models import CONFIG_SCHEMA_VERSION, Config
from media_agent.errors import (
    ConfigNotFoundError,
    ConfigParseError,
    ConfigValidationError,
    ConfigVersionError,
)

__all__ = ["CONFIG_SCHEMA_VERSION", "load_config"]

#: `Hint:` 行（詳細設計 5.4 のエラー出力例）。
_HINT = "media-agent doctor を実行すると、設定の問題をまとめて確認できます"

#: Pydantic の `loc` に混ざる合成要素。キーパスの表示からは落とす。
_SYNTHETIC_LOC_PARTS = frozenset({"[key]"})


def load_config(path: Path) -> Config:
    """`config.yaml` を読み、検証済みの `Config` を返す（詳細設計 5.3）。

    Raises:
        ConfigNotFoundError: ファイルが無い（C-1）
        ConfigParseError: YAML として読めない / mapping でない（C-2 / C-3）
        ConfigVersionError: 対応していない版数（C-7）
        ConfigValidationError: スキーマ違反（C-4 / C-5 / C-6）
    """
    raw = _read_mapping(path)
    _check_version(raw, path)
    try:
        return Config.model_validate(raw)
    except ValidationError as exc:
        raise _validation_error(exc, path) from exc


def _read_mapping(path: Path) -> Mapping[str, Any]:
    """ファイルを読み、トップレベルが mapping であることまでを確認する。"""
    if not path.is_file():
        raise ConfigNotFoundError(
            f"config.yaml が見つかりません: {path}",
            hint="media-agent init を実行すると生成されます",
        )
    text = path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigParseError(
            f"config.yaml の構文が正しくありません: {path}",
            details=_yaml_error_details(exc),
            hint=_HINT,
        ) from exc
    if not isinstance(data, Mapping):
        raise ConfigParseError(
            f"config.yaml の構文が正しくありません（設定は mapping で書きます）: {path}",
            details=[f"読み取れた型: {type(data).__name__}"],
            hint=_HINT,
        )
    return data


def _yaml_error_details(exc: yaml.YAMLError) -> list[str]:
    """PyYAML の例外から、行番号を含む1行の説明を作る（詳細設計 5.4 の C-2）。"""
    mark = getattr(exc, "problem_mark", None)
    problem = getattr(exc, "problem", None) or "YAML として解析できません"
    if mark is not None:
        return [f"{mark.line + 1} 行 {mark.column + 1} 列: {problem}"]
    return [str(problem)]


def _check_version(raw: Mapping[str, Any], path: Path) -> None:
    """対応していない設定スキーマ版数を先に弾く（詳細設計 5.4 の C-7）。

    `version <= 0` は範囲エラー（`ConfigValidationError`）として `Config` 側で検出する。
    """
    version = raw.get("version", CONFIG_SCHEMA_VERSION)
    if isinstance(version, bool) or not isinstance(version, int):
        return
    if version > CONFIG_SCHEMA_VERSION:
        raise ConfigVersionError(
            f"config.yaml の version {version} はサポートされていません"
            f"（対応している版数: {CONFIG_SCHEMA_VERSION}）: {path}",
            details=[
                f"version: {version} は、このバージョンの Media Agent では読めません"
            ],
            hint="Media Agent を更新するか、version を 1 に戻してください",
        )


def _validation_error(exc: ValidationError, path: Path) -> ConfigValidationError:
    """Pydantic の違反を、キーパス付きの `ConfigValidationError` へ変換する。

    **キーパスは必ずメッセージに含める**（詳細設計 5.4。テストの判定対象）。
    """
    details = [
        f"{_key_path(error['loc'])}: {_describe(error)}" for error in exc.errors()
    ]
    return ConfigValidationError(
        f"config.yaml の検証に失敗しました ({len(details)} 件): {path}",
        details=details,
        hint=_HINT,
    )


def _key_path(loc: tuple[Any, ...]) -> str:
    """Pydantic の `loc` をドット区切りのキーパスにする。"""
    parts = [str(part) for part in loc if str(part) not in _SYNTHETIC_LOC_PARTS]
    return ".".join(parts) if parts else "(トップレベル)"


def _describe(error: Any) -> str:
    """違反の種類を日本語1行にする。判定対象はキーパスであり、この文面ではない。"""
    error_type = str(error.get("type", ""))
    if error_type == "missing":
        return "必須項目がありません"
    if error_type == "extra_forbidden":
        return "設定できないキーです（打ち間違いの可能性があります）"
    if error_type == "enum":
        return (
            f"{error.get('input')!r} は使用できません（{_expected(error)} のいずれか）"
        )
    return str(error.get("msg", "値が正しくありません"))


def _expected(error: Any) -> str:
    """列挙の候補を `auto / approval / disabled` の形に整える（詳細設計 5.4 の例）。"""
    raw = str(error.get("ctx", {}).get("expected", "")).replace("'", "")
    candidates = [part.strip() for part in raw.replace(" or ", ", ").split(",")]
    return " / ".join(part for part in candidates if part)
