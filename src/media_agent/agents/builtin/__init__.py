"""検証用の組み込み Agent（詳細設計 8.4）。

| name | version | 挙動 |
| --- | --- | --- |
| `echo` | 1 | 入力をそのまま返す |
| `fail` | 1 | 常に `AgentFailedForVerificationError` を送出する |

**どちらも AI を呼ばない・ネットワークへ出ない・ファイルを書かない**
（PO 制約 C-1〜C-3、品質基準 Q6・Q9）。

主な公開物（申し送り K-1 により、ここで再エクスポートする）。
"""

from __future__ import annotations

from media_agent.agents.builtin.echo import EchoAgent
from media_agent.agents.builtin.fail import AgentFailedForVerificationError, FailAgent
from media_agent.agents.builtin.registry import BUILTIN_AGENTS, build_default_registry

__all__ = [
    "BUILTIN_AGENTS",
    "AgentFailedForVerificationError",
    "EchoAgent",
    "FailAgent",
    "build_default_registry",
]
