"""テスト基盤の自己検査: ネットワーク遮断 fixture が実際に効いていること。

| 項目 | 出所 |
| --- | --- |
| 追加した理由 | 方式設計 10.4（ネットワーク遮断は機構で担保する）/ 品質基準 Q6 / PO 制約 C-1・C-2 |
| 位置づけ | **S-A〜S-I ではない。** 完了条件を検証するテストではなく、テスト基盤の自己検査である |

遮断が黙って外れていると、「外部接続が無いこと」の担保が見かけだけになる。
そのため遮断そのものを検査する。`media_agent` を import しないので、
このファイルだけは製品の実装状況にかかわらず実行できる。
"""

from __future__ import annotations

import socket

import pytest

from tests.conftest import NetworkAccessBlockedError

pytestmark = pytest.mark.acceptance


def test_outbound_tcp_connect_is_blocked() -> None:
    """外向きの TCP 接続は例外になる。"""
    with (
        pytest.raises(NetworkAccessBlockedError),
        socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock,
    ):
        sock.settimeout(1)
        sock.connect(("example.com", 80))


def test_create_connection_is_blocked() -> None:
    """`socket.create_connection` も塞がれている。"""
    with pytest.raises(NetworkAccessBlockedError):
        socket.create_connection(("example.com", 80), timeout=1)


def test_dns_resolution_of_external_hosts_is_blocked() -> None:
    """外部ホストの名前解決も塞がれている。"""
    with pytest.raises(NetworkAccessBlockedError):
        socket.getaddrinfo("example.com", 80)
