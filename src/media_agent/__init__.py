"""Media Agent — メディア運用の汎用エージェント基盤。

`__version__` がパッケージ版数の**単一の真実**である（方式設計12章）。
`pyproject.toml` は hatchling の dynamic version でこの値を読む。
"""

from __future__ import annotations

__all__ = ["__version__"]

#: セマンティックバージョニング。Stage が1つ進むごとに minor を上げる（方式設計12章）。
__version__ = "0.1.0"
