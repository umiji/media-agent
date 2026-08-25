# Media Agent ハンドブック

<!-- このファイルは自動生成物です。直接編集しないでください。
     マスタ: docs/features/overview.md / docs/features/stage0-scope.md / docs/guides/install.md / docs/guides/quickstart.md / docs/features/cli.md / docs/features/project-directory.md / docs/guides/verification-stage0.md / docs/guides/development.md
     生成:   python3 docs/tools/build_docs.py -->

Media Agent の利用者向け文書を 1 つに結合したものです。
個別の文書は `docs/features/` と `docs/guides/` にあります。

## 目次

- [Media Agent とは](#media-agent-とは)
  - [設計上の約束](#設計上の約束)
  - [4層構造](#4層構造)
- [Stage 0 でできること・できないこと](#stage-0-でできることできないこと)
  - [動くもの](#動くもの)
  - [動かないもの](#動かないもの)
  - [認証情報は要らない](#認証情報は要らない)
  - [Stage 1 以降のロードマップ](#stage-1-以降のロードマップ)
- [インストール](#インストール)
  - [前提](#前提)
  - [取得とインストール](#取得とインストール)
  - [疎通確認](#疎通確認)
  - [導入先プロジェクトで使う](#導入先プロジェクトで使う)
  - [アンインストール](#アンインストール)
- [はじめての Media Agent](#はじめての-media-agent)
  - [1. プロジェクトを初期化する](#1-プロジェクトを初期化する)
  - [2. 健全性を確認する](#2-健全性を確認する)
  - [3. 現在の状態を見る](#3-現在の状態を見る)
  - [4. Agent を実行する](#4-agent-を実行する)
  - [5. 記録を確認する](#5-記録を確認する)
  - [6. 設定を変える](#6-設定を変える)
  - [ここから先](#ここから先)
- [CLI リファレンス](#cli-リファレンス)
  - [実行の経路](#実行の経路)
  - [出力例の読み方](#出力例の読み方)
  - [グローバルオプション](#グローバルオプション)
  - [コマンド一覧](#コマンド一覧)
  - [`media-agent init`](#media-agent-init)
  - [`media-agent doctor`](#media-agent-doctor)
  - [`media-agent status`](#media-agent-status)
  - [`media-agent run`](#media-agent-run)
  - [`media-agent agent list`](#media-agent-agent-list)
  - [`media-agent task list`](#media-agent-task-list)
  - [終了コード](#終了コード)
- [プロジェクトディレクトリ `.media-agent/`](#プロジェクトディレクトリ-media-agent)
  - [Git で追跡するもの・しないもの](#git-で追跡するものしないもの)
  - [`config.yaml`](#configyaml)
  - [運用ログと監査記録は別物](#運用ログと監査記録は別物)
  - [DB](#db)
- [Stage 0 動作確認手順書](#stage-0-動作確認手順書)
  - [確認する範囲](#確認する範囲)
  - [確認しないこと（Stage 0 に無いもの）](#確認しないことstage-0-に無いもの)
  - [認証情報は不要である](#認証情報は不要である)
  - [前提](#前提)
  - [手順 1 — リポジトリを取得する](#手順-1-リポジトリを取得する)
  - [手順 2 — 仮想環境を作り、インストールする](#手順-2-仮想環境を作りインストールする)
  - [手順 3 — インストールされたことを確認する](#手順-3-インストールされたことを確認する)
  - [手順 4 — 確認用のプロジェクトを作る](#手順-4-確認用のプロジェクトを作る)
  - [手順 5 — `media-agent init`（Project 生成）](#手順-5-media-agent-initproject-生成)
  - [手順 6 — `media-agent doctor`（検証）](#手順-6-media-agent-doctor検証)
  - [手順 7 — `media-agent status`（状態表示）](#手順-7-media-agent-status状態表示)
  - [手順 8 — Agent を実行し、記録されることを確認する](#手順-8-agent-を実行し記録されることを確認する)
  - [手順 9 — 失敗が失敗として記録されることを確認する](#手順-9-失敗が失敗として記録されることを確認する)
  - [手順 10 — 未実装のコマンドが「未実装」として振る舞うことを確認する](#手順-10-未実装のコマンドが未実装として振る舞うことを確認する)
  - [手順 11 — 未初期化のディレクトリで正しく止まることを確認する](#手順-11-未初期化のディレクトリで正しく止まることを確認する)
  - [手順 12 — 外部へ接続していないことを確認する（任意）](#手順-12-外部へ接続していないことを確認する任意)
  - [手順 13 — テストが通ることを確認する（任意）](#手順-13-テストが通ることを確認する任意)
  - [手順 14 — 後片付け](#手順-14-後片付け)
  - [確認結果のチェックリスト](#確認結果のチェックリスト)
  - [期待どおりにならなかった場合](#期待どおりにならなかった場合)
- [開発者向け](#開発者向け)
  - [開発環境](#開発環境)
  - [テスト・リント・型検査](#テストリント型検査)
  - [CI](#ci)
  - [ソース構成](#ソース構成)
  - [技術スタック](#技術スタック)
  - [バージョン](#バージョン)
  - [設計と決定の記録](#設計と決定の記録)

---

## Media Agent とは

Media Agent は、**任意のプロジェクトへ導入して使える、AI によるメディア運用 Agent 基盤**である。

単純な SNS 自動投稿ツールではない。

> 情報を収集し、価値を判断し、コンテンツを生成し、投稿し、結果を分析し、その結果を次の運用戦略へ反映する

という一連のメディア運用を、Agent によって自動化・半自動化することを目的とする。

初期の対象メディアは X だが、**Core は SNS や X 固有の仕様から独立させてある。**
将来的に複数の SNS・メディアへ拡張できる構造を保つ。

### 設計上の約束

| 約束 | 意味 |
| --- | --- |
| Project Independent | 本体は特定のプロジェクトに依存しない。設定・知識・独自 Agent は導入先プロジェクト側（`.media-agent/`）に置く |
| Agent Driven | 機能を関数ではなく、独立した責務（Agent）として分割する |
| 段階的な自動化 | Human → AI 提案 → 人が承認 → AI 実行 → 自律実行、の順で自動化レベルを上げる。最初から全自動にしない |
| Decision と Action の分離 | Agent の判断 → Policy 判定 → Action → 外部サービス、の順に通す。AI が誤った判断をしても、Action を実行する前に止められる |
| 追跡できること | Agent の判断は監査記録（`audit.jsonl` と DB）へ残す。運用ログとは別に持つ |

### 4層構造

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

<sub>出典: [`docs/features/overview.md`](features/overview.md)</sub>

---

## Stage 0 でできること・できないこと

現在の実装状況は **Stage 0（Media Agent Core）** である。
Stage 0 の目的は「汎用基盤を任意のプロジェクトへ導入して動かせる」ところまでを作ることであり、
**メディア運用そのもの（情報収集・コンテンツ生成・投稿）はまだ動かない。**

### 動くもの

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

### 動かないもの

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

### 認証情報は要らない

**Stage 0 は外部サービスへ一切接続しない。**

- X の API キー、アクセストークン、LLM の API キーは**どれも不要**である
- `.env` を置く必要はない。設定する場所も無い
- `media-agent doctor` は `.env` が無いことを異常として扱わない（`security.env_not_tracked` は `[skipped]` になる）
- 動作確認のために外部アカウントを用意する必要も、課金の発生する API を呼ぶ必要も無い

外部接続を持たないことは、テストでも機械的に確認している（ネットワーク遮断のテスト・依存パッケージの検査）。

### Stage 1 以降のロードマップ

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

<sub>出典: [`docs/features/stage0-scope.md`](features/stage0-scope.md)</sub>

---

## インストール

### 前提

| 項目 | 条件 |
| --- | --- |
| Python | **3.11 以上**（3.11 / 3.12 / 3.13 で検証している） |
| Git | リポジトリを取得するために使う |
| ネットワーク | 依存パッケージの取得にのみ使う。**Media Agent 自体は外部サービスへ接続しない** |
| 認証情報 | **不要。** X や LLM の API キーは要らない |

```
$ python3 --version
Python 3.11.15
```

### 取得とインストール

**Media Agent はまだ PyPI へ公開していない**（配布は Stage 8）。ソースから入れる。

```sh
git clone https://github.com/umiji/media-agent.git
cd media-agent

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

`-e`（editable）はソースを直接参照する開発向けの入れ方である。使うだけなら `-e` と `[dev]` は省いてよい。

```sh
.venv/bin/python -m pip install .
```

### 疎通確認

```sh
.venv/bin/media-agent --version
```

```
media-agent, version 0.1.0
```

以降このドキュメントでは、次のように仮想環境へパスを通した状態で `media-agent` と書く。

```sh
export PATH="$PWD/.venv/bin:$PATH"
```

パスを通さない場合は `.venv/bin/media-agent ...` と書くか、`python -m media_agent ...` を使う。

### 導入先プロジェクトで使う

Media Agent は**導入先のプロジェクトのディレクトリで実行する。** 本体のリポジトリの中で実行するのではない。

```sh
cd ~/my-project
media-agent init
```

別のディレクトリから対象を指定することもできる。

```sh
media-agent -C ~/my-project status
```

### アンインストール

```sh
.venv/bin/python -m pip uninstall media-agent
```

導入先プロジェクトの `.media-agent/` は残る。不要なら手で削除する
（**中の DB とログも消える。** 消す前に中身を確認すること）。

<sub>出典: [`docs/guides/install.md`](guides/install.md)</sub>

---

## はじめての Media Agent

インストール済みであることを前提に、Stage 0 でできることを一通り動かす。**外部サービスへは接続しない。**

### 1. プロジェクトを初期化する

```sh
mkdir -p ~/my-project && cd ~/my-project
media-agent init
```

```
created  .media-agent/config.yaml
created  .media-agent/strategy.md
created  .media-agent/rules.md
created  .media-agent/agents/.gitkeep
created  .media-agent/memory/.gitkeep
created  .media-agent/data/
created  .media-agent/logs/
created  .media-agent/.gitignore
created  .media-agent/data/media-agent.db
Media Agent を初期化しました: /home/you/my-project
```

### 2. 健全性を確認する

```sh
media-agent doctor
```

15 項目の検査結果と `結果: 14 ok / 0 warn / 1 skipped / 0 fail` が出れば正常。
`.env` が無いことは異常ではない（`security.env_not_tracked` が `[skipped]`）。

### 3. 現在の状態を見る

```sh
media-agent status
```

```
project      : my-project
config       : version N / platform x / posts_per_day 3
automation   : require_approval=false  post=auto reply=approval repost=approval like=disabled
database     : .media-agent/data/media-agent.db (schema N)
agents       : 2 registered — echo, fail
tasks        : total 0 — pending 0 / running 0 / completed 0 / failed 0 / cancelled 0
recent tasks :
  (タスクはありません)
```

`version N` と `(schema N)` の `N` には数字が入る。**版数は実装の更新に伴って上がるため、
本書では数字を伏せてある。** 現在の数字は
[プロジェクトディレクトリ `.media-agent/`](features/project-directory.md) にある。

### 4. Agent を実行する

登録されている Agent を見る。

```sh
media-agent agent list
```

```
NAME  VERSION  DESCRIPTION
echo  1        入力をそのまま返す検証用の組み込み Agent
fail  1        常に失敗する検証用の組み込み Agent
```

`echo` を実行する。**入力をそのまま返すだけの Agent であり、AI も外部サービスも呼ばない。**

```sh
media-agent run --input '{"note":"hello media agent"}'
```

```
Media Agent run — /home/you/my-project
agent   : echo
task    : 02a308e5-e475-4e4b-b775-ba258753a0a7
status  : completed
output  : {"note":"hello media agent"}
```

### 5. 記録を確認する

```sh
media-agent status
media-agent task list
```

`status` の `tasks` が増え、`task list` に実行済みの Task が並ぶ。

判断の記録は監査記録として残る。

```sh
cat .media-agent/logs/audit.jsonl
```

1 行 1 レコードの JSON である。**設定で消せない記録である。**

```
{"action": null, "agent": "echo", "agent_version": 1, "decision": "echo",
 "decision_id": "268242e0-...", "error": null, "input": {"note": "hello media agent"},
 "kind": "agent_run", "reason": "組み込みの検証用 Agent のため、入力をそのまま返した",
 "result": {"note": "hello media agent"}, "schema_version": N,
 "task": "1d4e14ad-...", "timestamp": "2026-08-25T04:48:32.175319Z"}
```

（実際は 1 行だが、ここでは読みやすさのために折り返している。UUID と時刻は実行のたびに変わる。）

`schema_version` は監査記録の形式版数で、ここでも数字を伏せてある。
`agent_version` は**実行した Agent 自身の版数**で（`media-agent agent list` の `VERSION` 列と同じ値）、
記録の形式版数とは別物である。

人が動作を追うための運用ログは別のファイルにある。

```sh
tail .media-agent/logs/media-agent.log
```

```
2026-08-24T23:42:43.238370Z INFO     media_agent.cli agent=echo task=c4b9eb04-... started
2026-08-24T23:42:43.240740Z INFO     media_agent.cli agent=echo task=c4b9eb04-... completed elapsed=0.002s
```

### 6. 設定を変える

`.media-agent/config.yaml` を編集し、`media-agent doctor` で検証する。
壊れていれば `[fail]` の行が出て終了コード 5 になる。

```sh
media-agent doctor --json | head
```

`--json` は `doctor` / `status` / `run` / `agent list` / `task list` で使える。

### ここから先

- 何が動いて何が動かないか → 「Stage 0 でできること・できないこと」
- コマンドとオプションの一覧 → 「CLI リファレンス」
- `.media-agent/` の中身 → 「プロジェクトディレクトリ `.media-agent/`」

<sub>出典: [`docs/guides/quickstart.md`](guides/quickstart.md)</sub>

---

## CLI リファレンス

### 実行の経路

| 書き方 | 前提 |
| --- | --- |
| `media-agent ...` | パッケージをインストールした環境（`pip install` 済み） |
| `python -m media_agent ...` | 同上。コンソールスクリプトへパスが通っていない場合に使える |

どちらも同じ実装を呼ぶ。

### 出力例の読み方

本書の出力例は実際に実行した出力である。ただし、環境や更新で変わる値は次のように読む。

| 例に出てくる値 | 読み方 |
| --- | --- |
| `/path/to/my-project` | 実際のプロジェクトのディレクトリに読み替える |
| UUID・時刻 | 実行のたびに変わる |
| **`N`（版数）** | **実装の更新に伴って上がるため、数字を伏せてある** |

**本書は版数の数字を書かない。** 版数が上がるたびに文書を直す構造は、必ず実物との食い違いを生む。
現在の数字が要る場合は [プロジェクトディレクトリ `.media-agent/`](features/project-directory.md) を見る。

### グローバルオプション

コマンド名の**前**に置く（例: `media-agent -C ~/my-project doctor`）。

| オプション | 既定 | 意味 |
| --- | --- | --- |
| `-C, --project-dir PATH` | カレントディレクトリ | 対象プロジェクトのディレクトリ。環境変数 `MEDIA_AGENT_PROJECT_DIR` でも指定できる（`-C` の方が強い） |
| `-v, --verbose` | off | 運用ログを詳細レベルで標準エラーへ出す |
| `-q, --quiet` | off | エラー以外の出力を抑制する |
| `--json` | off | 機械可読な JSON で出力する |
| `--version` | — | バージョンを表示して終了する |
| `--help` | — | ヘルプを表示して終了する |

`-C` を指定しない場合、カレントディレクトリから**上位へ `.media-agent/` を探索する**（Git と同じ挙動）。
プロジェクトのサブディレクトリからでもコマンドを実行できる。
ただし `init` だけは探索せず、**対象ディレクトリそのもの**に作る。

### コマンド一覧

| コマンド | 状態 | 何をするか |
| --- | --- | --- |
| `init` | 実装済み | 現在のプロジェクトに Media Agent を導入する（`.media-agent/` を生成） |
| `doctor` | 実装済み | 設定・構造・依存関係を検証する |
| `status` | 実装済み | 現在の Agent / Task の状態を表示する |
| `run` | 実装済み | Agent を実行し、Task として記録する |
| `agent list` | 実装済み | 登録された Agent を一覧する |
| `task list` | 実装済み | 記録された Task を一覧する |
| `setup` | 未実装（Stage 3） | 終了コード 10 で終わる |
| `post` | 未実装（Stage 3） | 終了コード 10 で終わる |
| `research` | 未実装（Stage 2） | 終了コード 10 で終わる |
| `analyze` | 未実装（Stage 5） | 終了コード 10 で終わる |

---

### `media-agent init`

導入先のプロジェクトへ `.media-agent/` を作る。既に存在する場合、既存ファイルは上書きしない（`--force` で雛形を作り直せる）。

| オプション | 意味 |
| --- | --- |
| `--force` | テンプレート由来の4ファイル（`config.yaml` / `strategy.md` / `rules.md` / `.gitignore`）を上書きする |

```
$ media-agent init
created  .media-agent/config.yaml
created  .media-agent/strategy.md
created  .media-agent/rules.md
created  .media-agent/agents/.gitkeep
created  .media-agent/memory/.gitkeep
created  .media-agent/data/
created  .media-agent/logs/
created  .media-agent/.gitignore
created  .media-agent/data/media-agent.db
Media Agent を初期化しました: /path/to/my-project
```

終了コード 0。2回目以降の実行では、既に在るものが `created` ではなく `skipped` と表示される。
**同じディレクトリで2回目を実行しても、記録済みの Task や DB は消えない。**

### `media-agent doctor`

プロジェクトが正しく初期化され、設定が壊れていないかを 15 項目で検査する。
各行の左にある識別子（`structure.files` など）は**安定した ID** であり、表示文言が変わっても ID は変わらない。

```
$ media-agent doctor
Media Agent doctor — /path/to/my-project
[ok]      structure.files           config.yaml / strategy.md / rules.md がそろっています
[ok]      structure.dirs            agents / memory / data / logs がそろっています
[ok]      config.syntax             config.yaml を YAML として読めます
[ok]      config.schema             設定はスキーマを満たしています
[ok]      config.version            config 版数 N
[ok]      config.consistency        content.posts_per_day (3) <= actions.post.max_per_day (3)
[ok]      db.file                   media-agent.db を SQLite として開けます
[ok]      db.schema                 スキーマ版数 N / 6 テーブルがそろっています
[ok]      db.foreign_keys           外部キー制約が有効です
[ok]      logs.writable             .media-agent/logs へ書き込めます
[ok]      security.gitignore        data/, logs/, .env が除外されています
[skipped] security.env_not_tracked  .env はありません（Stage 0 では認証情報を使いません）
[ok]      agents.registry           2 件の Agent が登録されています: echo, fail
[ok]      policy.config             4 件の Action を判定できます: post=allow reply=require_approval repost=require_approval like=deny
[ok]      runtime.python            Python 3.11
結果: 14 ok / 0 warn / 1 skipped / 0 fail
```

| 表示 | 意味 |
| --- | --- |
| `[ok]` | 合格 |
| `[warn]` | 動作はするが、確認した方がよい |
| `[skipped]` | 検査を実行しなかった。**合格とは区別する**（例: `.env` が無い） |
| `[fail]` | 不合格。1 件でもあれば終了コード 5 |

`fail` が 0 件なら終了コード 0。`--json` を付けると `project_root` / `overall` / `checks[]` を持つ JSON になる。
**`doctor` はプロジェクトの中身を変更しない**（ログも DB の追加ファイルも作らない）。

### `media-agent status`

プロジェクト名・設定の要約・DB・登録 Agent・Task の集計を表示する。

```
$ media-agent status
Media Agent status — /path/to/my-project
project      : demo
config       : version N / platform x / posts_per_day 3
automation   : require_approval=false  post=auto reply=approval repost=approval like=disabled
database     : .media-agent/data/media-agent.db (schema N)
agents       : 2 registered — echo, fail
tasks        : total 1 — pending 0 / running 0 / completed 1 / failed 0 / cancelled 0
recent tasks :
  2026-08-24T23:42:43.237954Z  completed  echo  c4b9eb04-109a-4fba-b249-7f8546fd45a5
```

Task が 1 件も無い場合、`recent tasks` は `(タスクはありません)` になる。
`--json` を付けると `project_name` / `config` / `database` / `agents` / `tasks` / `recent_tasks` を持つ JSON になる。

### `media-agent run`

Agent を 1 つ実行し、その実行を Task として DB へ記録する。
**Stage 0 の `run` は外部へ何も送らない。** 実行できるのは検証用の組み込み Agent だけである。

| オプション | 既定 | 意味 |
| --- | --- | --- |
| `--agent NAME` | `echo` | 実行する Agent 名 |
| `--input JSON` | `{"message":"hello"}` | Agent へ渡す入力（JSON 文字列） |
| `--json` | off | 実行結果を JSON で出力する |

```
$ media-agent run
Media Agent run — /path/to/my-project
agent   : echo
task    : c4b9eb04-109a-4fba-b249-7f8546fd45a5
status  : completed
output  : {"message":"hello"}

$ media-agent run --input '{"note":"hello media agent"}'
Media Agent run — /path/to/my-project
agent   : echo
task    : 02a308e5-e475-4e4b-b775-ba258753a0a7
status  : completed
output  : {"note":"hello media agent"}
```

`fail` Agent は常に失敗する。**Agent の失敗が正しく記録されることを確かめるための Agent である。**
失敗しても Task は `failed` として記録され、`running` のまま残らない。

```
$ media-agent run --agent fail
（標準エラーへ ERROR ログとトレースバックが出る）
Media Agent run — /path/to/my-project
agent   : fail
task    : 49497d5e-7cbc-4ae5-8bc7-d92fb4fffa08
status  : failed
error   : AgentFailedForVerificationError: 検証用 Agent 'fail' は常に失敗します
Error: Agent の実行が失敗しました (task=49497d5e-7cbc-4ae5-8bc7-d92fb4fffa08)
  - AgentFailedForVerificationError: 検証用 Agent 'fail' は常に失敗します
Hint: media-agent task list で記録された Task を確認できます
```

終了コード 1。

### `media-agent agent list`

登録された Agent を一覧する。Stage 0 では組み込みの 2 種だけが登録される。

```
$ media-agent agent list
NAME  VERSION  DESCRIPTION
echo  1        入力をそのまま返す検証用の組み込み Agent
fail  1        常に失敗する検証用の組み込み Agent
```

### `media-agent task list`

DB に記録された Task を一覧する。

| オプション | 意味 |
| --- | --- |
| `--status STATUS` | この状態の Task だけを表示する（`pending` / `running` / `completed` / `failed` / `cancelled`） |
| `--json` | 機械可読な JSON で出力する |

```
$ media-agent task list
TASK_ID                               AGENT  TYPE       STATUS     CREATED_AT                   COMPLETED_AT
c4b9eb04-109a-4fba-b249-7f8546fd45a5  echo   agent_run  completed  2026-08-24T23:42:43.237954Z  2026-08-24T23:42:43.238663Z
```

### 終了コード

**「非ゼロなら何でもよい」という扱いをしない。** 異常の種類ごとに値が決まっている。

| 終了コード | 意味 |
| --- | --- |
| 0 | 成功 |
| 1 | 想定内の実行時エラー（Agent の実行失敗など） |
| 2 | CLI の使い方の誤り（存在しないコマンド、不正なオプション） |
| 3 | プロジェクトが未初期化（`.media-agent/` が見つからない） |
| 4 | 設定エラー（`config.yaml` の構文・必須項目欠落・型不一致） |
| 5 | `doctor` の検査に不合格（`fail` が 1 件以上） |
| 6 | Policy により拒否された |
| 10 | Stage 0 では未実装のコマンド（`setup` / `post` / `research` / `analyze`） |
| 70 | 想定外の内部エラー（`--verbose` を付けるとトレースを表示する） |

エラーメッセージは標準エラーへ、通常の出力は標準出力へ出る。

```
$ media-agent status            # .media-agent/ が無いディレクトリで
Error: Media Agent が初期化されていません: /path/to/empty
Hint: media-agent init を実行してプロジェクトを初期化してください
$ echo $?
3
```

<sub>出典: [`docs/features/cli.md`](features/cli.md)</sub>

---

## プロジェクトディレクトリ `.media-agent/`

`media-agent init` は、導入先のプロジェクトへ次の構造を作る。
**Media Agent 本体のリポジトリではなく、Media Agent を導入した側のディレクトリに作られる。**

```
my-project/
├── .media-agent/
│   ├── config.yaml        プロジェクト設定
│   ├── strategy.md        メディア戦略（自然言語で書く）
│   ├── rules.md           禁止事項・ブランドルール・投稿ルール
│   ├── .gitignore         data/ logs/ .env を追跡対象から外す
│   ├── agents/            Custom Agent の置き場所（Stage 0 では読み込まない）
│   ├── memory/            Memory の置き場所（Stage 0 では使わない）
│   ├── data/
│   │   └── media-agent.db SQLite。Task・判断・投稿等の記録
│   └── logs/
│       ├── media-agent.log  運用ログ（人が動作を追うため）
│       └── audit.jsonl      監査記録（AI の判断を追跡するため）
└── （元からあるプロジェクトのファイル）
```

`data/` と `logs/` は `init` 時点では空で、コマンドを実行すると中身が作られる。

### Git で追跡するもの・しないもの

`.media-agent/.gitignore` が次を除外する。

| 追跡する | 追跡しない |
| --- | --- |
| `config.yaml` / `strategy.md` / `rules.md` | `data/`（DB）、`logs/`（ログ・監査記録）、`.env` / `.env.*` |

**`config.yaml` に認証情報を書かないこと。** 追跡対象であり、リポジトリへ入る。

### `config.yaml`

`init` が作る初期値は次のとおり。`{{PROJECT_NAME}}` にはディレクトリ名が入る。

```yaml
version: 1

project:
  name: "my-project"
  description: ""

media:
  primary_platform: x        # Stage 0 では x のみ

content:
  posts_per_day: 3           # 目標値。上限は actions.post.max_per_day

automation:
  require_approval: false    # true にすると、すべての Action が承認必須になる

actions:
  post:
    mode: auto               # auto / approval / disabled
    max_per_day: 3
  reply:
    mode: approval
  repost:
    mode: approval
  like:
    mode: disabled

limits:
  max_actions_per_hour: 10
  forbidden_topics: []
  forbidden_users: []

logging:
  level: info                # debug / info / warning / error
```

| キー | 意味 |
| --- | --- |
| `version` | 設定ファイルの構造版数。**パッケージの版数とも DB のスキーマ版数とも独立している** |
| `automation.require_approval` | `true` にすると、`actions` の設定にかかわらず全 Action が承認必須になる |
| `actions.<name>.mode` | `auto`（自動実行を許可）/ `approval`（人の承認が要る）/ `disabled`（禁止） |
| `actions.<name>.max_per_day` | その Action の 1 日あたりの上限。判定は「実行時刻から 24 時間さかのぼる窓」で行う（暦日ではない） |
| `limits.max_actions_per_hour` | 全 Action 合計の 1 時間あたり上限 |
| `logging.level` | 運用ログのレベル |

**Stage 0 には Action の実行先が無い。** `actions` / `limits` は Policy 判定の入力として読まれ、判定結果が
監査記録へ残るところまでが動く。投稿そのものは行われない。

設定を書き換えたら `media-agent doctor` で検証できる。壊れていれば `config.syntax` / `config.schema` /
`config.version` / `config.consistency` のいずれかが `[fail]` になり、`doctor` は終了コード 5、
他のコマンドは終了コード 4 で止まる。

### 運用ログと監査記録は別物

**「ログ」と一括りにしない。** 2 つは目的も保証も違う。

| | 運用ログ | 監査記録 |
| --- | --- | --- |
| ファイル | `logs/media-agent.log` | `logs/audit.jsonl` と DB の `decisions` テーブル |
| 目的 | 人が動作を追う | AI の判断を後から検証する |
| 設定の影響 | `logging.level` で量が変わる | **設定で消せない** |
| 形式 | 人が読むテキスト | 1 行 1 レコードの JSON（追記のみ） |

どちらにも**秘密値は出力しない。** 入力に含まれる `api_key` のような値はマスクされる。

監査記録の各行は、その行の形式版数を `schema_version` として持つ（現在 **2**）。
**DB のスキーマ版数とも `config.yaml` の `version` とも独立している。**
DB のスキーマ版数と同じく、数字を書いているのはここだけで、他の文書の出力例では `N` と伏せてある。

### DB

`data/media-agent.db` は SQLite で、Stage 0 のスキーマ版数は **2**、テーブルは 6 つ
（`projects` / `sources` / `posts` / `performances` / `tasks` / `decisions`）。
Stage 0 で実際に書き込まれるのは `projects`（プロジェクト 1 行）・`tasks`・`decisions` の 3 つである。
`sources` / `posts` / `performances` は Stage 1 以降のための枠であり、Stage 0 では空のままになる。

**利用者向け文書で DB のスキーマ版数を数字で書いているのは、この 1 か所だけである。**
版数は実装の更新に伴って上がるため、他の文書の出力例では `N` と伏せてある
（数字を各所へ書くと、版数が上がるたびに全文書が実物と食い違う）。

<sub>出典: [`docs/features/project-directory.md`](features/project-directory.md)</sub>

---

## Stage 0 動作確認手順書

**この文書は、Media Agent の Stage 0（Media Agent Core）が手元で動くことを、自分で確かめるための手順書である。**
上から順にコピーして実行すれば終わる。所要時間は 5〜10 分（依存パッケージの取得時間を除く）。

### 確認する範囲

Stage 0 の検証条件は次の 1 行である。

> `media-agent init` → Project 生成 → `media-agent doctor` → `media-agent status` が正常動作すること。

本書は上記に加えて、Agent の実行・記録、未実装コマンドの扱い、外部接続が無いことまでを確認する。

### 確認しないこと（Stage 0 に無いもの）

- X（旧 Twitter）への投稿・返信 — **Stage 0 には投稿機能そのものが存在しない**
- ニュース・RSS からの情報収集、AI によるコンテンツ生成 — Stage 1 / Stage 2

### 認証情報は不要である

**この手順書のどこでも、API キー・アクセストークン・パスワードを入力しない。**
Media Agent は Stage 0 で外部サービスへ一切接続しないため、認証情報を置く場所も、要求する箇所も無い。
**もし手順の途中で認証情報の入力を求められたら、それは異常である。** 最後の「期待どおりにならなかった場合」を参照。

---

### 前提

| 項目 | 条件 | 確認方法 |
| --- | --- | --- |
| OS | Linux / macOS（`sh` 系のシェル） | — |
| Python | **3.11 以上** | `python3 --version` |
| Git | 導入済み | `git --version` |
| ネットワーク | 依存パッケージの取得にのみ必要 | — |
| ディスク | 数十 MB 程度 | — |

```sh
python3 --version
git --version
```

期待される出力（版数は環境により異なる。**Python が 3.11 以上であること**だけを見る）:

```
Python 3.11.15
git version 2.43.0
```

---

### 手順 1 — リポジトリを取得する

作業用の一時ディレクトリで行う。既存の環境を汚さない。

```sh
mkdir -p ~/media-agent-check && cd ~/media-agent-check
git clone https://github.com/umiji/media-agent.git
cd media-agent
```

確認するブランチが `main` でない場合は、続けて切り替える。

```sh
git checkout claude/session-resume-mdqrmg
git log --oneline -1
```

**確認すること**: `git log` が確認対象のコミットを指していること。終了コードは 0。

### 手順 2 — 仮想環境を作り、インストールする

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

**確認すること**: エラーなく終わること（最後に `Successfully installed ...` が出る）。終了コードは 0。

以降のコマンドを短く書くため、この端末で仮想環境へパスを通す。

```sh
export PATH="$PWD/.venv/bin:$PATH"
```

### 手順 3 — インストールされたことを確認する

```sh
media-agent --version
echo "EXIT=$?"
```

期待される出力:

```
media-agent, version 0.1.0
EXIT=0
```

続けてコマンド一覧を見る。

```sh
media-agent --help
```

期待される出力（抜粋）:

```
Commands:
  agent     登録された Agent を確認する。
  analyze   （Stage 5 で実装予定。Stage 0 では未実装）
  doctor    設定・構造・依存関係を検証する。
  init      現在のプロジェクトに Media Agent を導入する。
  post      （Stage 3 で実装予定。Stage 0 では未実装）
  research  （Stage 2 で実装予定。Stage 0 では未実装）
  run       Media Agent の Workflow を実行する。
  setup     （Stage 3 で実装予定。Stage 0 では未実装）
  status    現在の Agent / Task の状態を確認する。
  task      記録された Task を確認する。
```

**確認すること**: 未実装のコマンドが「Stage 0 では未実装」と明示されていること。

### 手順 4 — 確認用のプロジェクトを作る

**Media Agent 本体のリポジトリの中ではなく、別のディレクトリで実行する。**
Media Agent は「導入先のプロジェクト」で使う道具だからである。

```sh
mkdir -p ~/media-agent-check/demo-project && cd ~/media-agent-check/demo-project
pwd
```

### 手順 5 — `media-agent init`（Project 生成）

```sh
media-agent init
echo "EXIT=$?"
```

期待される出力:

```
created  .media-agent/config.yaml
created  .media-agent/strategy.md
created  .media-agent/rules.md
created  .media-agent/agents/.gitkeep
created  .media-agent/memory/.gitkeep
created  .media-agent/data/
created  .media-agent/logs/
created  .media-agent/.gitignore
created  .media-agent/data/media-agent.db
Media Agent を初期化しました: /home/you/media-agent-check/demo-project
EXIT=0
```

生成されたものを確認する。

```sh
find .media-agent -type f | sort
```

期待される出力:

```
.media-agent/.gitignore
.media-agent/agents/.gitkeep
.media-agent/config.yaml
.media-agent/data/media-agent.db
.media-agent/memory/.gitkeep
.media-agent/rules.md
.media-agent/strategy.md
```

**確認すること**: 設定・戦略・ルールの 3 ファイルと DB が作られていること。
**`.env` や認証情報のファイルが作られていないこと。**

設定の中身も見ておく。

```sh
cat .media-agent/config.yaml
```

**確認すること**: `project.name` が `demo-project`（ディレクトリ名）になっていること。
**API キーやトークンを書く欄がどこにも無いこと。**

### 手順 6 — `media-agent doctor`（検証）

```sh
media-agent doctor
echo "EXIT=$?"
```

期待される出力:

```
Media Agent doctor — /home/you/media-agent-check/demo-project
[ok]      structure.files           config.yaml / strategy.md / rules.md がそろっています
[ok]      structure.dirs            agents / memory / data / logs がそろっています
[ok]      config.syntax             config.yaml を YAML として読めます
[ok]      config.schema             設定はスキーマを満たしています
[ok]      config.version            config 版数 N
[ok]      config.consistency        content.posts_per_day (3) <= actions.post.max_per_day (3)
[ok]      db.file                   media-agent.db を SQLite として開けます
[ok]      db.schema                 スキーマ版数 N / 6 テーブルがそろっています
[ok]      db.foreign_keys           外部キー制約が有効です
[ok]      logs.writable             .media-agent/logs へ書き込めます
[ok]      security.gitignore        data/, logs/, .env が除外されています
[skipped] security.env_not_tracked  .env はありません（Stage 0 では認証情報を使いません）
[ok]      agents.registry           2 件の Agent が登録されています: echo, fail
[ok]      policy.config             4 件の Action を判定できます: post=allow reply=require_approval repost=require_approval like=deny
[ok]      runtime.python            Python 3.11
結果: 14 ok / 0 warn / 1 skipped / 0 fail
EXIT=0
```

**確認すること**:

- 最終行が `0 fail` であること
- **`security.env_not_tracked` が `[skipped]` であること。** 認証情報が無いことを異常として扱っていない
- `runtime.python` の版数は環境により `3.12` / `3.13` になることがある。それでよい
- **`config 版数` と `スキーマ版数` の `N` には数字が入る。** 本書は版数の数字を書かない
  （更新に伴って上がるため）。**見るのは数字ではなく、その行が `[ok]` であることである**

### 手順 7 — `media-agent status`（状態表示）

```sh
media-agent status
echo "EXIT=$?"
```

期待される出力:

```
Media Agent status — /home/you/media-agent-check/demo-project
project      : demo-project
config       : version N / platform x / posts_per_day 3
automation   : require_approval=false  post=auto reply=approval repost=approval like=disabled
database     : .media-agent/data/media-agent.db (schema N)
agents       : 2 registered — echo, fail
tasks        : total 0 — pending 0 / running 0 / completed 0 / failed 0 / cancelled 0
recent tasks :
  (タスクはありません)
EXIT=0
```

**確認すること**: `project` が手順 4 で作ったディレクトリ名になっていること。終了コードが 0 であること。
`version N` / `(schema N)` の `N` は手順 6 と同じく版数で、**数字は確認対象ではない**。

**ここまでで Stage 0 の検証条件（`init` → Project 生成 → `doctor` → `status`）を満たしている。**
以降は、Core が実際に動いていることの追加確認である。

### 手順 8 — Agent を実行し、記録されることを確認する

登録されている Agent を見る。

```sh
media-agent agent list
echo "EXIT=$?"
```

```
NAME  VERSION  DESCRIPTION
echo  1        入力をそのまま返す検証用の組み込み Agent
fail  1        常に失敗する検証用の組み込み Agent
EXIT=0
```

**この 2 つは検証用の Agent である。** AI も外部サービスも呼ばない。

実行する。

```sh
media-agent run
echo "EXIT=$?"
```

期待される出力（`task` の UUID は毎回変わる）:

```
Media Agent run — /home/you/media-agent-check/demo-project
agent   : echo
task    : c4b9eb04-109a-4fba-b249-7f8546fd45a5
status  : completed
output  : {"message":"hello"}
EXIT=0
```

記録されたことを確認する。

```sh
media-agent status
media-agent task list
```

**確認すること**: `tasks` が `total 1 — ... completed 1 ...` に変わり、`task list` に 1 行出ること。

判断の記録が残っていることを確認する。

```sh
cat .media-agent/logs/audit.jsonl
```

**確認すること**: `agent` / `input` / `result` / `decision` / `timestamp` などを含む JSON が 1 行あること。

### 手順 9 — 失敗が失敗として記録されることを確認する

```sh
media-agent run --agent fail
echo "EXIT=$?"
```

**標準エラーへ ERROR ログとトレースバックが出る。これは想定どおりである**（`fail` は常に失敗する検証用 Agent）。

```
Media Agent run — /home/you/media-agent-check/demo-project
agent   : fail
task    : 49497d5e-7cbc-4ae5-8bc7-d92fb4fffa08
status  : failed
error   : AgentFailedForVerificationError: 検証用 Agent 'fail' は常に失敗します
Error: Agent の実行が失敗しました (task=49497d5e-7cbc-4ae5-8bc7-d92fb4fffa08)
  - AgentFailedForVerificationError: 検証用 Agent 'fail' は常に失敗します
Hint: media-agent task list で記録された Task を確認できます
EXIT=1
```

```sh
media-agent task list --status failed
media-agent status
```

**確認すること**: 失敗した Task が `failed` として残り、`running` のまま残る Task が無いこと。
続けて他のコマンドが問題なく動くこと。

### 手順 10 — 未実装のコマンドが「未実装」として振る舞うことを確認する

```sh
media-agent post
echo "EXIT=$?"
```

期待される出力:

```
Error: `media-agent post` は Stage 0 では未実装です（Stage 3 で実装予定）
  - X Connector が Stage 3 で入る
EXIT=10
```

`setup` / `research` / `analyze` も同様に終了コード 10 で終わる。

```sh
for c in setup research analyze; do media-agent "$c"; echo "$c EXIT=$?"; done
```

**確認すること**: **黙って成功しないこと。** 未実装のコマンドが終了コード 0 を返すと、
スクリプトや CI から呼んだときに「実行された」と誤認される。

### 手順 11 — 未初期化のディレクトリで正しく止まることを確認する

```sh
mkdir -p ~/media-agent-check/empty && cd ~/media-agent-check/empty
media-agent status
echo "EXIT=$?"
```

期待される出力:

```
Error: Media Agent が初期化されていません: /home/you/media-agent-check/empty
Hint: media-agent init を実行してプロジェクトを初期化してください
EXIT=3
```

**確認すること**: 何をすればよいかが示されていること。終了コードが 10 でも 1 でもなく **3** であること。

### 手順 12 — 外部へ接続していないことを確認する（任意）

依存パッケージに HTTP クライアントも SNS の SDK も入っていないことを確認する。

```sh
cd ~/media-agent-check/media-agent
.venv/bin/python -m pip list --format=freeze | grep -Ei 'requests|httpx|aiohttp|tweepy|openai|anthropic' ; echo "MATCH=$?"
```

期待される出力:

```
MATCH=1
```

`MATCH=1` は「1 件も一致しなかった」という意味である（`grep` は一致が無いと 1 を返す）。

ソースが認証情報を読む箇所が無いことも確認できる。

```sh
grep -rn 'getenv\|environ' src/ ; echo "MATCH=$?"
```

期待される出力:

```
MATCH=1
```

### 手順 13 — テストが通ることを確認する（任意）

```sh
cd ~/media-agent-check/media-agent
PATH="$PWD/.venv/bin:$PATH" .venv/bin/pytest -q
echo "EXIT=$?"
```

**確認すること**: `... passed` で終わり、`failed` が 0 件、`EXIT=0` であること。

```sh
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy src
echo "EXIT=$?"
```

**確認すること**: `All checks passed!` / `... already formatted` / `Success: no issues found ...` が出て `EXIT=0`。

### 手順 14 — 後片付け

確認用に作ったものはすべて 1 か所にある。消せば元に戻る。

```sh
cd ~
rm -rf ~/media-agent-check
```

Media Agent 自身は `~/media-agent-check` の外へ何も書き込まない（仮想環境もリポジトリの中にある）。
**残るのは `pip` のダウンロードキャッシュ（`~/.cache/pip`）だけである。** 気になる場合は
`.venv/bin/python -m pip cache purge` で消せる。

---

### 確認結果のチェックリスト

| # | 確認項目 | 期待 | 結果 |
| --- | --- | --- | --- |
| 1 | `media-agent --version` が動く | `0.1.0` / 終了コード 0 | |
| 2 | `media-agent init` が `.media-agent/` を作る | 終了コード 0 | |
| 3 | 設定・戦略・ルールと DB が生成される | 7 ファイル | |
| 4 | `media-agent doctor` が通る | `0 fail` / 終了コード 0 | |
| 5 | 認証情報の不在が異常扱いされない | `security.env_not_tracked` が `[skipped]` | |
| 6 | `media-agent status` が状態を表示する | 終了コード 0 | |
| 7 | `media-agent run` が Agent を実行し記録する | 終了コード 0 / Task が 1 件増える | |
| 8 | 失敗が `failed` として記録される | 終了コード 1 | |
| 9 | 未実装コマンドが黙って成功しない | 終了コード 10 | |
| 10 | 未初期化で正しく止まる | 終了コード 3 | |
| 11 | 外部接続の依存が無い | 一致 0 件 | |
| 12 | テスト・リント・型検査が通る | 終了コード 0 | |

**#2・#4・#6 が Stage 0 の検証条件そのものである。**

---

### 期待どおりにならなかった場合

**手順書を書き換えて辻褄を合わせないこと。** 期待と違ったなら、手順書か実装のどちらかが誤っている。

#### 1. 次の 4 つを控える

| 控えるもの | 取り方 |
| --- | --- |
| 実行したコマンド | 手順番号でよい |
| 実際の出力（全文） | 端末からコピーする |
| 実際の終了コード | 直後に `echo "EXIT=$?"` |
| 環境 | `python3 --version` と `uname -a`、`git log --oneline -1` |

#### 2. 追加で取れると原因が早く分かるもの

```sh
media-agent doctor --json
media-agent -v status                      # 詳細な運用ログが標準エラーへ出る
cat .media-agent/logs/media-agent.log
```

**`audit.jsonl` と `media-agent.log` に秘密値は出力されない設計だが、共有する前に中身を一読すること。**

#### 3. 渡す先

開発セッション（オーケストレーター）へ、上記を添えて伝える。
不具合として扱うか、手順書の誤りとして扱うかは、そこで切り分ける。
GitHub の Issue へ登録する場合も同じ内容を書く。

#### よくある食い違い

| 症状 | 原因として考えられること |
| --- | --- |
| `media-agent: command not found` | 手順 2 の `export PATH=...` を実行していない。`.venv/bin/media-agent` と書けば動く |
| `doctor` / `status` が終了コード 3 | `.media-agent/` の無いディレクトリで実行している。手順 4 のディレクトリへ移動する |
| 終了コード 4 が出る | `config.yaml` を編集して壊した。`media-agent doctor` が該当キーを示す |
| `run --agent fail` でトレースバックが出る | **想定どおり。** `fail` は失敗を確認するための Agent である |
| `runtime.python` の版数が違う | 3.11 以上なら問題ない |

<sub>出典: [`docs/guides/verification-stage0.md`](guides/verification-stage0.md)</sub>

---

## 開発者向け

### 開発環境

```sh
git clone https://github.com/umiji/media-agent.git
cd media-agent
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

### テスト・リント・型検査

| 目的 | コマンド |
| --- | --- |
| 全テスト | `.venv/bin/pytest` |
| 単体テストだけ | `.venv/bin/pytest tests/unit` |
| 受け入れテストだけ | `.venv/bin/pytest tests/acceptance` |
| リント | `.venv/bin/ruff check .` |
| 整形の検査 | `.venv/bin/ruff format --check .` |
| 整形の適用 | `.venv/bin/ruff format .` |
| 型検査 | `.venv/bin/mypy src` |

すべて終了コード 0 で通ることが、このリポジトリの品質基準である。

**コンソールスクリプト（`media-agent`）の疎通を確かめるテストがあるため、
仮想環境へパスを通した状態で実行すること。**

```sh
PATH="$PWD/.venv/bin:$PATH" .venv/bin/pytest
```

カバレッジは計測するが、閾値は設けていない。閾値を満たすためのテストが書かれると、
テストが仕様の検証ではなく行数の消化になるためである。

### CI

`.github/workflows/ci.yml` が `push` と `pull_request` で走る。
Python 3.11 / 3.12 / 3.13 の 3 通りで、`ruff check` → `ruff format --check` → `mypy src` → `pytest` を実行する。
**CI は認証情報（secrets）を一切使わない。**

### ソース構成

```
src/media_agent/
├── errors.py      例外階層。各例外が自分の終了コードをクラス属性で持つ
├── cli/           CLI 層。**例外を終了コードへ変換する唯一の場所**
│   └── commands/  1 コマンド 1 モジュール
├── core/          Core 層
│   ├── config/    設定のモデルと読み込み・検証
│   ├── db/        接続・スキーマ・Repository（手書き SQL）
│   ├── runtime/   Agent インターフェース・登録簿・実行器
│   ├── task/      Task のモデルと状態遷移
│   ├── policy/    Policy Engine
│   └── observability/  運用ログと監査記録
├── project/       導入先プロジェクトの層（`.media-agent/` の解決と生成）
└── agents/builtin/ 検証用の組み込み Agent（echo / fail）
```

依存の向きは `cli → project → core` と `agents → core` の一方向に固定してある。

**`core/` は `cli/` `project/` `agents/` を import しない。**
`core/` にはプロジェクト固有の事情（`.media-agent` という文字列を含む）を持ち込まない。パスは `project/` から引数で受け取る。
この規約は grep で機械的に検査している。

### 技術スタック

| | |
| --- | --- |
| Python | >= 3.11 |
| CLI | Click |
| 設定 | PyYAML（`safe_load`）+ Pydantic v2 |
| DB | 標準ライブラリの `sqlite3` + 手書き SQL |
| テスト | pytest |
| lint / format | Ruff |
| 型 | mypy（`src` のみ） |
| ビルド | hatchling（src レイアウト） |

実行時の依存は `click` / `PyYAML` / `pydantic` の 3 つだけである。
**HTTP クライアントも LLM の SDK も入っていない。**

### バージョン

`src/media_agent/__init__.py` の `__version__` が唯一の真実で、`pyproject.toml` はそこから読む。

**版数は 3 つあり、互いに独立している。混同しないこと。**

| 版数 | どこ | 何の版数か |
| --- | --- | --- |
| パッケージ版数 | `__version__` | Media Agent 本体 |
| 設定の構造版数 | `config.yaml` の `version` | 設定ファイルの構造 |
| DB のスキーマ版数 | SQLite の `user_version` | DB の構造 |

（監査記録の各行が持つ `schema_version` も、これらとは独立している。）

### 設計と決定の記録

**「なぜその方式にしたか」は README ではなく設計成果物にある。**

| 文書 | 内容 |
| --- | --- |
| `docs/design/stage0-architecture.md` | 方式設計。全体構成、技術選定と却下案、CLI 設計、終了コード |
| `docs/design/stage0-detail.md` | 詳細設計。Config / DB / Agent / Task / Policy / Logging・Audit |
| `docs/requirements-media-agent-v0.2.md` | 要件定義書 v0.2 |
| `docs/glossary.md` | このリポジトリで意味が決まっている語 |

<sub>出典: [`docs/guides/development.md`](guides/development.md)</sub>

---

## ドキュメント一覧

| 文書 | 内容 |
| --- | --- |
| [`docs/features/overview.md`](features/overview.md) | Media Agent とは |
| [`docs/features/stage0-scope.md`](features/stage0-scope.md) | Stage 0 でできること・できないこと |
| [`docs/guides/install.md`](guides/install.md) | インストール |
| [`docs/guides/quickstart.md`](guides/quickstart.md) | はじめての Media Agent |
| [`docs/features/cli.md`](features/cli.md) | CLI リファレンス |
| [`docs/features/project-directory.md`](features/project-directory.md) | プロジェクトディレクトリ `.media-agent/` |
| [`docs/guides/verification-stage0.md`](guides/verification-stage0.md) | Stage 0 動作確認手順書 |
| [`docs/guides/development.md`](guides/development.md) | 開発者向け |
