# Media Agent とは

Media Agent は、**任意のプロジェクトへ導入して使える、AI によるメディア運用 Agent 基盤**である。

単純な SNS 自動投稿ツールではない。

> 情報を収集し、価値を判断し、コンテンツを生成し、投稿し、結果を分析し、その結果を次の運用戦略へ反映する

という一連のメディア運用を、Agent によって自動化・半自動化することを目的とする。

初期の対象メディアは X だが、**Core は SNS や X 固有の仕様から独立させてある。**
将来的に複数の SNS・メディアへ拡張できる構造を保つ。

## 設計上の約束

| 約束 | 意味 |
| --- | --- |
| Project Independent | 本体は特定のプロジェクトに依存しない。設定・知識・独自 Agent は導入先プロジェクト側（`.media-agent/`）に置く |
| Agent Driven | 機能を関数ではなく、独立した責務（Agent）として分割する |
| 段階的な自動化 | Human → AI 提案 → 人が承認 → AI 実行 → 自律実行、の順で自動化レベルを上げる。最初から全自動にしない |
| Decision と Action の分離 | Agent の判断 → Policy 判定 → Action → 外部サービス、の順に通す。AI が誤った判断をしても、Action を実行する前に止められる |
| 追跡できること | Agent の判断は監査記録（`audit.jsonl` と DB）へ残す。運用ログとは別に持つ |

## 4層構造

```
Media Agent
├── Core        Agent Runtime / Task / Policy / DB / Memory / Logger / Scheduler
├── Media       Research / Content / Analytics / Engagement / Strategy / Orchestrator
└── Connectors  X / Google News / RSS / Web
        │
   導入先プロジェクト（.media-agent/）
```

**現在実装されているのは Core と、Core を動かすための CLI・Project 層だけである**（Stage 0）。
Media 層と Connector 層は、位置だけを予約してある。何が動いて何が動かないかは「Stage 0 でできること・できないこと」を参照。
