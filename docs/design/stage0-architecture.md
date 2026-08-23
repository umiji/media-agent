# Stage 0 方式設計 — Media Agent Core

- 出所タスク: T-001（`docs/tasks/T-001.md`）
- 作成日: 2026-08-23
- 対象: 要件定義書 v0.2（`docs/requirements-media-agent-v0.2.md`）の **Stage 0（Media Agent Core）のみ**
- 読み手: T-002（詳細設計）、T-003（受け入れテスト）、T-004〜T-007（実装）、T-008〜T-009（テスト・レビュー）
- 位置づけ: 設計成果物（組織の内側向け）。**「なぜその方式にしたか」を記録する文書**であり、利用者向けドキュメントではない

---

## 1. 対象範囲

### 1.1 この設計がカバーする範囲

要件定義書28節「最初に決定する対象」14項目のうち、次の8項目と、19節の表で S0 が「設計」となっている Custom Agent ロード方式を加えた **9項目**。

| # | 項目 | 本文書の章 |
| --- | --- | --- |
| 1 | Repository 構造 | 4章 |
| 2 | Python package 構造 | 5章 |
| 3 | CLI 設計 | 6章 |
| 4 | `.media-agent/` 構造 | 7章 |
| 5 | `.claude/` 連携構造（**設計のみ・Stage 0 では実装しない**） | 8章 |
| 12 | Test 構造 | 10章 |
| 13 | GitHub Actions | 11章 |
| 14 | Version 管理 | 12章 |
| — | Custom Agent のロード方式（**設計のみ・Stage 0 では実装しない**） | 9章 |

あわせて、要件定義書24節「未決事項」のうち Stage 0 に効く技術選定（3章）と、Stage 1 以降を足すための拡張点の位置（13章）を決める。

### 1.2 この設計がカバーしない範囲

**書かれていないことは決まっていない。** 推測で埋めず、下記の担当へ回すこと。

| 対象 | 誰が決めるか |
| --- | --- |
| Config Schema / DB Schema / Agent Interface のシグネチャ / Task Model / Policy Model / Logging・Audit の項目 | **T-002**（Stage 0 詳細設計） |
| Migration 方式の具体 | **T-002** |
| `init` / `doctor` / `status` / `run` の出力文言・検査項目の内訳 | **T-002** |
| Stage 1 以降の Agent（Content / Research / Strategy / Analytics / Engagement / Orchestrator） | 今回のゴール外 |
| X Connector / Google News / RSS / Web Connector | 今回のゴール外（Stage 2・3 以降） |
| X API の利用方式 / AI 処理の実行方式 / Memory・Similarity 検索方式 / Package 配布方式 / Agent Plugin API | 今回のゴール外（T-001 の禁止事項。決めても実装されないまま陳腐化するため） |
| Scheduler（要件定義書5.6節） | 今回のゴール外。18節 Stage 0 の実装項目にも 19節の表にも含まれない |
| 既存 CSV をそのまま永続 DB とするか Import するか（要件定義書11.2節） | **Stage 1**（16.3 参照。Stage 0 に過去投稿 Import は無い） |

---

## 2. 前提・制約

この設計は次の前提に依拠する。**前提が崩れたら、この設計は無効になる。**

| # | 前提 | 崩れたときに影響する箇所 |
| --- | --- | --- |
| P-1 | 今回のゴールは **Stage 0 のみ**（`docs/handover.md`）。Stage 1 以降は実装しない | 全体 |
| P-2 | **X への実投稿を行わず、認証情報は環境に存在しない**（PO 制約 C-1〜C-3）。よって Stage 0 に外部ネットワーク送信も認証も存在しない | 6章（`post` 等のスタブ化）、7章（`.env` を作らない）、10章（ネットワーク遮断 fixture） |
| P-3 | 要件定義書28節「Stage 0 ではまだ X API やニュース取得等を実装しない」 | 6章のコマンド切り分け |
| P-4 | 実行環境から PyPI へ到達できる（本タスクで検証済み。15.2 参照） | 3章の技術選定すべて |
| P-5 | 実行環境の既定 `python3` は 3.11.15、`sqlite3` は 3.45.1（本タスクで検証済み） | 3.1・3.4 |
| P-6 | 開発・CI・受け入れテストはすべて**単一マシン上のローカル実行**で完結する。サーバ・コンテナ・外部サービスを必要としない | 3.4（DB 方式） |
| P-7 | 実装は単一のワークツリーで**直列**に進む（`docs/handover.md` の並列実行判断） | 15章の分割案の順序 |

---

## 3. 技術選定

各項目について「採用」「却下案」「却下理由」を示す。決定ログ（`docs/tasks/T-001.md`）にも同じ結論を記録した。

### 3.1 Python の最低バージョン

**採用: Python >= 3.11**（CI の検証対象は 3.11 / 3.12 / 3.13）

理由:

- 実行環境の既定 `python3` が 3.11.15 である（P-5）。ここより上を要求すると、開発・テスト・CI のたびに別インタプリタの指定が要る
- 3.11 から `tomllib` が標準ライブラリに入る。将来 `pyproject.toml` を読む必要が出ても依存が増えない
- 例外グループ・`Self` 型など、Agent Runtime のエラー処理で使える言語機能が揃っている

| 却下案 | 却下理由 |
| --- | --- |
| >= 3.9 / 3.10 | 得るものが「古い環境で動く」だけ。Media Agent は利用者が自分の開発機に入れる CLI であり、古い Python を要求される場面が想定に無い。`tomllib` も無い |
| >= 3.12 | 実行環境の既定インタプリタ（3.11）を外す。全コマンドで `python3.12` を明示することになり、手順書と CI の両方が壊れやすくなる。3.12 固有の機能を使う予定も無い |
| >= 3.13 | 同上に加え、依存パッケージのホイール提供が最も薄いバージョンを最低要件にすることになる |

### 3.2 CLI Framework

**採用: Click（`click>=8.1,<9`）**

理由:

- サブコマンド群（要件定義書10節の10コマンド）を宣言的に構成でき、`init` / `doctor` / `status` / `run` と将来の `research` / `post` を同じ形で足せる
- `click.testing.CliRunner` により、**プロセスを起こさずに終了コードと stdout/stderr を検証できる**。受け入れテスト S-A〜S-D・S-I が終了コードとメッセージを判定する設計（6.4）と直結する
- API が安定しており、8 系の情報量が多い。上限を `<9` に固定するのは、9 系で非推奨 API の削除が予告されているため（本タスクで `click.__version__` の非推奨警告を確認済み）

| 却下案 | 却下理由 |
| --- | --- |
| Typer | 実体は Click のラッパであり、テストも終了コード制御も結局 Click 経由になる。型ヒントから引数を生成する糖衣のために層が1枚増え、エラーメッセージの制御が遠くなる。Stage 0 の利得より不透明さのコストが上回る |
| argparse（標準ライブラリ） | 依存ゼロは魅力だが、`CliRunner` 相当のテストハーネスが無い。10 コマンド分のサブパーサ組み立て・終了コード変換・出力捕捉をすべて手書きすることになり、受け入れテストが実装の写像になりやすい。なお PyYAML（3.5）が必須依存として残るため「依存ゼロ」自体は達成できない |
| Fire / docopt | 引数仕様がコード・docstring に暗黙化し、`--help` と実挙動の整合を機械的に保てない |

