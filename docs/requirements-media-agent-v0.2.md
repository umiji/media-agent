# Media Agent 要件定義書

> **出典**: PO が 2026-08-23 にセッションへ提示した原文を、参照可能にするためリポジトリへ収めたもの。
> **この文書はオーケストレーターだけが更新する。** 内容の解釈で迷ったら推測せず、オーケストレーターへ差し戻すこと。
> 今回のゴールは **Stage 0 のみ**。範囲と達成条件は `docs/handover.md` にある。

Version: 0.2
Status: Draft / Architecture Definition
Primary Development Environment: Claude Code
Initial Target Platform: X
Deployment Strategy: Local → GitHub Actions → VPS等へ拡張

---

## 1. プロダクト概要

### 1.1 プロダクト名

Media Agent

### 1.2 プロダクトの目的

Media Agentは、プロジェクトごとに導入可能な、AIによるメディア運用Agent基盤である。

単純なSNS自動投稿ツールではなく、

«情報を収集し、価値を判断し、コンテンツを生成し、投稿し、結果を分析し、その結果を次の運用戦略へ反映する»

一連のメディア運用をAgentによって自動化・半自動化することを目的とする。

初期MVPではXを対象とするが、システムのCoreはSNSやX固有仕様から独立させ、将来的に複数のSNS・メディアへ拡張可能な構造とする。

---

## 2. プロダクトの基本思想

### 2.1 Project Independent

Media Agent本体は特定プロジェクトに依存しない。ユーザーは任意のプロジェクトにMedia Agentを導入できる。

### 2.2 Agent Driven

機能を単なる関数・処理としてではなく、将来的にAgentとして独立可能な責務単位に分割する。

### 2.3 Human → AI Assisted → Autonomous

自動化レベルを段階的に引き上げる。Human → AI Suggest → Human Approve → AI Execute → AI Autonomous。
すべてを最初から完全自動化しない。

### 2.4 DecisionとActionを分離

Agent Decision → Policy Check → Action → External Service。
これにより、AIが誤判断してもAction実行前に制御できる構造とする。

### 2.5 再利用可能な基盤

Media Agent本体はCLI / Packageとして配布可能にし、各プロジェクト固有の設定・Knowledge・Agentはプロジェクト側に保持する。

---

## 3. 想定利用者

### 3.1 Primary User

開発者・個人事業者・プロジェクトオーナーなど、自身のメディア運用をAIで自動化したいユーザー。

### 3.2 初期利用方法

```
pip install media-agent
cd my-project
media-agent init      # プロジェクト固有設定を作成
media-agent run
```

またはClaude CodeからMedia Agentを操作する。

---

## 4. システム全体構成

Media Agentは以下の4層を基本構造とする。

```
┌───────────────────────────────────────────┐
│                Media Agent                │
│  ┌─────────────────────────────────────┐  │
│  │              Core                   │  │
│  │ Agent Runtime / Task / Policy / DB  │  │
│  │ Memory / Logger / Scheduler         │  │
│  └──────────────────┬──────────────────┘  │
│  ┌──────────────────▼──────────────────┐  │
│  │             Media Layer             │  │
│  │ Research / Content / Analytics      │  │
│  │ Engagement / Strategy / Orchestrator│  │
│  └──────────────────┬──────────────────┘  │
│  ┌──────────────────▼──────────────────┐  │
│  │             Connectors              │  │
│  │ X / Google News / RSS / Web         │  │
│  └──────────────────┬──────────────────┘  │
└─────────────────────┼─────────────────────┘
              ┌───────▼────────┐
              │    Project     │
              │ .media-agent/  │
              └────────────────┘
```

---

## 5. Core Layer

Media Agentの汎用的な実行基盤。

### 5.1 Agent Runtime

Agentを登録・実行・管理する。必要機能：Agent登録 / Agent実行 / AgentへのInput渡し / Agent Output取得 /
Agent実行状態管理 / Agentエラー処理 / Agent実行ログ。

### 5.2 Task

Agentが実行する仕事をTaskとして管理する。Taskは `pending` / `running` / `completed` / `failed` / `cancelled`
等の状態を持つ。将来的にはOrchestratorが大きな目標をTaskへ分解する。

### 5.3 Policy Engine

Action実行前のルールチェックを担当する。例：

