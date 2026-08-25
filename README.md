# Media Agent

<!-- このファイルは自動生成物です。直接編集しないでください。
     マスタ: docs/features/overview.md / docs/features/stage0-scope.md / docs/guides/install.md / docs/guides/quickstart.md / docs/guides/development.md
     生成:   python3 docs/tools/build_docs.py -->

**任意のプロジェクトへ導入して使える、AI によるメディア運用 Agent 基盤。**

> **現在の実装状況は Stage 0（Media Agent Core）です。**
> CLI・プロジェクト初期化・設定・DB・Task・Agent Runtime・Policy・ログ／監査記録までが動きます。
> **X への投稿、情報収集、AI によるコンテンツ生成はまだ実装されていません。**
> 外部サービスへ接続しないため、**API キーなどの認証情報は一切必要ありません。**

- 動作を確認したい方 → [Stage 0 動作確認手順書](docs/guides/verification-stage0.md)
- コマンドの詳細 → [CLI リファレンス](docs/features/cli.md)
- 通し読み → [ハンドブック](docs/handbook.md)

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

<sub>出典: [`docs/features/overview.md`](docs/features/overview.md)</sub>

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

<sub>出典: [`docs/features/stage0-scope.md`](docs/features/stage0-scope.md)</sub>

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

<sub>出典: [`docs/guides/install.md`](docs/guides/install.md)</sub>

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
[プロジェクトディレクトリ `.media-agent/`](docs/features/project-directory.md) にある。

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

<sub>出典: [`docs/guides/quickstart.md`](docs/guides/quickstart.md)</sub>

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

<sub>出典: [`docs/guides/development.md`](docs/guides/development.md)</sub>

---

## ドキュメント一覧

| 文書 | 内容 |
| --- | --- |
| [`docs/features/overview.md`](docs/features/overview.md) | Media Agent とは |
| [`docs/features/stage0-scope.md`](docs/features/stage0-scope.md) | Stage 0 でできること・できないこと |
| [`docs/guides/install.md`](docs/guides/install.md) | インストール |
| [`docs/guides/quickstart.md`](docs/guides/quickstart.md) | はじめての Media Agent |
| [`docs/features/cli.md`](docs/features/cli.md) | CLI リファレンス |
| [`docs/features/project-directory.md`](docs/features/project-directory.md) | プロジェクトディレクトリ `.media-agent/` |
| [`docs/guides/verification-stage0.md`](docs/guides/verification-stage0.md) | Stage 0 動作確認手順書 |
| [`docs/guides/development.md`](docs/guides/development.md) | 開発者向け |