### 3.3 設定ファイルのパーサとスキーマ検証

**採用: パーサ = PyYAML（`PyYAML>=6.0`、`yaml.safe_load` のみ使用） / スキーマ検証 = Pydantic v2（`pydantic>=2.7,<3`）**

理由:

- 要件定義書8.2節が設定ファイルを `config.yaml` と定めている。**形式は要件で決まっており、選択の余地は無い**。パーサ側の選択肢は PyYAML と ruamel.yaml だけになる
- Pydantic v2 は「検証済みの型付きオブジェクト」を返すため、Config を辞書のまま持ち回らずに済む。既定値・必須/任意・型変換・エラーメッセージが1か所に集まり、T-002 が Config Schema を表で書けばそのままモデル定義になる
- 同じモデル機構を Task / Policy / Agent の入出力にも使えるため、Stage 0 の範囲でモデル表現が1種類に揃う
- `yaml.load` は使わない（任意オブジェクト構築を許すため）。**`yaml.safe_load` に限定する**

| 却下案 | 却下理由 |
| --- | --- |
| dataclasses + 手書きバリデータ | 依存は減るが、必須・既定値・型変換・エラーメッセージを項目ごとに手書きすることになる。T-002 が「検証エラー時の挙動」を定める以上、エラー表現の一貫性を人手で担保するのは割に合わない |
| jsonschema | 辞書のまま検証するため、検証後も型が付かない。スキーマ（JSON）とコード上のモデルという**真実が2つ**になる |
| ruamel.yaml | コメント保持・往復編集が強みだが、Stage 0 に設定ファイルを機械で書き戻す機能は無い（`init` はテンプレートを新規に書き出すだけ）。使わない機能のために重い依存を入れることになる |
| TOML（`tomllib`）へ変更 | 要件定義書8.2節の `config.yaml` と食い違う。要件定義書は PO の持ち物であり、設計側で形式を変えない |
| `.env` / python-dotenv | Stage 0 に認証情報を必要とする機能が存在しない（P-2）。読み込む対象が無いまま依存だけ増える。拡張点としてのみ 13章に記す |

### 3.4 DB 方式

**採用: SQLite（標準ライブラリ `sqlite3`）+ 手書き SQL の Repository 層。DB ファイルは `.media-agent/data/media-agent.db`**

理由:

- 要件定義書2.1節・5.4節が「プロジェクトごとに導入」「Memory は他プロジェクトと完全分離」を求める。**プロジェクトディレクトリ配下の単一ファイル**という形が、この分離をファイルシステムの構造そのもので実現する
- サーバプロセス・認証情報・ネットワークを一切必要としない（P-2・P-6）
- 要件定義書16節の6 Entity は、型・主キー・外部キー・インデックスを持つ素直なリレーショナル構造であり、SQLite の機能で過不足なく表現できる
- 標準ライブラリのため、依存追加ゼロで CI・利用者環境の双方で確実に動く（実行環境の SQLite は 3.45.1、P-5）

| 却下案 | 却下理由 |
| --- | --- |
| SQLAlchemy（+ Alembic） | 6テーブル・Stage 0 の CRUD に対して抽象化が過大。ORM のセッション管理という第二の状態機械が増え、Task の状態遷移（T-002）と混ざると障害の切り分けが難しくなる。**Repository 層を挟んでおけば、必要になった時点で背後だけ差し替えられる**（13章の拡張点 E-2） |
| JSON / CSV ファイルへの直書き | 検索・インデックス・同時書き込みの制御が無い。要件定義書11節の重複チェック（Stage 1）で必ず行き詰まる。要件定義書16節が Entity 単位の関連（Post ↔ Performance）を前提にしている点とも噛み合わない |
| TinyDB 等の軽量ドキュメント DB | 依存が増えるうえ、SQLite に対する優位が無い（永続化・クエリ・型のいずれも劣る） |
| PostgreSQL / MySQL | サーバと接続情報が必要になる。P-2（認証情報を置かない）・P-6（ローカル完結）と両立しない。「任意のプロジェクトに `pip install` して導入する」という要件定義書3.2節の利用像とも合わない |
| DuckDB / ベクトル DB | 要件定義書23節が「高度な Vector Database」を MVP 非対象と明記している |

補足（T-002 への申し送り）:

- Migration 方式の具体は T-002 が決める。方式設計としての制約は「**スキーマ版数を DB 自身が持ち、初期化を何度実行しても壊れないこと**」（T-005 完了条件3）。`PRAGMA user_version` を使う前提で矛盾は無い
- 接続時に `PRAGMA foreign_keys = ON` を明示すること（SQLite の既定は OFF。外部キーが黙って効かない典型的な罠）

### 3.5 テストフレームワークと実行コマンド

**採用: pytest（`pytest>=8`）+ pytest-cov。実行コマンドは `pytest`**

理由:

- `tmp_path` fixture により、`media-agent init` を毎回まっさらなディレクトリで検証できる。Stage 0 の受け入れテストは大半が「空のディレクトリに何が生成されるか」であり、この fixture が中心になる
- fixture の合成と `parametrize` により、Policy の4通り判定（S-G）や Task 状態遷移（S-F）を表で書ける
- `conftest.py` に autouse fixture を置くことで、**全テストからのネットワーク遮断を機構として強制できる**（10.4）。PO 制約 C-1・C-2 をレビューの目視ではなくテスト基盤で担保する

| 却下案 | 却下理由 |
| --- | --- |
| unittest（標準ライブラリ） | 依存は減るが、`tmp_path` 相当・パラメタライズ・autouse fixture を自前で用意することになる。ネットワーク遮断の全体適用も `setUp` の継承で回すことになり、書き忘れが検出できない |
| nose2 | 実質的に保守が止まっている |
| pytest + tox / nox | 複数環境の切り替えは CI の matrix（11章）で足りる。ローカルに第二の実行系を増やすと「どのコマンドが正か」が曖昧になる |

**カバレッジの閾値は Stage 0 では設けない**（計測はする）。却下案: `--cov-fail-under=NN` の導入 → 骨格実装の段階で数値を決める根拠が無く、閾値を満たすためのテストが書かれると受け入れテストの意味が薄れる。代わりに「新規モジュールに対応する単体テストがあること」をレビュー観点（14章 Q5）に置く。

### 3.6 リンタ・フォーマッタ・型チェック（補助的な選定）

**採用: Ruff（lint + format 兼用）+ mypy**

| 却下案 | 却下理由 |
| --- | --- |
| black + flake8 + isort | ツール3つ・設定3つになり、相互の衝突（行長・import 並び）を調整する手間が恒常的に残る。Ruff は同じ役割を1ツール・1設定（`pyproject.toml`）で満たす |
| pylint | 既定の指摘が多く、Stage 0 の骨格実装で大量の抑制コメントを生む |
| 型チェックを入れない | Agent Interface・Task・Policy は3つの実装タスク（T-005〜T-007）にまたがる。**型の食い違いをレビューではなくコマンドで検出できることの価値が大きい** |
| pyright | Node.js 実行環境への依存が増える。Python 環境だけで閉じる mypy を採る |

