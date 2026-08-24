# Stage 0 でできること・できないこと

現在の実装状況は **Stage 0（Media Agent Core）** である。
Stage 0 の目的は「汎用基盤を任意のプロジェクトへ導入して動かせる」ところまでを作ることであり、
**メディア運用そのもの（情報収集・コンテンツ生成・投稿）はまだ動かない。**

## 動くもの

| 機能 | 実体 |
| --- | --- |
| CLI | `media-agent` コマンド。実装済みは `init` / `doctor` / `status` / `run` / `agent list` / `task list` |
| Project 初期化 | `media-agent init` が導入先に `.media-agent/` を生成する |
| Config | `.media-agent/config.yaml` の読み込み・スキーマ検証・版数検査 |
| DB | `.media-agent/data/media-agent.db`（SQLite）。Task・判断・Agent 等の 6 テーブル |
| Task | Task の生成と状態遷移（`pending` / `running` / `completed` / `failed` / `cancelled`） |
| Agent Runtime | Agent の登録簿と実行器。検証用の組み込み Agent `echo` / `fail` が動く |
| Policy 基盤 | `config.yaml` の `actions` / `limits` に基づく `allow` / `require_approval` / `deny` の判定 |
| Logging / Audit | 運用ログ `logs/media-agent.log` と、監査記録 `logs/audit.jsonl`（+ DB の判断記録） |
| Test 基盤 | 単体テスト・受け入れテスト・lint・型検査・GitHub Actions |

## 動かないもの

**次のものは Stage 0 には存在しない。**「設定すれば動く」のではなく、実装されていない。

| 動かないもの | いつ入る予定か |
| --- | --- |
| X（旧 Twitter）への投稿・返信・リポスト | Stage 3 |
| ニュース・RSS・Web からの情報収集 | Stage 2 |
| AI（LLM）によるコンテンツ生成・評価 | Stage 1 |
| 投稿結果の分析、戦略への反映 | Stage 4 / Stage 5 |
| Custom Agent の読み込み・実行 | Stage 6（Stage 0 では設計のみ） |
| Claude Code 連携 Skill の導入 | Stage 7（Stage 0 では設計のみ） |
| スケジュール実行（GitHub Actions からの定期実行） | Stage 3 以降 |

`setup` / `post` / `research` / `analyze` の 4 コマンドは、**呼ぶと未実装である旨を標準エラーへ出し、終了コード 10 で終わる。**
黙って成功しない。スクリプトや CI から呼んだときに、未実装が成功として通過しないようにするためである。

```
$ media-agent post
Error: `media-agent post` は Stage 0 では未実装です（Stage 3 で実装予定）
  - X Connector が Stage 3 で入る
$ echo $?
10
```

## 認証情報は要らない

**Stage 0 は外部サービスへ一切接続しない。**

- X の API キー、アクセストークン、LLM の API キーは**どれも不要**である
- `.env` を置く必要はない。設定する場所も無い
- `media-agent doctor` は `.env` が無いことを異常として扱わない（`security.env_not_tracked` は `[skipped]` になる）
- 動作確認のために外部アカウントを用意する必要も、課金の発生する API を呼ぶ必要も無い

外部接続を持たないことは、テストでも機械的に確認している（ネットワーク遮断のテスト・依存パッケージの検査）。

## Stage 1 以降のロードマップ

| Stage | 内容 |
| --- | --- |
| **Stage 0（現在）** | Media Agent Core — CLI / Project / Config / DB / Task / Agent Runtime / Policy / Logging・Audit / Test 基盤 |
| Stage 1 | Content Agent — 過去投稿の取り込み、重複チェック、コンテンツ生成 |
| Stage 2 | Research Agent — Google News / RSS / Web からの情報収集 |
| Stage 3 | X Publisher — X Connector と自動投稿、GitHub Actions 実行 |
| Stage 4 | Media Strategy — Strategy Agent |
| Stage 5 | Analytics Agent — 投稿結果の分析 |
| Stage 6 | Engagement Agent、Custom Agent の実行 |
| Stage 7 | Orchestrator — 全体の統括実行、Claude Code 連携 |
| Stage 8 | Distribution / Plugin Platform — Package として配布 |