```yaml
actions:
  post:
    mode: auto
    max_per_day: 3
  reply:
    mode: approval
  repost:
    mode: approval
  like:
    mode: disabled
```

Policyはプロジェクト単位で設定可能とする。

### 5.4 Memory

Project単位のMemoryを保持する。Memoryは他プロジェクトと完全分離する。
主な対象：過去投稿 / 過去コンテンツ / 投稿結果 / AI判断履歴 / プロジェクト固有Knowledge。

### 5.5 Logger / Audit

Agentの判断・実行を記録する。最低限、

```
timestamp / agent / task / input / decision / reason / action / result / error
```

を記録する。特にAIが「なぜその判断をしたか」を追跡可能にする。

### 5.6 Scheduler

定期実行を管理する。初期環境では Local cron / GitHub Actions を利用可能とする。
将来的にVPS等へ拡張可能な設計とする。

---

## 6. Media Layer

メディア運用固有のAgent群。

### 6.1 Research Agent

外部情報を収集する。初期対象：Google News / RSS / 指定Webサイト / X Trend。将来的に追加可能なConnector構造とする。

### 6.2 Trend Agent

収集した情報から、話題性 / 新規性 / 関連性 / 投稿価値 等を評価する。

### 6.3 Content Agent

情報・プロジェクト設定・過去コンテンツを元にX投稿を生成する。
初期仕様：複数案生成 / 投稿評価 / 最適案選択 / 重複チェック / ブランドルール適用。

### 6.4 Strategy Agent

「何を投稿するか」を判断する。
入力：Research結果 / Trend情報 / 過去投稿 / 投稿パフォーマンス / Project Strategy。
出力：今日の投稿テーマ / 投稿優先順位 / 投稿形式 / 投稿タイミング / 投稿数。

### 6.5 Analytics Agent

投稿結果を分析する。分析対象：インプレッション / Like / Reply / Repost / その他取得可能な指標。
目的：結果 → 要因分析 → 成功パターン → 失敗パターン → 次回戦略。

### 6.6 Engagement Agent

X上の関連投稿・ユーザーとのInteraction候補を判断する。
対象：Like候補 / Reply候補 / Repost候補 / 自分へのReply / メンション。
初期段階では候補生成・評価を中心とする。完全自動Actionについては、X API・規約・Policyを確認した上で段階的に実装する。

### 6.7 Orchestrator

各Agentを統括する最終的な司令塔。
責務：Goal受領 / Task分解 / Agent選択 / Agent実行 / 結果評価 / 次Task決定 / エラー処理 / Userへのエスカレーション。

---

## 7. Connector Layer

外部サービスとの接続を担当する。

### 7.1 X Connector

初期対象。想定機能：Post / 投稿情報取得 / Metrics取得 / Reply関連処理 / その他APIで利用可能なAction。
**X Webサイトへのブラウザ自動操作を正式な実装方式とはしない。**

### 7.2 Google News Connector

ニュース検索・情報取得を担当する。

### 7.3 RSS Connector

RSSから情報を取得する。既存のRSSベースの投稿データもMedia Agentから利用できる構造とする。

### 7.4 Web Connector

指定Webサイトから必要情報を取得する。取得方式は対象サイト・利用規約・技術条件に応じて決定する。

---

## 8. Project Layer

各プロジェクト固有の情報を保持する。

### 8.1 Project Directory

```
my-project/
├── .media-agent/
│   ├── config.yaml
│   ├── strategy.md
│   ├── rules.md
│   ├── agents/
│   ├── memory/
│   ├── data/
│   └── logs/
└── existing-project-files/
```

### 8.2 config.yaml

```yaml
project:
  name: pergram
media:
  primary_platform: x
content:
  posts_per_day: 3
automation:
  require_approval: false
```

### 8.3 strategy.md

プロジェクトのメディア戦略を自然言語で定義する。例：ターゲット / ブランドトーン / メディア目的 / 投稿方針 / コンテンツ方針。

### 8.4 rules.md

禁止事項・ブランドルール・投稿ルール等を定義する。

### 8.5 Custom Agents

ユーザー独自Agentを追加可能とする。例：`.media-agent/agents/protein-expert.md`。
Media Agent CoreはCustom Agentをロード・実行可能な設計とする。

---

## 9. Claude Code Integration

Claude CodeをMedia Agentの主要な操作インターフェースの一つとする。