mypy は `--strict` にしない。Stage 0 の目的は骨格であり、厳格設定の充足が実装の主目的になるのを避ける。適用範囲は `src/media_agent` のみ（`tests/` は対象外）。

### 3.7 ビルドバックエンドと開発インストール

**採用: `pyproject.toml` + hatchling。開発インストールは `pip install -e ".[dev]"`**

- **ここで決めるのはローカル開発インストールだけである。** PyPI への公開・リリースフロー等の「Package 配布方式」は Stage 8 の対象であり、T-001 の禁止事項（決めない）

| 却下案 | 却下理由 |
| --- | --- |
| setuptools | 動作はするが、src レイアウトのパッケージ探索とパッケージデータ（テンプレート）の同梱に追加設定が要る。hatchling は既定でパッケージ配下を同梱する |
| Poetry / PDM | 依存解決とロックの独自ワークフローが加わる。Stage 0 に必要なのは「入れてテストが動く」ことだけで、ロックファイルの運用を今決める理由が無い |
| setuptools-scm によるバージョン付け | Git タグからバージョンを導出するため、タグの無い作業ブランチでは不定な版数になる。12章の方針（単一の真実を `__init__.py` に置く）と両立しない |

---

## 4. Repository 構造

```
media-agent/                        # このリポジトリ（= Media Agent 本体の開発リポジトリ）
├── pyproject.toml                  # パッケージ定義・依存・ruff/mypy/pytest の設定（唯一の設定ファイル）
├── README.md                       # 利用者向け。org-documentation の担当
├── .gitignore
├── .github/
│   └── workflows/
│       └── ci.yml                  # テストとリントだけを実行する CI（11章）
├── src/
│   └── media_agent/                # Python パッケージ本体（5章）
├── tests/                          # 10章
├── docs/                           # 要件定義書・タスク台帳・設計成果物
│   ├── design/                     # 設計成果物（本文書）
│   ├── tasks/
│   └── ...
├── CLAUDE.md                       # AI 開発組織の運営規約（層2）
└── .claude/                        # ★ AI 開発組織の運営ファイル。製品の一部ではない
```

決定と理由:

- **src レイアウトを採る。** `src/` を挟むと、テストがリポジトリルートの `media_agent/` ディレクトリを偶然 import することがなくなり、**「インストールされたパッケージ」を検証していると保証できる**。却下案: フラットレイアウト（ルート直下に `media_agent/`）→ 未インストールでも import できてしまい、entry point（`media-agent` コマンド）の欠陥をテストが見逃す
- **設定は `pyproject.toml` に集約する。** `setup.cfg` / `pytest.ini` / `.flake8` / `mypy.ini` を作らない。却下案: ツールごとの個別ファイル → 設定の所在が分散し、どれが有効かの判断コストが恒常的にかかる
- **`.claude/` はこのリポジトリの AI 開発組織の運営ファイルであり、製品が生成する `.claude/`（8章）とは別物である。** 実装タスクはリポジトリ直下の `.claude/` を読み書きしない（詳細は 17.1 の罠 T-1）

---

## 5. Python package 構造

### 5.1 ディレクトリ

要件定義書4節の4層（Core / Media / Connector / Project）を、そのままパッケージの構造に写す。層の名前を一致させるのは、**要件のどの節がどのディレクトリに対応するかを、探さずに分かる状態にするため**である。

```
src/media_agent/
├── __init__.py                 # __version__ の単一の真実（12章）
├── __main__.py                 # `python -m media_agent` の入口
├── errors.py                   # 例外階層（6.5）。CLI が終了コードへ変換する
│
├── cli/                        # インターフェース層
│   ├── __init__.py
│   ├── app.py                  # click グループ、グローバルオプション、例外→終了コード変換
│   └── commands/               # 1コマンド1モジュール（init.py / doctor.py / status.py / run.py / stubs.py ...）
│
├── core/                       # Core Layer（要件定義書5節）
│   ├── config/                 # Config のモデルと読み込み・検証（T-002 が Schema を確定）
│   ├── db/                     # 接続・スキーマ・Repository（3.4）
│   ├── runtime/                # Agent Interface・Registry・Runner（要件5.1）
│   ├── task/                   # Task モデルと状態遷移（要件5.2）
│   ├── policy/                 # Policy Engine（要件5.3・13節）
│   └── observability/          # log.py（運用ログ）/ audit.py（判断の追跡記録）（要件5.5・17節）
│
├── project/                    # Project Layer（要件定義書8節）
│   ├── layout.py               # プロジェクトルート探索と `.media-agent/` 配下のパス解決
│   ├── scaffold.py             # `init` の生成処理
│   └── templates/              # config.yaml / strategy.md / rules.md / .gitignore の雛形
│
└── agents/                     # Media Layer（要件定義書6節）。Stage 0 は検証用の組み込み Agent のみ
    ├── __init__.py
    └── builtin/                # echo Agent 等（T-002 が定義する検証用ダミー Agent）
```

- `connectors/`（Connector Layer、要件定義書7節）は **Stage 0 では作らない。** 位置だけ `src/media_agent/connectors/` に予約する。空パッケージを先に置かないのは、中身の無いディレクトリが「実装済み」に見えるため（13章 E-3）
- `core/observability/` を `core/logging/` としないのは、標準ライブラリ `logging` と同名のパッケージが読み手を混乱させるため（絶対 import なので動作上の衝突は起きないが、名前で誤解を招く）

### 5.2 依存の向き（構造上の規約）

```
cli  ──▶  project  ──▶  core
 │                        ▲
 └──────────────────────┘
agents ──▶ core
```

- **`core/` は `cli/` `project/` `agents/` を import しない。** Core を Project 固有の事情から切り離す（要件定義書 開発原則6、非機能要件20.2）
- **`core/` は `.media-agent` という文字列を持たない。** パスは必ず `project/layout.py` から受け取る。この一行は grep で機械的に検査できる（14章 Q7）
- Stage 1 以降で Agent を足すときに `core/` を変更しなくてよい状態を保つ。これが「Agent を追加できる構造」（非機能要件20.1）の実体である

却下案: レイヤ分けをせず `media_agent/` 直下にモジュールを並べる → Stage 0 の規模なら成立するが、Stage 1 以降で Media Layer と Core の境界（要件定義書 開発原則4・6）が曖昧になり、Agent が Core を直接書き換える経路を止められない。

---

## 6. CLI 設計

### 6.1 エントリポイント

| 経路 | 定義 |
| --- | --- |
| `media-agent ...` | `[project.scripts]` の `media-agent = "media_agent.cli.app:main"` |
| `python -m media_agent ...` | `__main__.py` が同じ `main` を呼ぶ |

**2経路とも同じ関数へ落とす。** 却下案: entry point のみ → 開発中に未インストール状態で動かす手段が無い。

### 6.2 グローバルオプション

| オプション | 既定 | 意味 |
| --- | --- | --- |
| `-C, --project-dir PATH` | カレントディレクトリ | 対象プロジェクトのディレクトリ。環境変数 `MEDIA_AGENT_PROJECT_DIR` でも指定できる |
| `-v, --verbose` | off | 運用ログを詳細レベルで標準エラーへ出す |
| `-q, --quiet` | off | エラー以外を抑制する |
| `--json` | off | 機械可読出力（Stage 0 では `doctor` / `status` が対応。他コマンドは無視する） |
| `--version` | — | バージョンを表示して終了（12章） |

