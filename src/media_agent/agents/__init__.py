"""Media Layer（要件定義書6節）。

**Stage 0 は検証用の組み込み Agent のみ**である（方式設計 5.1）。Content / Research /
Strategy / Analytics / Engagement / Orchestrator の各 Agent は Stage 1 以降（拡張点 E-1）。

依存の向き: `agents/` は `core/` を import してよい。**`core/` は `agents/` を
import しない**（方式設計 5.2）。組み込み Agent は `AgentRegistry` へ**外から**登録される。
"""
