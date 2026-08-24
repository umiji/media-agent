"""`core/clock.py` の単体テスト（詳細設計 6.2 / 罠 D-T9）。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from media_agent.core.clock import from_iso, to_iso, utcnow


def test_utcnow_is_timezone_aware_utc() -> None:
    """`utcnow()` は必ず timezone-aware（UTC）を返す。"""
    now = utcnow()

    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_to_iso_uses_the_designed_format() -> None:
    """UTC・マイクロ秒まで・末尾 `Z`（詳細設計 6.2）。"""
    dt = datetime(2026, 8, 23, 10, 0, 0, 123456, tzinfo=UTC)

    assert to_iso(dt) == "2026-08-23T10:00:00.123456Z"


def test_to_iso_converts_other_offsets_to_utc() -> None:
    """別のタイムゾーンの値も UTC へ直してから書く。"""
    jst = datetime(2026, 8, 23, 19, 0, 0, 0, tzinfo=timezone(timedelta(hours=9)))

    assert to_iso(jst) == "2026-08-23T10:00:00.000000Z"


def test_to_iso_rejects_naive_datetime() -> None:
    """naive な値は受け取らない。**時差のずれを黙って書き込ませない**（罠 D-T9）。"""
    with pytest.raises(ValueError, match="naive"):
        to_iso(datetime(2026, 8, 23, 10, 0, 0))  # noqa: DTZ001 - 検証対象


def test_from_iso_round_trips() -> None:
    """`to_iso` → `from_iso` で元の値へ戻る。"""
    dt = datetime(2026, 8, 23, 10, 0, 0, 123456, tzinfo=UTC)

    assert from_iso(to_iso(dt)) == dt


def test_from_iso_treats_naive_text_as_utc() -> None:
    """タイムゾーンを持たない文字列は UTC とみなす（DB の値は常に UTC）。"""
    assert from_iso("2026-08-23T10:00:00.000000") == datetime(
        2026, 8, 23, 10, 0, 0, tzinfo=UTC
    )