- **`-C` を必ず持たせる。** 受け入れテストがカレントディレクトリを変えずに一時ディレクトリを対象にできること、Claude Code 等の外部からプロジェクトを明示して呼べることの2つが理由。却下案: cwd 固定 → テストが `os.chdir` に依存し、実行順序に影響される
- **`--json` を Stage 0 から入れる。** 要件定義書9.2節が Claude Code から CLI を呼ぶ構成を想定しており、出力の機械可読形式を後付けすると人間向け文言のパースが先に定着してしまう

### 6.3 プロジェクトルートの決定

1. `-C/--project-dir` または `MEDIA_AGENT_PROJECT_DIR` があればそのディレクトリ
2. 無ければカレントディレクトリから**上位へ `.media-agent/` を探索**する（Git と同じ挙動）。ファイルシステムのルートに達したら「未初期化」とする
3. `init` だけは例外で、**探索せず対象ディレクトリそのもの**に作る

却下案: 常にカレントディレクトリのみを見る → プロジェクトのサブディレクトリで作業中にコマンドが使えず、要件定義書3.2節の利用像（`cd my-project` して使う）から外れる。
罠: 上方探索は「親に `.media-agent/` があると子ディレクトリでも成功する」ことを意味する。テストは必ず一時ディレクトリ（`tmp_path`）を使うこと（17.1 の罠 T-3）。

### 6.4 コマンドの切り分け（Stage 0）

| コマンド | Stage 0 の扱い | 内容 | 実装タスク |
| --- | --- | --- | --- |
| `init` | **実装** | `.media-agent/` を生成する（7章） | T-004 |
| `doctor` | **実装** | 設定・構造・DB の検証（検査項目は T-002）。**認証情報の不在を異常としない** | T-007 |
| `status` | **実装** | 登録 Agent と Task の現在状態を出力する | T-007 |
| `run` | **実装** | Stage 0 では組み込みの検証用 Agent を1本実行し、Task と Audit を残す（具体は T-002） | T-007 |
| `agent list` | **実装（読み取りのみ）** | Registry に登録された Agent の一覧 | T-007 |
| `task list` | **実装（読み取りのみ）** | 記録された Task の一覧と状態 | T-007 |
| `setup` | **スタブ** | 設定対象（Connector・認証）が Stage 0 に存在しないため | T-004 |
| `post` | **スタブ** | X Connector は Stage 3（P-2・P-3） | T-004 |
| `research` | **スタブ** | Research Agent は Stage 2 | T-004 |
| `analyze` | **スタブ** | Analytics Agent は Stage 5 | T-004 |

- **`agent list` / `task list` を実装する理由**: Runtime と Task は Stage 0 の実装対象であるにもかかわらず、CLI から観測する手段が `status` しかないと、受け入れテストが内部 API を直接叩くことになる。**公開された面（CLI）で検証できる状態を作る**ほうが、テストが実装の写像になりにくい。読み取り専用に限るため実装コストは小さい
- `agent run` / `task cancel` 等の書き込み系サブコマンドは Stage 0 では**設けない**（`run` と重複するため）
- **`setup` をスタブにする理由**: `setup` は要件定義書10節で「Project 設定・Connector 等を設定する」と定義される。Stage 0 に Connector も認証情報も存在しないため、対話設定の対象が `config.yaml` の再編集しか残らない。却下案: `config.yaml` の対話編集として実装する → Stage 3 で Connector 設定が入った時点で作り直しになる

**スタブの挙動（全スタブ共通）**: 標準エラーへ「このコマンドは Stage 0 では未実装であり、Stage N で実装予定である」と明示し、**終了コード 10 で終了する**。標準出力には何も出さない。
却下案: 終了コード 0 で「未実装」と表示 → スクリプトや CI から成功と区別できない。これは要件定義書の趣旨（沈黙して成功しない）に反する。

### 6.5 終了コードと例外階層

**CLI 層が唯一の例外変換点である。** 各コマンドは例外を投げ、`cli/app.py` がまとめて終了コードへ変換する。

| 終了コード | 意味 | 対応する例外 |
| --- | --- | --- |
| 0 | 成功 | — |
| 1 | 想定内の実行時エラー | `MediaAgentError`（下記以外） |
| 2 | CLI の使い方の誤り | Click の `UsageError`（Click 既定値） |
| 3 | プロジェクトが未初期化 | `ProjectNotInitializedError` |
| 4 | 設定エラー（構文・必須項目欠落・型不一致） | `ConfigError` とその派生 |
| 5 | `doctor` の検査に不合格 | `DoctorCheckFailedError` |
| 6 | Policy により拒否された | `PolicyDeniedError` |
| 10 | Stage 0 では未実装のコマンド | `NotImplementedInStageError` |
| 70 | 想定外の内部エラー | 上記以外の例外（トレースは `--verbose` 時のみ表示） |

- 例外はすべて `media_agent.errors.MediaAgentError` を基底とし、**クラス属性として自分の終了コードを持つ**。CLI 側に `if isinstance(...)` の分岐表を作らない
- 却下案A: 全異常を 1 にまとめる → 受け入れテスト S-D（未初期化）と S-I（設定不正）が同じコードになり、テストがメッセージ文字列に依存する
- 却下案B: `sysexits.h` に全面的に合わせる（64/65/78 等） → 対応が直感的でなく、利用者にも読み取りにくい。想定外エラーの 70 のみ慣習に合わせる
- **エラーメッセージは標準エラーへ、通常出力は標準出力へ出す。** Click 8.2 以降の `CliRunner` は両者を分離して返すため、テストが取り違えない（15.2 で確認済み）

---

## 7. `.media-agent/` 構造

`media-agent init` が対象プロジェクトに生成する。要件定義書8.1節の構造に、Stage 0 で必要な2ファイルを加える。

```
<project>/.media-agent/
├── config.yaml        # プロジェクト設定（要件8.2・13節）。Git 管理対象
├── strategy.md        # メディア戦略（要件8.3）。Git 管理対象
├── rules.md           # 禁止事項・ブランドルール（要件8.4）。Git 管理対象
├── agents/            # Custom Agent 定義の置き場（要件8.5、9章）。Stage 0 ではロードしない
│   └── .gitkeep
├── memory/            # Stage 1 以降の Memory（要件5.4）。Stage 0 では空
│   └── .gitkeep
├── data/
│   └── media-agent.db # SQLite（3.4）。Git 管理対象外
├── logs/
│   ├── media-agent.log # 運用ログ。Git 管理対象外
│   └── audit.jsonl     # 判断の追跡記録。Git 管理対象外
└── .gitignore         # data/ logs/ .env を除外（要件14.2）
```

決定と理由:

- **`.gitignore` を `.media-agent/` の中に置く。** プロジェクト側のルート `.gitignore` を書き換えると、利用者の既存の設定と衝突する。自分が作ったディレクトリの中で完結させる。却下案: プロジェクトルートの `.gitignore` へ追記 → 既存ファイルの改変になり、`init` を冪等にしにくい
- **設定・戦略・ルールは Git 管理対象、状態（DB・ログ）は対象外。** 前者はプロジェクトの意思、後者は実行時の産物であるため
- **`.env` を生成しない。** Stage 0 に認証情報を必要とする機能が無い（P-2）。ただし `.gitignore` には `.env` を**先に書いておく**（要件定義書14.2節。将来ファイルが置かれたときに漏れない）
- **DB ファイルは `init` の成否に依存させない。** DB は接続時に「無ければ作ってスキーマを適用する」冪等な処理（`ensure_schema`）で用意する。`init` はその処理を呼ぶだけにする。理由は 17.2 の順序制約 O-1（T-004 が DB を知らずに完了できるようにするため）
- **`config.yaml` はスキーマ版数を持つ。** 具体的なキー名と値は T-002 が決めるが、「版数を持つこと」は方式として確定させる。持たないと将来の設定移行が実施できない
- 既に `.media-agent/` が存在する場合の `init` の挙動は **T-002 が決める**（本設計は「冪等であること」だけを要求する）

---

## 8. `.claude/` 連携構造（**設計のみ。Stage 0 では実装しない**）

要件定義書19節の表で、Claude Code 連携は S0 が「設計」である。ここでは**将来 `init` が生成する形**だけを決め、Stage 0 では生成処理を実装しない。

### 8.1 生成物の形（将来）

```
<project>/.claude/
├── skills/
│   └── media-agent/
│       └── SKILL.md      # 「今日のメディア運用を実行して」→ media-agent CLI への対応付け
└── agents/
    └── media-agent-operator.md
```

### 8.2 設計上の境界（ここが本章の要点）

- **Skill / Agent 定義は CLI を呼ぶだけであり、ロジックを持たない。** 判断・実行・記録はすべて `media-agent` CLI 側にある。要件定義書9.2節の構成（Claude Code → Media Agent CLI → Agents）をそのまま境界にする
  - 理由: Skill にロジックが入ると、Claude Code 経由と CLI 直接実行とで挙動が食い違う。追跡（要件20.3）と再現性（要件20.5）が壊れる
- **Skill が CLI を呼ぶときは `--json` を使う**（6.2）。人間向けの文言を解析させない
- **生成は明示的なオプトインとする。** 将来の実装は `media-agent init --with-claude`（既定は生成しない）。理由: `.claude/` は利用者が既に自分の用途で使っている可能性が高いディレクトリであり、`init` が黙って書き込んでよい場所ではない
- Stage 0 では **`init` は `.claude/` を一切読み書きしない**

却下案: Stage 0 で雛形だけ生成しておく → 中身が CLI の実挙動と対応していない Skill が残り、利用者が実行して失敗する。要件定義書23節「『将来可能な構造』にすることと『MVP で実装すること』を明確に分離する」に反する。

---

## 9. Custom Agent のロード方式（**設計のみ。Stage 0 では実装しない**）

要件定義書19節の表で、Custom Agent も S0 は「設計」である。

### 9.1 定義フォーマット

**Markdown + YAML front matter**（`.media-agent/agents/*.md`）

```markdown
---
name: protein-expert
description: プロテイン関連の投稿を専門に評価する
version: 1
inputs: [topic, sources]
outputs: [evaluation]
---

（本文 = Agent への指示。自然言語で書く）
```

- 要件定義書8.5節が例として `.media-agent/agents/protein-expert.md` を挙げており、**拡張子が `.md` であることは要件側で決まっている**
- front matter に構造化メタデータ、本文に自然言語の指示、という分担にする。利用者が書く対象は本文であり、機械が読む対象は front matter である
- front matter の項目は将来の詳細設計で確定させる（Stage 0 の T-002 でも決めない。ロードを実装しないため）

| 却下案 | 却下理由 |
| --- | --- |
| Python プラグイン（entry points） | 「Agent Plugin API」は Stage 8 の対象であり、T-001 の禁止事項。利用者に Python 実装を要求する点も要件定義書3.1節の想定利用者像より重い |
| YAML / JSON 単体 | 自然言語の指示（長文・改行・Markdown 記法）を持たせにくい。要件定義書8.5節の例がファイル形式として `.md` を示している |
| 独自 DSL | 学習コストに見合う利得が無い |

### 9.2 ロードの合流点

- Custom Agent は、**組み込み Agent と同じ `AgentRegistry` に、同じインターフェースで登録される**（`core/runtime`）。Runtime は「その Agent が組み込みか利用者定義か」を区別しない
- 読み込む場所は `project/` 層（`.media-agent/agents/` を走査する責務は Project Layer にある）。`core/runtime` はディレクトリを知らない（5.2 の依存の向き）
- 実行時に自然言語の指示を処理するには AI Provider が要る。**AI 処理の実行方式は Stage 0 の範囲外（禁止事項）**であり、この設計では「Registry への合流点はここである」ことだけを固定する

**Stage 0 の実装範囲**: `.media-agent/agents/` ディレクトリを `init` が作るところまで。走査・解析・登録は実装しない（T-006 完了条件7 と一致）。

---

## 10. Test 構造

### 10.1 ディレクトリ

```
tests/
├── conftest.py            # 全テスト共通の fixture（10.3・10.4）
├── unit/                  # 単体テスト。★実装エージェントが書く
│   └── ...                # src/media_agent/ の構造に対応させる
├── acceptance/            # 受け入れテスト。★org-test（T-003）が書く
│   └── test_stage0_*.py   # S-A 〜 S-I
└── fixtures/              # サンプル config など、テストデータ
```

- **単体テストと受け入れテストをディレクトリで分ける。** 書く主体が違う（`docs/glossary.md`「テスト」）ため、レビュー時に「誰の担当分が欠けているか」がディレクトリ単位で分かる
- 受け入れテストには `@pytest.mark.acceptance` を付け、`pyproject.toml` に marker を登録して `--strict-markers` を有効にする。`pytest -m acceptance` / `pytest tests/unit` で切り分けられる

### 10.2 CLI の検証方法

- **既定は `click.testing.CliRunner` によるインプロセス実行。** 高速で、終了コード・標準出力・標準エラーをそのまま取得できる
- **加えて、`media-agent --version` と `media-agent --help` の疎通だけ subprocess で1本確認する。** entry point スクリプトが実際に生成されているかは、インプロセス実行では検証できないため
- 却下案: 全て subprocess → 遅く、失敗時の情報が乏しい。却下案: 全てインプロセス → `pip install -e .` が壊れていても気付けない

### 10.3 プロジェクト用 fixture

- すべてのテストは `tmp_path` 上のディレクトリを対象にし、`-C/--project-dir` で指定する。`os.chdir` を使わない（テスト間の順序依存を作らないため）
- `initialized_project` 相当の fixture（`init` 済みの一時プロジェクト）を `conftest.py` に置く。S-B / S-C / S-E〜S-I が共有する

### 10.4 ネットワーク遮断（PO 制約の機構化）

`tests/conftest.py` に **autouse の fixture を置き、テスト実行中の外向きソケット接続を例外にする**。

- 理由: Stage 0 に外部接続は存在しない（P-2・P-3）。「書かないこと」をレビューの目視に委ねず、**外へ出た瞬間にテストが落ちる**状態にする
- これは T-003 の完了条件4（X API・外部ネットワーク・認証情報を使わない）と、T-004〜T-007 の禁止事項を同時に担保する
- 却下案: レビューでの目視確認のみ → 依存ライブラリが内部で通信した場合に検出できない

