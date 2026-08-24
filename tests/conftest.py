"""全テスト共通の fixture。

対応: 方式設計 `docs/design/stage0-architecture.md` 10.3（プロジェクト用 fixture）/
10.4（ネットワーク遮断）、品質基準 Q6、PO 制約 C-1・C-2。

**このファイルは `media_agent` を import しない。**
T-003（受け入れテスト作成）の時点ではパッケージが存在せず、ここで import すると
全テストが conftest の収集エラー1件に畳まれて「どのシナリオが未実装で落ちたか」が
読めなくなるため。製品への import は各テストモジュール、または fixture の内側で行う。
"""

from __future__ import annotations

import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

# --------------------------------------------------------------------------------------
# ネットワーク遮断（方式設計 10.4 / PO 制約 C-1・C-2 / 品質基準 Q6）
#
# Stage 0 に外部接続は存在しない。「書かないこと」をレビューの目視に委ねず、
# 外へ出た瞬間にテストが落ちる状態にする。
# --------------------------------------------------------------------------------------

_BLOCKED_FAMILIES = frozenset({socket.AF_INET, socket.AF_INET6})
_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0", ""})

_real_connect = socket.socket.connect
_real_connect_ex = socket.socket.connect_ex
_real_create_connection = socket.create_connection
_real_getaddrinfo = socket.getaddrinfo


class NetworkAccessBlockedError(RuntimeError):
    """テスト実行中に外向きのネットワーク接続が試みられた。

    Stage 0 は外部サービスへ接続しない（PO 制約 C-1・C-2、品質基準 Q6）。
    この例外が出た場合、設計かテストか実装のいずれかが誤っている。
    """


def _is_loopback(address: Any) -> bool:
    host = address[0] if isinstance(address, (tuple, list)) and address else address
    return isinstance(host, str) and host in _LOOPBACK_HOSTS


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """外向きの TCP/UDP 接続と名前解決を例外にする（autouse）。

    - AF_INET / AF_INET6 のみを対象にする（AF_UNIX は対象外）
    - ループバック宛は通す。遮断の目的は「外部サービスへ出ないこと」であり、
      ローカル通信まで塞ぐと将来テスト基盤側が壊れるだけで意味が無い
    """

    def guarded_connect(
        self: socket.socket, address: Any, *args: Any, **kwargs: Any
    ) -> Any:
        if self.family in _BLOCKED_FAMILIES and not _is_loopback(address):
            raise NetworkAccessBlockedError(
                f"外向きのネットワーク接続が試みられました: {address!r}"
            )
        return _real_connect(self, address, *args, **kwargs)

    def guarded_connect_ex(
        self: socket.socket, address: Any, *args: Any, **kwargs: Any
    ) -> Any:
        if self.family in _BLOCKED_FAMILIES and not _is_loopback(address):
            raise NetworkAccessBlockedError(
                f"外向きのネットワーク接続が試みられました: {address!r}"
            )
        return _real_connect_ex(self, address, *args, **kwargs)

    def guarded_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        if not _is_loopback(address):
            raise NetworkAccessBlockedError(
                f"外向きのネットワーク接続が試みられました: {address!r}"
            )
        return _real_create_connection(address, *args, **kwargs)

    def guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if host is not None and not (isinstance(host, str) and host in _LOOPBACK_HOSTS):
            raise NetworkAccessBlockedError(
                f"外部ホストの名前解決が試みられました: {host!r}"
            )
        return _real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", guarded_create_connection)
    monkeypatch.setattr(socket, "getaddrinfo", guarded_getaddrinfo)
    yield


# --------------------------------------------------------------------------------------
# 環境の分離（方式設計 6.2・6.3、罠 T-3）
# --------------------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def isolate_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """プロジェクトの解決先が実行環境に依存しないようにする。

    `MEDIA_AGENT_PROJECT_DIR`（方式設計 6.2）が実行環境に設定されていると、
    `-C` を渡していないテストが意図しないプロジェクトを掴む。
    """
    monkeypatch.delenv("MEDIA_AGENT_PROJECT_DIR", raising=False)


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    """`init` していない空のディレクトリ（方式設計 10.3、罠 T-3）。

    テストは必ず `tmp_path` 上を対象にし、`-C` で明示する。`os.chdir` は使わない。
    """
    target = tmp_path / "workspace"
    target.mkdir()
    return target