### 9.1 Claude Code Skill

プロジェクト初期化時に必要なClaude Code用Skill / Agent定義を導入可能とする。

```
my-project/
└── .claude/
    ├── agents/
    └── skills/
        └── media-agent/
```

### 9.2 Claude Codeからの操作

「今日のメディア運用を実行して」 → Claude Code → Media Agent CLI → Orchestrator / Agents という構造を想定する。

---

## 10. CLI要件

基本CLIを提供する。想定コマンド：

```
media-agent init
media-agent setup
media-agent doctor
media-agent run
media-agent status
media-agent research
media-agent post
media-agent analyze
media-agent task
media-agent agent
```

- `init` — 現在のプロジェクトにMedia Agentを導入する
- `setup` — Project設定・Connector等を設定する
- `doctor` — 設定・認証・依存関係等を検証する
- `run` — Media AgentのWorkflowを実行する
- `status` — 現在のAgent / Task / Workflow状態を確認する

---

## 11. コンテンツ重複防止

既存のRSSベース投稿データを利用する。

### 11.1 目的

新しい投稿を生成する際に、過去投稿との完全一致 / 類似内容 / 同一ニュースの重複 / 同一テーマの過剰反復 を防止する。

### 11.2 処理

Existing CSV → Import → Historical Content Memory → New Source → Similarity Check → Content Generation

既存CSVをそのまま永続DBとするか、Media Agent内部DBへImportするかはStage 0/1の技術検証で決定する。

---

## 12. Human Approval

承認機能はMVP初期では最小限とし、将来的に拡張する。

- 初期：AI → CLIに結果表示 → User
- 将来：AI → Approval Queue → CLI / LINE等 → Approve / Edit / Reject

LINE等の通知・承認インターフェースは将来拡張とする。

---

## 13. Automation Policy

Actionごとに自動化レベルを設定可能とする。

```yaml
actions:
  post:
    mode: auto
  reply:
    mode: approval
  repost:
    mode: approval
  like:
    mode: disabled
```

さらに、1日最大投稿数 / 1時間最大Action数 / 特定トピック禁止 / 特定ユーザーへのAction禁止 / Approval必須条件
等を設定可能とする。

---

## 14. Security

### 14.1 Credential Management

MVPでは環境変数 / `.env` 方式を基本とする。将来的に OS Keychain / Secret Manager / GitHub Secrets 等へ拡張する。

### 14.2 Secrets

API Key、OAuth Token等のCredentialをGitへコミットしない。`.gitignore` および設定検証で保護する。

---

## 15. AIモデル方針

Claude Codeを開発環境および主要なAIインターフェースとして利用する。
実運用時のAI処理については、初期MVPではClaude Codeを中心とする。
ただし、将来的なLLM変更・複数モデル利用を妨げないよう、AI ProviderをCoreから分離可能な構造とする。

---

## 16. データ要件

最低限以下のEntityを管理する。

| Entity | 項目 |
| --- | --- |
| Project | project_id / name / configuration / created_at / updated_at |
| Source | source_id / title / url / source_type / content / collected_at / score |
| Post | post_id / content / topic / source / status / created_at / scheduled_at / published_at |
| Performance | post_id / impressions / likes / replies / reposts / collected_at |
| Task | task_id / agent / type / status / input / output / created_at / completed_at |
| Decision | decision_id / agent / input / decision / reason / timestamp |

---

## 17. Logging / Audit要件

すべての重要なAgent実行について追跡可能とする。例：

```
10:00 Research Agent started
10:01 12 sources collected
10:02 Trend Agent scored sources
10:03 Strategy Agent selected topic
10:04 Content Agent generated 3 posts
10:05 Policy Agent approved Post #12
10:05 Publisher posted Post #12
10:06 Result saved
```

これにより、デバッグ / AI判断検証 / 失敗原因分析 / コスト分析 / 将来のAgent改善 を可能にする。

---

## 18. MVPロードマップ

### Stage 0 — Media Agent Core

**実装**: Git Repository / Python Package / CLI / Project初期化 / `.media-agent/` / Config / DB /
Logging / Audit / Task / Agent Interface / Policy基盤 / Test基盤

**検証**: `media-agent init` → Project生成 → `media-agent doctor` → `media-agent status` が正常動作すること。

### Stage 1 — Content Agent