### 10.5 テスト実行コマンド

11.2 および 15章のコマンド表を参照。正典は `pytest`（引数なし＝全テスト）。

---

## 11. GitHub Actions

### 11.1 Stage 0 で置くもの・置かないもの

要件定義書19節の表では GitHub Actions の行が S3 以降になっており、28節では「最初に決定する対象」に挙がっている。**これは矛盾ではなく、対象が違う。**

| 用途 | Stage 0 | 根拠 |
| --- | --- | --- |
| **CI（テストとリントの実行）** | **置く**（`.github/workflows/ci.yml`） | 28節13番の決定対象。T-007 完了条件6 |
| **Scheduler（定期実行による自動投稿）** | **置かない** | 要件定義書5.6節の Scheduler は Stage 3（自動投稿）で初めて意味を持つ。19節の表の GitHub Actions 行はこちらを指す |

この解釈は T-001 の決定ログに記録した。

### 11.2 CI workflow の内容（方式）

- トリガ: `push`（全ブランチ）と `pull_request`
- Python matrix: 3.11 / 3.12 / 3.13（3.1 の決定と対応）
- 手順:
  1. checkout
  2. setup-python
  3. `python -m pip install -e ".[dev]"`
  4. `ruff check .`
  5. `ruff format --check .`
  6. `mypy src`
  7. `pytest`
- **Secrets を一切参照しない。外部サービスへ接続しない**（P-2）。CI が認証情報を要求する構成になったら、それは Stage 0 の範囲を超えた合図である
- 却下案: `main` への push のみでトリガ → 今回の作業は作業ブランチ上で進むため、ブランチ上で一度も CI が走らないことになる
- 却下案: 単一 Python バージョンのみ → 「>= 3.11」という宣言（3.1）を検証しないまま公言することになる

**注記（未検証）**: 本タスクでは GitHub Actions を実際に実行していない。workflow の妥当性は T-007 の完了条件6（ファイルの妥当性まで）に従う。

---

## 12. Version 管理

| 項目 | 決定 |
| --- | --- |
| 版数の体系 | セマンティックバージョニング。Stage 0 の完成時点で **0.1.0** |
| Stage との対応 | **Stage が1つ進むごとに minor を上げる**（Stage 0 = 0.1.x、Stage 1 = 0.2.x …）。1.0.0 は Stage 8（配布可能な状態）に到達したときに検討する |
| 単一の真実 | `src/media_agent/__init__.py` の `__version__`。`pyproject.toml` は hatchling の dynamic version でここを読む |
| 表示 | `media-agent --version` は `media_agent.__version__` を表示する |
| Config スキーマ版数 | パッケージ版数とは**独立**に `config.yaml` が持つ（7章）。項目名は T-002 |
| DB スキーマ版数 | パッケージ版数とは**独立**に DB が持つ（3.4 補足）。方式は T-002 |
| Git タグ | `v0.1.0` の形式。**タグ付けは Stage 0 の完了条件に含めない**（リリース運用はオーケストレーターの判断） |
| CHANGELOG | Stage 0 では必須としない。必要性の判断は org-documentation 側（T-010 以降） |

決定の理由:

- 版数の定義が2か所にあると必ずずれる。`importlib.metadata` から読む案は、**未インストールのソースから実行したときに失敗する**ため採らない（開発中と本番で挙動が変わるのを避ける）
- Stage と minor を対応させるのは、要件定義書18節のロードマップが唯一の進捗の物差しであるため。版数を見れば「どの Stage の成果物か」が分かる
- **アプリ版数・Config 版数・DB 版数を分離するのが要点である。** 3つを1つの数で表そうとすると、コードだけ直したいときに設定移行が要るように見えてしまう

---

## 13. Stage 1 以降のための拡張点

**「将来可能な構造」にすることと「MVP で実装すること」を分離する**（要件定義書23節）。ここは*位置の予約*であり、実装ではない。

| # | 拡張点 | 位置 | Stage 0 でやること |
| --- | --- | --- | --- |
| E-1 | Agent の追加（Content / Research / Strategy / Analytics / Engagement） | `src/media_agent/agents/` に足し、`AgentRegistry` へ登録する。**`core/` は変更しない** | Registry と Agent インターフェースを用意する（T-002・T-006） |
| E-2 | DB アクセス方式の差し替え | `core/db/` の Repository 層。呼び出し側は SQL を直接書かない | Repository 層を挟む（T-005） |
| E-3 | Connector の追加（X / Google News / RSS / Web） | `src/media_agent/connectors/` を新設する（Stage 0 では**作らない**） | 位置の予約のみ。ディレクトリも作らない |
| E-4 | Action の実行（投稿等） | **必ず Policy Engine を通る経路にする。** Stage 0 の時点で関門を先に作る | Policy Engine を実装する（T-006） |
| E-5 | AI Provider の差し替え | Agent の内側。Core は AI を直接呼ばない | 方式は決めない（禁止事項）。Core が AI に依存しないことだけ守る |
| E-6 | Custom Agent のロード | `project/` 層で走査し、同じ Registry へ登録する（9章） | ディレクトリを作るまで |
| E-7 | Claude Code Skill の生成 | `init --with-claude`（8章） | 生成しない |
| E-8 | 認証情報（環境変数 / `.env`） | Config 読み込みの後段。Stage 0 では読み込まない | `.gitignore` に `.env` を先に書く |
| E-9 | Scheduler / 定期実行 | `.github/workflows/` の別 workflow、または cron | 置かない（11.1） |

---

## 14. このプロジェクトの品質基準（→ オーケストレーターが層2 へ載せる）

**タスクごとの完了条件へ複写しない。** レビュー（T-009）が参照する基準として、`CLAUDE.md` または `.claude/rules/` に置くことを提案する。

| # | 基準 | 判定方法 |
| --- | --- | --- |
| Q1 | 全テストが通る | `pytest` の終了コードが 0 |
| Q2 | リント・整形に違反が無い | `ruff check .` と `ruff format --check .` の終了コードが 0 |
| Q3 | 型チェックに違反が無い | `mypy src` の終了コードが 0 |
| Q4 | 公開関数・メソッド・クラス属性に型注釈がある | Q3 に含まれる（`disallow_untyped_defs`） |
| Q5 | 新規モジュールに対応する単体テストがある | レビュー観点（`tests/unit/` の対応を目視） |
| Q6 | 外部ネットワーク接続・認証情報の要求が無い（Stage 0） | 10.4 のネットワーク遮断 fixture + レビュー |
| Q7 | `core/` が Project 固有の事情を持たない | `src/media_agent/core/` に `.media-agent` の文字列が出現しない（grep） |
| Q8 | 例外は `media_agent.errors` の階層を使い、終了コードへの変換は CLI 層だけで行う | レビュー観点 |
| Q9 | Agent は外部副作用を持たず、Action は Policy Check を経てから実行される（要件2.4・開発原則5） | レビュー観点 |
| Q10 | ログ・Audit に秘密値を出力しない | レビュー観点 |

---

## 15. 実際に動くコマンド

**本タスクでは実行しない**（実行は実装タスクの担当）。3章の依存が実際に導入可能であることだけは 15.2 で確認した。

