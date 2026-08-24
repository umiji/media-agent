"""秘密値のマスク（詳細設計 11.4 / 品質基準 Q10）。

**Stage 0 に秘密値を扱う機能は無い。先に入れておく理由は、Stage 3 で認証情報が入った
瞬間に監査記録や運用ログへ漏れるのを防ぐためである**（拡張点 E-8）。

- 監査記録: `input` / `result` の**キー名**が秘密値らしいときに値を `***` にする
- 運用ログ: 1行のテキストなので、`key=value` / `"key": "value"` の形を検出して値を伏せる
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["MASK", "SECRET_KEY_PATTERN", "mask_mapping", "mask_text", "mask_value"]

#: 伏せ字。値そのものを残さないため、長さも情報として出さない。
MASK = "***"

#: 秘密値とみなすキー名（詳細設計 11.4）。
SECRET_KEY_PATTERN = (
    r"(?i)(token|secret|password|passwd|api[_-]?key|credential|authorization)"
)

_SECRET_KEY_RE = re.compile(SECRET_KEY_PATTERN)

#: 運用ログの1行から `key=value` / `"key": "value"` を見つける。
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(?P<key>token|secret|password|passwd|api[_-]?key|credential|authorization)"
    r"(?P<sep>[\"']?\s*[:=]\s*)"
    r"(?P<quote>[\"']?)"
    r"(?P<value>[^\s,;\)\]\}\"']+)"
    r"(?P=quote)"
)


def is_secret_key(key: str) -> bool:
    """キー名が秘密値らしいか。"""
    return _SECRET_KEY_RE.search(key) is not None


def mask_value(value: Any) -> Any:
    """辞書・リストの中まで再帰的にマスクする（詳細設計 11.4）。"""
    if isinstance(value, dict):
        return {
            key: (
                MASK
                if isinstance(key, str) and is_secret_key(key)
                else mask_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [mask_value(item) for item in value]
    return value


def mask_mapping(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """`None` を保ったまま辞書をマスクする（監査記録の `input` / `result` 用）。"""
    if value is None:
        return None
    masked = mask_value(value)
    return dict(masked) if isinstance(masked, dict) else {}


def mask_text(text: str) -> str:
    """運用ログの1行から秘密値らしい代入の右辺を伏せる。"""
    return _SECRET_ASSIGNMENT_RE.sub(
        lambda m: (
            f"{m.group('key')}{m.group('sep')}{m.group('quote')}{MASK}{m.group('quote')}"
        ),
        text,
    )