**実装**: 既存CSV読み込み / 過去投稿Import / Content Memory / 重複チェック / Content生成 / 複数案生成 / AI評価 / 投稿履歴保存

**検証**: 過去投稿と類似した内容を避けながら、実用的なX投稿案を生成できること。

### Stage 2 — Research Agent

**実装**: Google News / RSS / 指定Webサイト / 情報収集 / 重複除去 / 情報分類 / 関連性評価 / 投稿価値評価

**検証**: 指定テーマについて「投稿する価値のある情報」をAIが抽出できること。

### Stage 3 — X Publisher

**実装**: X Connector / 投稿Queue / Scheduler / 自動投稿 / 投稿結果保存 / Retry / Error Handling

**検証**: Source → Content → Queue → Scheduler → X が正常動作すること。

### Stage 4 — Media Strategy

**実装**: Research → Strategy → Content → Publisher を統合。AIが「今日何を投稿するか」を判断する。

**検証**: 人間が投稿テーマを毎回指定しなくても、AIが妥当な投稿テーマを選択できること。

### Stage 5 — Analytics Agent

**実装**: 投稿Metrics取得 / 投稿分析 / 成功パターン分析 / 失敗パターン分析 / StrategyへのFeedback

**検証**: 投稿結果を分析し、次回投稿戦略に具体的な改善提案を反映できること。

### Stage 6 — Engagement Agent

**実装**: X Trend / X Search / 関連投稿候補 / Reply候補 / Like候補 / Repost候補 / AI評価 / Policy Check。
初期段階ではHuman-in-the-loopを基本とする。

**検証**: 関連性・返信価値・リスク等を考慮して、適切なAction候補を提示できること。

### Stage 7 — Orchestrator

**実装**: Goal / Task decomposition / Agent selection / Agent execution / Result evaluation / Next action /
Error recovery / Human escalation

**検証**: 「今日のメディア運用を実行」という高レベル指示だけで、Research → Strategy → Content → Policy →
Publish → Analytics を自律的に実行できること。

### Stage 8 — Distribution / Plugin Platform

**実装**: Package distribution / CLI install / Project initialization / Claude Code integration /
Custom Agent loading / Connector extension mechanism / Documentation

---

## 19. MVP Stage対応表

| 要件 | S0 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CLI | ● | | | | | | | | ● |
| Project管理 | ● | | | | | | | | ● |
| Config | ● | ● | ● | ● | ● | ● | ● | ● | ● |
| DB | ● | ● | ● | ● | ● | ● | ● | ● | |
| Agent Runtime | ● | ● | ● | ● | ● | ● | ● | ● | |
| Task | ● | ● | ● | ● | ● | ● | ● | ● | |
| Policy | ● | ● | ● | ● | ● | ● | ● | ● | |
| Logging / Audit | ● | ● | ● | ● | ● | ● | ● | ● | |
| 過去投稿Import | | ● | | | | | | | |
| 重複チェック | | ● | | | ● | ● | ● | ● | |
| Content Agent | | ● | | | ● | ● | ● | ● | |
| Research Agent | | | ● | ● | ● | ● | ● | ● | |
| Google News | | | ● | | | | | | |
| RSS | | | ● | | | | | | |
| Web | | | ● | | | | | | |
| X Connector | | | | ● | ● | ● | ● | ● | |
| 自動投稿 | | | | ● | ● | ● | | ● | |
| Strategy Agent | | | | | ● | ● | ● | ● | |
| Analytics Agent | | | | | | ● | ● | ● | |
| Engagement Agent | | | | | | | ● | ● | |
| Orchestrator | | | | | | | | ● | |
| Custom Agent | 設計 | | | | | | ● | ● | ● |
| Claude Code連携 | 設計 | | | | | | | ● | ● |
| GitHub Actions | | | | ● | ● | ● | ● | ● | ● |
| Package配布 | | | | | | | | | ● |

**S0 の `設計` は、実装ではなく設計だけを行うという意味である。**

---

## 20. 非機能要件

| # | 要件 |
| --- | --- |
| 20.1 拡張性 | 新しいAgent、Connector、LLM、SNSを追加できる構造とする |
| 20.2 保守性 | CoreとProject固有ロジックを分離する |
| 20.3 可観測性 | Agentの実行状況・判断・Actionを追跡可能とする |
| 20.4 安全性 | AIの判断とAction実行を分離し、Policy Engineによって制御する |
| 20.5 再現性 | 同じInput・設定・Agent Versionから、実行内容を追跡可能とする |
| 20.6 移植性 | Local、GitHub Actions、Docker、VPS等で実行可能な構造を目指す |