### 15.1 コマンド一覧

```bash
# --- 開発環境の準備（リポジトリルートで実行）---
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

# --- テスト ---
.venv/bin/pytest                          # 全テスト（正典）
.venv/bin/pytest tests/unit               # 単体テストのみ
.venv/bin/pytest -m acceptance            # 受け入れテストのみ
.venv/bin/pytest --cov=media_agent --cov-report=term-missing

# --- リント・整形・型チェック ---
.venv/bin/ruff check .                    # 静的検査
.venv/bin/ruff format --check .           # 整形の検査（CI 用。書き換えない）
.venv/bin/ruff format .                   # 整形の適用（手元用）
.venv/bin/mypy src

# --- CLI の疎通 ---
.venv/bin/media-agent --version
.venv/bin/media-agent --help
.venv/bin/python -m media_agent --help

# --- Stage 0 の検証シナリオ（要件定義書18節）---
mkdir -p /tmp/ma-demo && cd /tmp/ma-demo
media-agent init
media-agent doctor
media-agent status
media-agent run
```

- 仮想環境を有効化している場合は `.venv/bin/` の前置を省いてよい。**CI では前置しない**（`setup-python` 済みのため）
- `pip install -e ".[dev]"` の引用符は必須（zsh 等が `[` を展開するため）

### 15.2 本タスクで確認した事実（設計判断の根拠）

| 確認したこと | 結果 |
| --- | --- |
| 既定 `python3` のバージョン | 3.11.15 |
| `sqlite3` のバージョン | 3.45.1 |
| PyPI への到達性 | 到達可能 |
| `click` / `pydantic` / `PyYAML` / `pytest` / `pytest-cov` / `ruff` / `mypy` / `hatchling` の導入可否 | 一時ディレクトリの venv へ全て導入できた（click 8.4.2 / pydantic 2.13.4 / pytest 9.1.1 / ruff 0.16.4 / mypy 2.3.1） |
| Click 8.4 の `CliRunner` の stderr 挙動 | `result.stdout` と `result.stderr` が**分離**されている。`mix_stderr` 引数は存在しない（8.2 で削除） |

**リポジトリの作業ツリーには何も導入していない**（設計タスクのため）。

---

## 16. 実装単位の分割案

### 16.1 分割案

| 単位 | 範囲 | 完了の目安 | 必要なスキル |
| --- | --- | --- | --- |
| **U-1** | パッケージ骨格（`pyproject.toml`・依存・ruff/mypy/pytest 設定・`__version__`）／CLI エントリポイントとコマンド登録／グローバルオプションと終了コード変換／例外階層／Config の読み込みと検証／`init` による `.media-agent/` 生成／リポジトリの `.gitignore` | `media-agent --help` が動く。S-A / S-D / S-I が通る | Python パッケージング、Click、Pydantic |
| **U-2** | DB 層（6 Entity のスキーマ・`ensure_schema`・Repository）／Migration 機構／Logger（運用ログ）／Audit（判断記録） | S-H が通る。初期化を2回実行しても壊れない | SQLite / SQL、ログ設計 |
| **U-3** | Agent Interface・Registry・Runner／検証用の組み込み Agent／Task モデルと状態遷移／Policy Engine | S-E / S-F / S-G が通る | ドメインモデリング、状態機械 |
| **U-4** | `doctor` / `status` / `run` / `agent list` / `task list` の実装／Test 基盤の仕上げ／CI workflow | S-A〜S-I が全て通る。`.github/workflows/ci.yml` がある | CLI 統合、CI |

### 16.2 依存関係と推奨順序

```
U-1 ──▶ U-2 ──▶ U-3 ──▶ U-4
```

- U-2 は U-1 の Config とプロジェクトパス解決に依存する
- U-3 は U-2 の Task 永続化と Audit に依存する（T-006 完了条件3「新しい記録機構を作らない」）
- U-4 は U-1〜U-3 すべてに依存する

**並列に実行できる単位**: 理屈のうえでは U-2 と U-3 は「U-3 が U-2 のインターフェースにのみ依存する」形にすれば同時に着手できる。**ただし今回は直列を推奨する。** 理由は `docs/handover.md` の判断（同一ワークツリーでの同時 commit がインデックスを壊す、P-7）であり、設計上の依存ではない。並列化するならワークツリーを分ける必要がある。

### 16.3 オーケストレーターの想定分割（T-004〜T-007）との照合

**U-1〜U-4 は T-004〜T-007 と一対一で対応する。分割の境界に食い違いは無い。** ただし、**範囲の記述に加えるべき差分が3点**ある。いずれも境界の変更ではなく追記である。

| # | 対象 | 差分 | 理由 |
| --- | --- | --- | --- |
| D-1 | **T-004** | 変更範囲に「**ruff / mypy / pytest の設定（`pyproject.toml` 内）**」を明示してほしい | 全実装タスクの共通完了条件が「T-001 が定めたリントコマンドが通る」である以上、設定は T-004 の時点で存在していなければならない。T-007 の「Test 基盤の仕上げ」まで待てない |
| D-2 | **T-007** | 完了条件に「**`agent list` / `task list` が動作する**」を追加してほしい | 6.4 で Stage 0 実装と決めたため。T-004 は枠の登録のみ、中身は T-007。読み取り専用のため小さい |
| D-3 | **T-003** | 「`pyproject.toml` がまだ存在しない時点でテストを書く」ことになる点を明示してほしい | 17.2 の順序制約 O-2 を参照。T-003 の禁止事項（製品コードを書かない）と、完了条件1（T-001 が定めたコマンドで収集・実行できる）の両立方法を明記しないと、T-003 が停止条件に当たる可能性がある |

**分割をやり直す必要は無い**と判断する。上記3点は各タスクファイルへの追記で解消する（追記はオーケストレーターの担当）。

---

## 17. 実装時の注意点

### 17.1 踏みやすい罠

| # | 罠 | 対処 |
| --- | --- | --- |
| **T-1** | **このリポジトリ直下の `.claude/` を製品の生成対象と取り違える。** ここは AI 開発組織の運営ファイルであり、製品が生成する `.claude/`（8章）は*利用者のプロジェクト*側にある | 実装は本リポジトリの `.claude/` を読み書きしない。Stage 0 では `.claude/` の生成処理そのものを実装しない |
| **T-2** | SQLite の外部キーは既定で無効。制約を書いても黙って効かない | 接続ごとに `PRAGMA foreign_keys = ON` を実行する |
| **T-3** | プロジェクトルートの上方探索（6.3）により、親ディレクトリに `.media-agent/` があるとテストが誤って成功する | テストは必ず `tmp_path` を使い、`-C` で明示する。`os.chdir` を使わない |
| **T-4** | `project/templates/` を `__file__` 相対パスで読むと、将来の zip 配布や別の実行形態で壊れる | `importlib.resources` で読む。テンプレートが wheel に含まれることを確認する |
| **T-5** | Click 8.2 以降、`CliRunner(mix_stderr=False)` は存在しない。`result.stderr` は常に分離されている | 古い記事の書き方を写さない（15.2 で確認済み） |
| **T-6** | `yaml.load` を使うと任意オブジェクト構築を許す | `yaml.safe_load` のみ使う（3.3） |
| **T-7** | `core/observability/log.py` の中で標準ライブラリ `logging` を使うとき、モジュール名の見た目が紛らわしい | 絶対 import のみを使う（Python 3 の既定）。相対 import を書かない |
| **T-8** | スタブコマンドを終了コード 0 で終わらせる | 終了コード 10（6.4）。**沈黙して成功しないこと** |

