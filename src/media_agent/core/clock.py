"""時刻の取得と、DB へ書く文字列表現（詳細設計 6.2 / 罠 D-T9）。

**時刻の取得は必ずこのモジュールを通す。** `datetime.now()`（naive）を直接呼ぶと、
DB へ書いた 6.2 形式の文字列と比較したときに時差があっても気付けない。

形式: UTC の RFC3339、マイクロ秒まで、末尾 `Z`。例 `2026-08-23T10:00:00.123456Z`
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["from_iso", "to_iso", "utcnow"]

#: `to_iso` が使う書式（末尾の `Z` は固定文字列として付ける）。
_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"


def utcnow() -> datetime:
    """現在時刻を timezone-aware（UTC）で返す。"""
    return datetime.now(UTC)


def to_iso(dt: datetime) -> str:
    """`datetime` を 6.2 の文字列へ変換する。

    Raises:
        ValueError: naive な `datetime` を渡した（罠 D-T9）。時差の情報が無い値を
            UTC とみなして書き込むと、後から誤りを検出できない。
    """
    if dt.tzinfo is None:
        raise ValueError(
            "naive な datetime は扱えません。media_agent.core.clock.utcnow() を使ってください"
        )
    return dt.astimezone(UTC).strftime(_FORMAT) + "Z"


def from_iso(s: str) -> datetime:
    """6.2 の文字列を timezone-aware（UTC）な `datetime` へ戻す。

    タイムゾーンを持たない文字列は UTC とみなす（DB へ書かれる値は常に UTC のため）。
    """
    parsed = datetime.fromisoformat(s)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
