"""スタブコマンド（方式設計 6.4 / 用語集「スタブコマンド」）。

**プロジェクトの状態を見る前に終了コード 10 で終わる**（詳細設計 17.2）。
未実装であることは環境に依存しないため。標準出力には何も出さない。
"""

from __future__ import annotations

import click

from media_agent.errors import NotImplementedInStageError

#: コマンド名 → (実装予定の Stage, 何が来たら実装できるか)。出所: 方式設計 6.4。
STUB_COMMANDS: dict[str, tuple[int, str]] = {
    "setup": (3, "設定対象となる Connector・認証が Stage 3 で入る"),
    "post": (3, "X Connector が Stage 3 で入る"),
    "research": (2, "Research Agent が Stage 2 で入る"),
    "analyze": (5, "Analytics Agent が Stage 5 で入る"),
}


def _make_stub(name: str, stage: int, reason: str) -> click.Command:
    @click.command(name, help=f"（Stage {stage} で実装予定。Stage 0 では未実装）")
    def _stub() -> None:
        raise NotImplementedInStageError(
            f"`media-agent {name}` は Stage 0 では未実装です（Stage {stage} で実装予定）",
            details=[reason],
        )

    return _stub


def stub_commands() -> list[click.Command]:
    """スタブ4種を作る。"""
    return [
        _make_stub(name, stage, reason)
        for name, (stage, reason) in STUB_COMMANDS.items()
    ]
