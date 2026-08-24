"""Stage 0 で実装するが、**本タスク（T-004）では中身を持たないコマンド**の目印。

T-004 の範囲は「CLI にコマンドを登録する枠」までである（T-004 変更範囲）。
中身は DB（T-005）/ Runtime・Task・Policy（T-006）/ doctor・status・run（T-007）が入れる。

**終了コード 0 で黙って成功しない。** ここへ来た場合は想定外の内部エラー（終了コード 70）として
扱われる。スタブコマンド（終了コード 10）とは別物である — スタブは「Stage 0 では実装しない」、
こちらは「Stage 0 で実装するが、まだ来ていない」を意味する。
"""

from __future__ import annotations

from typing import NoReturn


def not_implemented_yet(command: str, task: str) -> NoReturn:
    """本体が未実装であることを、成功と区別できる形で知らせる。"""
    raise NotImplementedError(
        f"`{command}` の本体はまだ実装されていません（{task} の担当範囲です）"
    )