### 17.2 順序の制約

| # | 制約 |
| --- | --- |
| **O-1** | **DB の生成を `init` の実装（U-1）に埋め込まない。** DB は `ensure_schema`（冪等）で用意し、`init` はそれを呼ぶだけにする。こうしないと U-1 が U-2 の完成を待つことになる。U-2 の担当が `init` に1行足す形になる |
| **O-2** | **T-003（受け入れテスト作成）は `pyproject.toml` より前に来る。** T-003 の時点では `media_agent` パッケージが存在しないため、テストは収集時に `ModuleNotFoundError` で落ちる。**これが「未実装だから落ちた」証拠として正しい状態である。** T-003 は `pip install pytest` した仮想環境で `pytest tests/acceptance` を実行し、その出力を証拠にすればよい。**空のモジュールを作って回避しない**（T-003 の禁止事項） |
| **O-3** | Policy Engine（U-3）は Config（U-1）から設定を読む。独自の設定読み込みを作らない |
| **O-4** | Audit（U-2）は Runtime（U-3）より先に存在する必要がある。記録機構が無い状態で Runtime を作ると、記録の無い実行経路が残る |

---

## 18. 未解決の不確実性

| # | 事項 | 扱い |
| --- | --- | --- |
| **X-1** | 既存 CSV をそのまま永続 DB とするか、Media Agent 内部 DB へ Import するか（要件定義書11.2節が「Stage 0/1 の技術検証で決定する」としている） | **Stage 0 では決めない。** Stage 0 に過去投稿 Import は無く（19節の表で S1）、判断材料となる実データも Stage 0 の範囲に無いため。3.4 の Repository 層があるため、Stage 1 の判断がどちらに転んでも Core の変更にはならない |
| **X-2** | GitHub Actions が実際に成功するか | 本タスクでも T-007 でも実行しない（T-007 完了条件6 が「workflow ファイルの妥当性まで」と定めている）。**未検証であることを明示する** |
| **X-3** | `doctor` の検査項目の内訳、`status` / `run` の出力内容 | **T-002 の範囲**（本設計は 1.2 で対象外と宣言した）。ここを推測で埋めないこと |
| **X-4** | Windows での動作 | 検証環境が Linux のみ。パス操作は `pathlib` に統一して移植性の芽を残すが、Stage 0 では検証しない |

---

## 19. 新しく定義した語

この設計で名前を付けたもの。**用語集（`docs/glossary.md`）への登録はオーケストレーターが行う。**

| 語 | 定義 | 一般的な意味で受け取ると何を間違えるか |
| --- | --- | --- |
| **プロジェクトルート** | `.media-agent/` を含むディレクトリ。`-C` 指定が無ければカレントから上方へ探索して決まる（6.3） | 「リポジトリのルート」と取り違える。Media Agent 本体のリポジトリではなく、**Media Agent を導入した利用者側のディレクトリ**を指す |
| **スタブコマンド** | Stage 0 では未実装であることを標準エラーへ明示し、**終了コード 10** で終わる CLI コマンド（`setup` / `post` / `research` / `analyze`）（6.4） | 「何もしないコマンド」と取ると終了コード 0 で実装してしまう。**成功と区別できることが要件である** |
| **スキャフォールド（scaffold）** | `media-agent init` が `.media-agent/` 配下の初期ファイル群を生成する処理（`project/scaffold.py`）（7章） | 汎用的なコード生成器と取り違える。対象は `.media-agent/` 配下だけであり、利用者のプロジェクトの他のファイルには触れない |
| **組み込み Agent（builtin agent）** | Media Agent 本体に同梱される検証用の Agent。Stage 0 では AI を呼ばない（`agents/builtin/`）（5.1） | 「Content Agent 等の本番 Agent」と取り違える。Stage 0 の組み込み Agent は Runtime が動くことを示すためだけに存在する |
| **AgentRegistry / AgentRunner** | Agent の登録簿と、登録された Agent を Task として実行する実行器（`core/runtime/`）。Custom Agent も同じ Registry へ合流する（9.2） | Registry を「設定ファイル」と取り違える。実行時のオブジェクト登録簿である |
| **PolicyDecision** | Policy Engine の判定結果。`outcome`（`allow` / `require_approval` / `deny`）と `reason_code`（`mode_auto` / `mode_approval` / `mode_disabled` / `limit_exceeded` 等）の2要素を持つ（S-G の4通りはこの組で区別する） | `deny` と `limit_exceeded` を同じ値にすると、受け入れテスト S-G の「4通り」を区別できない。**結果の種類と理由は別の軸である** |
| **運用ログ / 監査記録（Logger / Audit）** | 前者は人間が動作を追うためのログ（`logs/media-agent.log`）、後者は AI の判断を追跡する追記専用の記録（`logs/audit.jsonl` と DB の Decision）（5.1・7章） | 両者を「ログ」と一括りにすると、片方だけ実装される。**別物として実装する**ことが T-002・T-005 の完了条件である |
| **拡張点（Extension Point）** | Stage 1 以降の機能を足す位置として、Stage 0 が予約しておく場所（13章） | 「実装済みの拡張機構」と取り違える。E-3（`connectors/`）のようにディレクトリすら作らないものがある |
| **スタブ終了コード 10 / 終了コード表** | 6.5 の対応表。CLI の異常はすべてこの表のいずれかに落ちる | 「非ゼロならなんでもよい」と取ると、受け入れテストが終了コードではなくメッセージ文字列を判定するようになる |

---

## 20. T-002 への申し送り

T-002（Stage 0 詳細設計）が本設計の上で決めるべきこと。**本設計が答えを持っていない箇所である。**

1. Config Schema（項目名・型・必須/任意・既定値・検証エラー時の挙動）。**スキーマ版数の項目名を含めること**（7章）
2. DB Schema（6 Entity の列・型・NULL 可否・主キー・外部キー・インデックス）と Migration 方式（`PRAGMA user_version` を使う前提で矛盾は無い）
3. Agent Interface のシグネチャ（`AgentRegistry` / `AgentRunner` / 入出力の型）と、検証用の組み込み Agent の定義
4. Task Model と**許される状態遷移の表**
5. Policy Model（`PolicyDecision` の `outcome` と `reason_code` の値域を確定させること。S-G の4通りが区別できること）
6. Logging / Audit の項目（要件定義書5.5節の9項目）と、`logs/media-agent.log` / `logs/audit.jsonl` / DB の Decision への書き分け。**単一の書き込み口（AuditRecorder 相当）を通すこと**
7. `init` が生成する `config.yaml` / `strategy.md` / `rules.md` の中身と、`.media-agent/` が既に存在する場合の挙動
8. `doctor` の検査項目と各項目の合格条件（**認証情報の不在を異常としない**）、`status` の出力内容、`run` が Stage 0 で何を実行するか
9. 要件定義書14節（Security）への対応の詳細（`.gitignore` の対象と `doctor` での検証）