---

## 21. GitHub公開時の利用モデル

Media Agent本体はPackageとして配布し、Project固有の設定・Agent・Memoryはユーザー側で管理する。
これにより、Media AgentのアップデートとProjectの独立性を確保する。

---

## 22. 将来拡張

- SNS拡張：X / Threads / Instagram / YouTube / LinkedIn 等
- Agent拡張：Research / Content / SEO / Video / Community Agent 等
- Notification拡張：CLI / LINE / Slack / Discord / Telegram 等
- AI拡張：複数LLM Providerへの対応

---

## 23. MVPで意図的に実装しないもの

Web管理画面 / Agent Marketplace / 複雑なGUI / 複数SNSの同時対応 / LINE通知 / 完全自律的な全Action /
高度なVector Database / SaaS化 / マルチユーザー管理 / 課金システム。

**「将来可能な構造」にすることと、「MVPで実装すること」を明確に分離する。**

---

## 24. 未決事項

現時点では以下を今後の設計工程で決定する。

1. Pythonの具体的な依存ライブラリ
2. CLI Framework
3. DB方式
4. Agent定義フォーマット
5. Agent Runtimeの実装方式
6. Claude Code Skillの具体仕様
7. X APIの具体的な利用方式
8. Google News取得方式
9. Web取得方式
10. AI処理の具体的な実行方式
11. GitHub Actions Workflow
12. Package配布方式
13. Version管理
14. Migration方式
15. Test Strategy
16. Project Config Schema
17. Memory / Similarity検索方式
18. Agent Plugin API
19. Orchestratorの具体的なTask管理方式

**これらは要件定義後の基本設計・詳細設計フェーズで決定する。**

---

## 25. 次工程

要件定義 → 基本アーキテクチャ設計 → Stage 0詳細設計 → Claude Code開発仕様書 → Stage 0実装 →
実環境検証 → Stage 0完了 → Stage 1 → ...

**各Stageは、実装完了ではなく「実運用上の検証完了」をもって完了とする。**

---

## 26. 開発原則

| # | 原則 |
| --- | --- |
| 1 | 最初から巨大なAgentシステムを作らない |
| 2 | 各Stageで動くものを作る |
| 3 | 各Stage終了時に実際に検証する |
| 4 | 将来のAgent化を考えて責務を分離する |
| 5 | AI DecisionとActionを分離する |
| 6 | Project固有情報をCoreに混ぜない |
| 7 | 過去の判断・Action・結果を可能な限り記録する |
| 8 | 自動化レベルをPolicyで制御する |
| 9 | Claude Codeを開発・運用インターフェースの中心に据える |
| 10 | 「実装できること」ではなく「実際にメディア運用の価値を生むこと」を各Stageの評価基準とする |

---

## 27. 現時点の最終MVPゴール

```
Media Agent → Project設定 → Research → (Google News / RSS / Web)
  → AI情報評価 → Content Agent → 重複チェック → 投稿生成・評価
  → Policy Check → X Publisher → X投稿 → 結果保存
```

ユーザーが最終的に `media-agent run`、またはClaude Codeから「今日のメディア運用を実行して」と指示するだけで、
この一連の処理が実行される状態をMVPの主要ゴールとする。
その後、Analytics → Engagement → Orchestrator へ段階的に自律性を高める。

---

## 28. 次回開発開始地点

次工程ではStage 0の基本設計を行う。最初に決定する対象：

1. Repository構造
2. Python package構造
3. CLI設計
4. `.media-agent/` 構造
5. `.claude/` 連携構造
6. Config Schema
7. DB Schema
8. Agent Interface
9. Task Model
10. Policy Model
11. Logging / Audit
12. Test構造
13. GitHub Actions
14. Version管理

**Stage 0ではまだX APIやニュース取得等を実装しない。**

まず、«「Media Agentという汎用基盤を、任意のプロジェクトに導入して動かせる」» ところまでを作り、
実際にCLI・Project初期化・Config・Agent実行・ログ・Policy等を検証する。これをStage 0の技術的基盤とする。
