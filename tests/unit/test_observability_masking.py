"""`core/observability/masking.py` の単体テスト（詳細設計 11.4 / 品質基準 Q10）。"""

from __future__ import annotations

import pytest

from media_agent.core.observability.masking import (
    MASK,
    is_secret_key,
    mask_mapping,
    mask_text,
    mask_value,
)


@pytest.mark.parametrize(
    "key",
    [
        "token",
        "SECRET",
        "password",
        "passwd",
        "api_key",
        "api-key",
        "apiKey",
        "credential",
        "Authorization",
        "x_api_key",
    ],
)
def test_secret_looking_keys_are_detected(key: str) -> None:
    assert is_secret_key(key)


@pytest.mark.parametrize("key", ["message", "topic", "agent", "keyword"])
def test_ordinary_keys_are_not_detected(key: str) -> None:
    assert not is_secret_key(key)


def test_values_of_secret_keys_are_replaced() -> None:
    assert mask_value({"api_key": "s3cret", "message": "hi"}) == {
        "api_key": MASK,
        "message": "hi",
    }


def test_masking_is_recursive() -> None:
    """ネストした辞書・リストの中も対象（詳細設計 11.4）。"""
    value = {"outer": {"token": "t"}, "items": [{"password": "p"}, {"ok": 1}]}

    assert mask_value(value) == {
        "outer": {"token": MASK},
        "items": [{"password": MASK}, {"ok": 1}],
    }


def test_mask_mapping_keeps_none() -> None:
    """`None`（値が無い）と `{}`（空）を混同しない。"""
    assert mask_mapping(None) is None
    assert mask_mapping({}) == {}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("api_key=s3cret", f"api_key={MASK}"),
        ('{"api_key": "s3cret"}', f'{{"api_key": "{MASK}"}}'),
        ("token: abc123", f"token: {MASK}"),
        ("agent=echo task=1", "agent=echo task=1"),
    ],
)
def test_log_lines_are_masked(text: str, expected: str) -> None:
    """運用ログにも同じ規則を適用する（詳細設計 11.4）。"""
    assert mask_text(text) == expected
