# Stage 0 詳細設計 — Config / DB / Agent / Task / Policy / Logging・Audit

- 出所タスク: T-002（`docs/tasks/T-002.md`）
- 作成日: 2026-08-23
- 前提文書: `docs/design/stage0-architecture.md`（T-001 方式設計）。**本文書はその上に載る。矛盾する場合は方式設計が優先し、本文書の誤りとして扱う**
- 対象: 要件定義書 v0.2（`docs/requirements-media-agent-v0.2.md`）の **Stage 0 のみ**
- 読み手: T-003（受け入れテスト）、T-004〜T-007（実装）、T-008〜T-009（テスト・レビュー）
- 位置づけ: 設計成果物（組織の内側向け）。利用者向けドキュメントではない

---

## 1. 対象範囲

### 1.1 この設計がカバーする範囲

方式設計 20章「T-002 への申し送り」の9項目に対応する。

| # | 申し送り項目 | 本文書の章 |
| --- | --- | --- |
| 1 | Config Schema（スキーマ版数を含む） | 5章 |
| 2 | DB Schema と Migration 方式 | 6章 / 7章 |
| 3 | Agent Interface と検証用の組み込み Agent | 8章 |
| 4 | Task Model と許される状態遷移 | 9章 |
| 5 | Policy Model（`PolicyDecision` の値域） | 10章 |
| 6 | Logging / Audit の項目と書き分け | 11章 |
| 7 | `init` の生成物と、既存 `.media-agent/` がある場合の挙動 | 12章 |
| 8 | `doctor` の検査項目 / `status` の出力 / `run` の挙動 | 13章 / 14章 / 15章 |
| 9 | 要件定義書14節（Security）への対応 | 18章 |

あわせて、`agent list` / `task list` の出力（16章）、異常時の終了コードと**テストが判定してよい安定文字列**（17章）、
受け入れテスト S-A〜S-I への対応表（19章）を定める。

### 1.2 この設計がカバーしない範囲

**書かれていないことは決まっていない。** 推測で埋めないこと。

| 対象 | 扱い |
| --- | --- |
| Stage 1 以降の Agent（Content / Research / Strategy / Analytics / Engagement / Orchestrator） | 今回のゴール外 |
| X Connector / Google News / RSS / Web Connector、投稿処理、ダミー送信先 | 今回のゴール外（PO 制約 C-1〜C-3、要件定義書28節） |
| X API の利用方式 / AI 処理の実行方式 / Memory・Similarity 検索方式 / Package 配布方式 / Agent Plugin API | 今回のゴール外（T-001・T-002 の禁止事項） |
| Custom Agent の front matter 項目・ロード処理 | 方式設計9章で「設計のみ・Stage 0 では実装しない」と確定済み。**本文書でも実装を要求しない** |
| `.claude/` 連携の生成処理 | 方式設計8章。Stage 0 では実装しない |
| Scheduler / 定期実行 | 方式設計11.1。Stage 0 では置かない |
| Source / Post / Performance を**使う**機能 | Stage 1 以降。Stage 0 で作るのは**テーブルと Repository の器だけ**（6.1 の判断） |
| Config スキーマ版数 2 以降への移行処理 | 7.5。版数 1 しか存在しないため実装しない |

---

## 2. 前提・制約

**前提が崩れたら、この設計は無効になる。**

| # | 前提 | 崩れたときに影響する箇所 |
| --- | --- | --- |
| D-P1 | 方式設計（T-001）の技術選定が有効である（Python>=3.11 / Click / PyYAML + Pydantic v2 / 標準 `sqlite3` / pytest / Ruff / mypy / hatchling） | 全体 |
| D-P2 | Stage 0 に外部接続・認証情報・Action の実行先は存在しない（PO 制約 C-1〜C-3） | 10章（Policy は判定のみ）、13章（doctor が認証を検査しない）、18章 |
| D-P3 | 1つの `.media-agent/` に対して DB ファイルは1つであり、**同時に実行される Media Agent プロセスは1つ**である（CLI を人間または Claude Code が逐次呼ぶ利用像。要件定義書3.2節） | 6.7（同時実行の扱い）、10.5（上限判定に競合制御を入れない） |
| D-P4 | 方式設計 17.2 の順序制約 O-1 が有効。**DB の生成は `init` の実装（T-004）に埋め込まず、T-005 が1行足す** | 12.4、19章の S-A の判定対象 |
| D-P5 | 実装は T-004 → T-005 → T-006 → T-007 の順に直列で進む（`docs/handover.md`） | 20章 |
| D-P6 | 受け入れテスト（T-003）は、CLI（`click.testing.CliRunner`）と **`media_agent` の公開 API の両方**を呼んでよい。S-E / S-F / S-G / S-H は Core の機能であり、Stage 0 では CLI から全経路を観測できない | 19章 |

---

## 3. 本文書の記法

- **シグネチャは「決まっていること」を示すための記述であり、実装コードではない。** 引数名・戻り値の型・例外は設計として確定させる。関数の中身は実装エージェントの自律範囲
- 型は Python 3.11 の記法で書く（`str | None` 等）
- 表の「必須」は**利用者が `config.yaml` に書く義務があるか**を指す。既定値がある項目は任意
- **「安定文字列」** = 受け入れテストが `in` で判定してよい文字列。ここに挙げていない文言は、実装が自由に変えてよい（テストは判定に使わない）
- JSON のキー名・終了コード・状態名・`reason_code` は**すべて安定した契約**である。変更には設計変更の手続きが要る

---

## 4. モジュールと型の全体像

方式設計 5.1 のパッケージ構造に、本文書が定める型を割り付ける。

| モジュール | 主な公開物 | 実装タスク |
| --- | --- | --- |
| `media_agent/errors.py` | `MediaAgentError` とその派生（17.1） | T-004 |
| `media_agent/project/layout.py` | `ProjectLayout`, `find_project_root()`, `layout_for()` | T-004 |
| `media_agent/project/scaffold.py` | `init_project()`, `ScaffoldResult` | T-004 |
| `media_agent/project/templates/` | `config.yaml` / `strategy.md` / `rules.md` / `gitignore` の雛形（12.2） | T-004 |
| `media_agent/core/config/models.py` | `Config` ほか（5章） | T-004 |
| `media_agent/core/config/loader.py` | `load_config()`, `CONFIG_SCHEMA_VERSION` | T-004 |
| `media_agent/core/db/connection.py` | `connect()`, `open_project_db()` | T-005 |
| `media_agent/core/db/migrations.py` | `SCHEMA_VERSION`, `MIGRATIONS`, `ensure_schema()` | T-005 |
| `media_agent/core/db/repositories.py` | 6 Entity の Repository（6.6） | T-005 |
| `media_agent/core/observability/log.py` | `setup_logging()`, `get_logger()` | T-005 |
| `media_agent/core/observability/audit.py` | `AuditRecord`, `AuditRecorder` | T-005 |
| `media_agent/core/task/` | `TaskStatus`, `Task`, `ALLOWED_TRANSITIONS`, `TaskService` | T-006 |
| `media_agent/core/runtime/` | `Agent`, `AgentInput`, `AgentOutput`, `AgentContext`, `AgentRegistry`, `AgentRunner`, `TaskRunResult` | T-006 |
| `media_agent/core/policy/` | `PolicyRequest`, `PolicyDecision`, `PolicyOutcome`, `PolicyReasonCode`, `PolicyEngine` | T-006 |
| `media_agent/agents/builtin/` | `EchoAgent`, `FailAgent`, `build_default_registry()` | T-006 |
| `media_agent/cli/commands/` | `init` / `doctor` / `status` / `run` / `agent` / `task` / スタブ4種 | T-004（枠）・T-007（中身） |

### 4.1 `ProjectLayout`（Core を `.media-agent` から切り離す装置）

品質基準 Q7（`core/` に `.media-agent` の文字列を出さない）は、**パス解決を Project 層に閉じ込めることで機構的に守る**。

```python
@dataclass(frozen=True)
class ProjectLayout:
    root: Path              # プロジェクトルート（.media-agent/ を含むディレクトリ）
    base: Path              # <root>/.media-agent
    config_path: Path       # <base>/config.yaml
    strategy_path: Path     # <base>/strategy.md
    rules_path: Path        # <base>/rules.md
    agents_dir: Path        # <base>/agents
    memory_dir: Path        # <base>/memory
    data_dir: Path          # <base>/data
    db_path: Path           # <base>/data/media-agent.db
    logs_dir: Path          # <base>/logs
    log_path: Path          # <base>/logs/media-agent.log
    audit_path: Path        # <base>/logs/audit.jsonl
    gitignore_path: Path    # <base>/.gitignore

def layout_for(root: Path) -> ProjectLayout: ...
def find_project_root(start: Path) -> Path:
    """方式設計 6.3 の探索。見つからなければ ProjectNotInitializedError。"""
```

- `core/` の関数は `ProjectLayout` か個別の `Path` を**引数で受け取る**。自分で組み立てない
- 相対パスの表示（`init` / `doctor` / `status` の出力）は `root` からの相対で行う。区切りは常に `/`（`PurePosixPath` 化して表示する。Windows 差異を出力に持ち込まない）

---

## 5. Config Schema

### 5.1 ファイルと全体構造

- 場所: `<project>/.media-agent/config.yaml`（方式設計7章）
- パーサ: `yaml.safe_load` のみ（方式設計 3.3、罠 T-6）
- 検証: Pydantic v2 のモデル。**全モデルで `extra="forbid"`**
- 読み込み関数: `load_config(path: Path) -> Config`

```yaml
version: 1

project:
  name: "my-project"
  description: ""

media:
  primary_platform: x

content:
  posts_per_day: 3

automation:
  require_approval: false

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

limits:
  max_actions_per_hour: 10
  forbidden_topics: []
  forbidden_users: []

logging:
  level: info
```

### 5.2 項目表

トップレベル。

| キー | 型 | 必須 | 既定値 | 制約 |
| --- | --- | --- | --- | --- |
| `version` | int | 任意 | `1` | `1` のみ。`>= 2` は「サポートされていない版数」エラー。`<= 0` は範囲エラー |
| `project` | mapping | **必須** | — | 5.2.1 |
| `media` | mapping | 任意 | 既定値で構成 | 5.2.2 |
| `content` | mapping | 任意 | 既定値で構成 | 5.2.3 |
| `automation` | mapping | 任意 | 既定値で構成 | 5.2.4 |
| `actions` | mapping | 任意 | 5.2.5 の既定表 | キーは4種の Action 名のみ |
| `limits` | mapping | 任意 | 既定値で構成 | 5.2.6 |
| `logging` | mapping | 任意 | 既定値で構成 | 5.2.7 |

#### 5.2.1 `project`

| キー | 型 | 必須 | 既定値 | 制約 |
| --- | --- | --- | --- | --- |
| `project.name` | str | **必須** | — | 前後空白を除去して 1〜100 文字。空文字は不可 |
| `project.description` | str | 任意 | `""` | 0〜500 文字 |

**`project.name` が唯一の必須項目である。** 他は既定値で成立する。理由: 要件定義書8.2節の例で `project.name` だけが
プロジェクト固有の値であり、残りは Media Agent 側が妥当な既定を持てるため。**「必須項目の欠落」を試す受け入れテスト（S-I）は
`project.name` を落とす**のが正典。

#### 5.2.2 `media`

| キー | 型 | 必須 | 既定値 | 制約 |
| --- | --- | --- | --- | --- |
| `media.primary_platform` | str | 任意 | `"x"` | `x` のみ（Stage 0）。他の値は列挙外エラー |

拡張点: 対象プラットフォームが増えるのは Stage 8 以降（要件定義書22節）。列挙に値を足すだけで済むようにする。

#### 5.2.3 `content`

| キー | 型 | 必須 | 既定値 | 制約 |
| --- | --- | --- | --- | --- |
| `content.posts_per_day` | int | 任意 | `3` | `0 <= n <= 100` |

- `content.posts_per_day` は**戦略上の目標値**であり、`actions.post.max_per_day` は**Policy の上限値**である。両者は別物
- Stage 0 の Policy Engine は `content.posts_per_day` を参照しない。参照するのは `actions.post.max_per_day` だけ
- 両者が矛盾する（`posts_per_day > max_per_day`）場合は **`doctor` の `config.consistency` 検査が `warn`** を出す（13.2）。エラーにはしない

#### 5.2.4 `automation`

| キー | 型 | 必須 | 既定値 | 制約 |
| --- | --- | --- | --- | --- |
| `automation.require_approval` | bool | 任意 | `false` | — |

**意味**: `true` のとき、`deny` にならなかったすべての Action が `require_approval` になる（`mode: auto` より優先）。
要件定義書2.3節「すべてを最初から完全自動化しない」に対応する全体スイッチである。判定順序は 10.4。

#### 5.2.5 `actions`

キーは **`post` / `reply` / `repost` / `like` の4種のみ**（Stage 0）。それ以外のキーは列挙外エラー。

| キー | 型 | 必須 | 既定値 | 制約 |
| --- | --- | --- | --- | --- |
| `actions.<action>.mode` | str | **そのアクションのキーを書いた場合は必須** | — | `auto` / `approval` / `disabled` |
| `actions.<action>.max_per_day` | int \| null | 任意 | `null`（上限なし） | `>= 0` |
| `actions.<action>.max_per_hour` | int \| null | 任意 | `null`（上限なし） | `>= 0` |

`actions` セクション全体、または個々の Action キーが**省略された場合の既定**（要件定義書13節の例に一致させる）。

| Action | 既定 `mode` | 既定 `max_per_day` | 既定 `max_per_hour` |
| --- | --- | --- | --- |
| `post` | `auto` | `3` | `null` |
| `reply` | `approval` | `null` | `null` |
| `repost` | `approval` | `null` | `null` |
| `like` | `disabled` | `null` | `null` |

- **`mode` を必須にする理由**: `post: {}` と書いて黙って `auto` になるのは危険側の既定である。「書いたなら明示せよ、書かないなら安全な既定を使う」に統一する
- `max_per_day: 0` は「1日0回まで＝実質禁止」を意味する。`disabled` との違いは `reason_code`（`limit_exceeded_per_day` か `mode_disabled` か）に現れる

#### 5.2.6 `limits`

| キー | 型 | 必須 | 既定値 | 制約 |
| --- | --- | --- | --- | --- |
| `limits.max_actions_per_hour` | int \| null | 任意 | `10` | `>= 0`。全 Action 合計の1時間あたり上限 |
| `limits.forbidden_topics` | list[str] | 任意 | `[]` | 各要素 1〜100 文字。**大文字小文字を区別しない完全一致**で判定 |
| `limits.forbidden_users` | list[str] | 任意 | `[]` | 各要素 1〜100 文字。先頭の `@` を除去し、**大文字小文字を区別しない完全一致**で判定 |

要件定義書13節の「1日最大投稿数 / 1時間最大Action数 / 特定トピック禁止 / 特定ユーザーへのAction禁止 / Approval必須条件」は、
それぞれ `actions.<a>.max_per_day` / `limits.max_actions_per_hour`（および `actions.<a>.max_per_hour`）/ `limits.forbidden_topics` /
`limits.forbidden_users` / `automation.require_approval` に対応する。**5項目すべてに置き場所がある。**

#### 5.2.7 `logging`

| キー | 型 | 必須 | 既定値 | 制約 |
| --- | --- | --- | --- | --- |
| `logging.level` | str | 任意 | `"info"` | `debug` / `info` / `warning` / `error`（小文字のみ） |

**Audit の出力レベルは設定できない。** 監査記録は常に全件記録される（11.2）。

### 5.3 モデル定義（シグネチャ）

```python
class ActionMode(StrEnum):      # auto / approval / disabled
class ActionName(StrEnum):      # post / reply / repost / like
class LogLevel(StrEnum):        # debug / info / warning / error

class ActionPolicyConfig(BaseModel):   # model_config = ConfigDict(extra="forbid")
    mode: ActionMode
    max_per_day: int | None = None
    max_per_hour: int | None = None

class Config(BaseModel):
    version: int = 1
    project: ProjectConfig
    media: MediaConfig = MediaConfig()
    content: ContentConfig = ContentConfig()
    automation: AutomationConfig = AutomationConfig()
    actions: dict[ActionName, ActionPolicyConfig] = <5.2.5 の既定表>
    limits: LimitsConfig = LimitsConfig()
    logging: LoggingConfig = LoggingConfig()

CONFIG_SCHEMA_VERSION: int = 1

def load_config(path: Path) -> Config: ...
```

- `Config` は**不変として扱う**（`model_config = ConfigDict(frozen=True)`）。読み込み後に書き換える経路を作らない。Stage 0 に設定を書き戻す機能は無い
- `actions` が部分的に書かれている場合、**書かれていない Action だけ**既定表で補う（マージ）。書かれている Action は既定とマージしない（`mode` は必須のため欠落しない）

### 5.4 検証エラー時の挙動

| # | 事象 | 例外 | 終了コード | 安定文字列 |
| --- | --- | --- | --- | --- |
| C-1 | `config.yaml` が存在しない | `ConfigNotFoundError` | 4 | `config.yaml` と対象の絶対パス |
| C-2 | YAML として解析できない | `ConfigParseError` | 4 | `config.yaml` / `構文` / 行番号（PyYAML が示す場合） |
| C-3 | トップレベルが mapping でない（例: リスト・スカラ・空ファイル） | `ConfigParseError` | 4 | `config.yaml` / `構文` |
| C-4 | 必須項目が無い | `ConfigValidationError` | 4 | 欠落キーのキーパス（例 `project.name`） |
| C-5 | 型・値域・列挙違反 | `ConfigValidationError` | 4 | 違反キーのキーパス（例 `actions.post.mode`） |
| C-6 | 未知のキーがある | `ConfigValidationError` | 4 | 未知キーのキーパス（例 `projet`） |
| C-7 | `version >= 2` | `ConfigVersionError` | 4 | `version` / 実際の版数 / `1` |

- 例外はすべて `ConfigError` の派生であり、`ConfigError.exit_code = 4`（方式設計 6.5）
- **`doctor` だけは例外にせず検査結果 `fail` として扱い、終了コード 5 で終わる**（13.4）。理由: doctor は「異常を列挙する道具」であり、最初の1件で落ちると残りの検査結果が見えない
- **キーパスはドット区切りで、必ずメッセージに含める。** これがテストの判定対象である。日本語の文面は判定対象にしない

エラー出力の形（stderr）:

```
Error: config.yaml の検証に失敗しました (2 件): /abs/path/.media-agent/config.yaml
  - project.name: 必須項目がありません
  - actions.post.mode: 'autoo' は使用できません（auto / approval / disabled のいずれか）
Hint: media-agent doctor を実行すると、設定の問題をまとめて確認できます
```

- 件数は `(N 件)` の形で出す。複数の違反を**1件目で打ち切らない**（Pydantic は全件返す）
- 却下案: 1件目だけ表示して終了 → 直しては再実行を繰り返すことになる。設定ファイルの検証で最も避けたい体験である

---

## 6. DB Schema

### 6.1 対象と方針

- 方式: SQLite（標準 `sqlite3`）+ 手書き SQL の Repository 層（方式設計 3.4）
- ファイル: `<project>/.media-agent/data/media-agent.db`
- **要件定義書16節の6 Entity すべてのテーブルを Stage 0 で作る**（T-002 完了条件1 の指定どおり）。Stage 1 以降が使う Source / Post / Performance も器だけ先に作る
  - 却下案: Stage 0 で使う Task / Decision / Project だけ作る → Stage 1 の冒頭で Migration を書くことになり、**Migration 機構が「一度も本番で動いていない」状態のまま Stage 0 を完了させる**ことになる。器を先に作れば、Migration 機構は Stage 1 の追加列で初めて使われる
- 型は SQLite の型親和性に従い、**5種のみを使う**: `TEXT` / `INTEGER` / `REAL` / `TEXT`(JSON) / `TEXT`(ISO8601)

### 6.2 共通規約

| 項目 | 規約 |
| --- | --- |
| 主キー | すべて `TEXT`。値は `str(uuid.uuid4())`（36文字のハイフン付き小文字） |
| 時刻 | `TEXT`。**UTC の RFC3339**、マイクロ秒まで、末尾 `Z`。例 `2026-08-23T10:00:00.123456Z` |
| JSON 列 | `TEXT`。`json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))`。**`sort_keys=True` は再現性（要件20.5）のため必須** |
| 真偽値 | `INTEGER`（0/1）。Stage 0 では使用しない |
| NULL | 「まだ無い」を表す。空文字で代用しない |
| 外部キー | 明示的に宣言し、接続ごとに `PRAGMA foreign_keys = ON`（罠 T-2） |
| 削除 | Stage 0 に削除経路は無い。`ON DELETE` は `RESTRICT`（既定）に任せる |

時刻ユーティリティ（`core/db/connection.py` ではなく `core/clock.py` に置く）:

```python
def utcnow() -> datetime          # timezone-aware, UTC
def to_iso(dt: datetime) -> str   # 上記の形式へ
def from_iso(s: str) -> datetime
```

**時刻の取得は必ずこの関数を通す。** `datetime.now()`（naive）を直接呼ばない。テストが時刻を差し替えられるよう、
`AgentRunner` / `PolicyEngine` / `AuditRecorder` は `clock: Callable[[], datetime] = utcnow` を受け取る。

### 6.3 接続

```python
def connect(db_path: Path) -> sqlite3.Connection:
    """親ディレクトリを作成し、接続し、下記 PRAGMA を適用する。"""

def open_project_db(layout: ProjectLayout, config: Config | None = None) -> sqlite3.Connection:
    """connect + ensure_schema (+ config があれば ProjectRepository.sync)。"""
```

接続ごとに適用する PRAGMA:

| PRAGMA | 値 | 理由 |
| --- | --- | --- |
| `foreign_keys` | `ON` | SQLite の既定は OFF。外部キーが黙って効かない（罠 T-2） |
| `journal_mode` | `WAL` | 読み書きの競合を減らす。ローカル単一ファイルでの標準的な選択 |
| `synchronous` | `NORMAL` | WAL と組み合わせた既定的な組み合わせ |
| `busy_timeout` | `5000`（ms） | 別プロセスが書き込み中のときに即座に失敗させない |

- `row_factory = sqlite3.Row`（列名でアクセスする。位置参照を書かない）
- **`detect_types` を使わない。** 時刻は 6.2 の文字列として扱い、変換は Repository が行う。sqlite3 の暗黙変換に依存しない

### 6.4 DDL（スキーマ版数 1）

```sql
CREATE TABLE projects (
    project_id    TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    configuration TEXT NOT NULL,              -- JSON: 検証済み Config のスナップショット
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE sources (
    source_id    TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    url          TEXT,
    source_type  TEXT NOT NULL,               -- 'rss' | 'news' | 'web' | 'x' | 'manual'（Stage 2 で拡張）
    content      TEXT,
    collected_at TEXT NOT NULL,
    score        REAL
);
CREATE INDEX idx_sources_collected_at ON sources (collected_at);
CREATE INDEX idx_sources_url          ON sources (url);

CREATE TABLE posts (
    post_id      TEXT PRIMARY KEY,
    content      TEXT NOT NULL,
    topic        TEXT,
    source_id    TEXT REFERENCES sources (source_id),
    status       TEXT NOT NULL
        CHECK (status IN ('draft','approved','scheduled','published','rejected','failed')),
    created_at   TEXT NOT NULL,
    scheduled_at TEXT,
    published_at TEXT
);
CREATE INDEX idx_posts_status       ON posts (status);
CREATE INDEX idx_posts_created_at   ON posts (created_at);
CREATE INDEX idx_posts_published_at ON posts (published_at);

CREATE TABLE performances (
    performance_id TEXT PRIMARY KEY,
    post_id        TEXT NOT NULL REFERENCES posts (post_id),
    impressions    INTEGER,
    likes          INTEGER,
    replies        INTEGER,
    reposts        INTEGER,
    collected_at   TEXT NOT NULL,
    UNIQUE (post_id, collected_at)
);
CREATE INDEX idx_performances_post_id ON performances (post_id);

CREATE TABLE tasks (
    task_id      TEXT PRIMARY KEY,
    agent        TEXT NOT NULL,
    type         TEXT NOT NULL,               -- Stage 0 は 'agent_run' のみ
    status       TEXT NOT NULL
        CHECK (status IN ('pending','running','completed','failed','cancelled')),
    input        TEXT NOT NULL,               -- JSON
    output       TEXT,                        -- JSON
    error        TEXT,
    created_at   TEXT NOT NULL,
    started_at   TEXT,
    completed_at TEXT
);
CREATE INDEX idx_tasks_status     ON tasks (status);
CREATE INDEX idx_tasks_created_at ON tasks (created_at);
CREATE INDEX idx_tasks_agent      ON tasks (agent);

CREATE TABLE decisions (
    decision_id TEXT PRIMARY KEY,
    kind        TEXT NOT NULL
        CHECK (kind IN ('agent_run','policy_check')),
    agent       TEXT NOT NULL,
    task_id     TEXT REFERENCES tasks (task_id),
    input       TEXT NOT NULL,                -- JSON
    decision    TEXT NOT NULL,
    reason      TEXT NOT NULL,
    action      TEXT,
    result      TEXT,                         -- JSON
    error       TEXT,
    timestamp   TEXT NOT NULL
);
CREATE INDEX idx_decisions_timestamp ON decisions (timestamp);
CREATE INDEX idx_decisions_task_id   ON decisions (task_id);
CREATE INDEX idx_decisions_kind_action_ts ON decisions (kind, action, timestamp);
```

要件定義書16節との差分（**すべて追加であり、削除は無い**）:

| テーブル | 差分 | 理由 |
| --- | --- | --- |
| `posts` | `source` → `source_id`（sources への外部キー） | 要件の `source` は関連そのもの。列名に `_id` を付けて外部キーであることを型で示す |
| `performances` | 代理主キー `performance_id` と `UNIQUE(post_id, collected_at)` | Metrics は同じ投稿に対して時系列で複数回集まる。他テーブルと主キーの形を揃える |
| `tasks` | `started_at` / `error` を追加 | `pending`→`running`→`completed` の遷移時刻を観測可能にする（S-F）。失敗理由を Task 自身が持たないと `task list` で失敗を説明できない |
| `decisions` | `kind` / `task_id` / `action` / `result` / `error` を追加 | **要件定義書5.5節の Audit 9項目を、この1テーブルで完全に満たすため**（11.3）。要件16節の Decision は「最低限」の列挙である |

**`decisions` は Decision Entity であると同時に Audit の永続面である。** 2つの表を作らない。
却下案: `audit_records` テーブルを別に作る → 同じ事実が2か所に書かれ、どちらが正か決められなくなる。要件16節の Decision も残るため二重管理になる。

### 6.5 `projects` テーブルの扱い

- Stage 0 の DB は**1プロジェクトにつき1ファイル**であるため、`projects` は**高々1行**である
- この単一行制約は **Repository が保証する**（DB 制約を置かない）。理由: 将来「1つの DB に複数プロジェクト」を許す可能性を、いま塞ぐ必要が無い
- `ProjectRepository.sync(config)`: 行が無ければ `project_id` を採番して挿入。あれば `name` / `configuration` が変化したときだけ `updated_at` とともに更新する
- `configuration` は**検証済み `Config` の JSON スナップショット**（`config.model_dump(mode="json")` 相当）。要件20.5（再現性）のため、「そのとき何の設定で動いたか」を DB から辿れるようにする
- 呼び出し箇所: `init` / `run` / `status`（`open_project_db` に config を渡した場合）。**`doctor` は呼ばない**（13.1 の副作用禁止）

### 6.6 Repository（シグネチャ）

すべて `sqlite3.Connection` を受け取り、**トランザクションの境界は呼び出し側が持つ**（`with conn:`）。

```python
class ProjectRepository:
    def sync(self, config: Config) -> ProjectRow
    def get(self) -> ProjectRow | None

class SourceRepository:
    def add(self, *, title: str, source_type: str, url: str | None = None,
            content: str | None = None, score: float | None = None,
            collected_at: datetime | None = None) -> SourceRow
    def get(self, source_id: str) -> SourceRow | None
    def list(self, *, limit: int = 50) -> list[SourceRow]

class PostRepository:
    def add(self, *, content: str, status: str = "draft", topic: str | None = None,
            source_id: str | None = None, scheduled_at: datetime | None = None) -> PostRow
    def get(self, post_id: str) -> PostRow | None
    def list(self, *, status: str | None = None, limit: int = 50) -> list[PostRow]
    def set_status(self, post_id: str, status: str, *, published_at: datetime | None = None) -> PostRow

class PerformanceRepository:
    def add(self, *, post_id: str, impressions: int | None = None, likes: int | None = None,
            replies: int | None = None, reposts: int | None = None,
            collected_at: datetime | None = None) -> PerformanceRow
    def list_for_post(self, post_id: str) -> list[PerformanceRow]

class TaskRepository:
    def add(self, *, agent: str, type: str, input: dict[str, Any]) -> TaskRow   # status='pending'
    def get(self, task_id: str) -> TaskRow | None
    def update_status(self, task_id: str, *, status: str, output: dict[str, Any] | None = None,
                      error: str | None = None, started_at: datetime | None = None,
                      completed_at: datetime | None = None) -> TaskRow
    def list(self, *, status: str | None = None, limit: int = 20) -> list[TaskRow]   # created_at DESC
    def count_by_status(self) -> dict[str, int]                                      # 5状態すべてのキーを返す

class DecisionRepository:
    def add(self, record: AuditRecord) -> str                                        # returns decision_id
    def list(self, *, task_id: str | None = None, kind: str | None = None,
             limit: int = 50) -> list[DecisionRow]
    def count_allowed_actions(self, *, action: str, since: datetime,
                              until: datetime | None = None) -> int
```

- `count_allowed_actions` は `kind='policy_check' AND decision='allow' AND action=? AND timestamp >= ?` を数える（10.5）
- `action=None` を渡すと全 Action の合計を数える（`limits.max_actions_per_hour` 用）。シグネチャ上は `action: str | None`
- 戻り値の `*Row` は Pydantic モデル（frozen）。**`sqlite3.Row` をモジュールの外へ出さない。** 外へ出すと DB 方式の差し替え（拡張点 E-2）が呼び出し側へ波及する

### 6.7 同時実行

- 前提 D-P3 により、Stage 0 では同時実行を設計上考慮しない
- ただし `busy_timeout` と WAL により、たまたま2プロセスが重なっても即座に壊れないようにする
- **上限判定（10.5）に競合制御（ロック・悲観制御）を入れない。** Stage 0 に Action の実行が無い以上、判定と実行の間の競合という概念が存在しない。Stage 3 で Action を実装するときに、この前提を必ず見直すこと（拡張点 E-4）

---

## 7. Migration 方式

### 7.1 決定

**`PRAGMA user_version` を版数の保持先とし、前進のみの連番 Migration をコード内の一覧で管理する。**

```python
SCHEMA_VERSION: int = 1

@dataclass(frozen=True)
class Migration:
    version: int          # 適用後の版数
    description: str
    statements: tuple[str, ...]

MIGRATIONS: tuple[Migration, ...] = (
    Migration(version=1, description="Stage 0 の6 Entity を作成する", statements=(...6.4 の DDL...)),
)

def ensure_schema(conn: sqlite3.Connection) -> int:
    """現在の user_version から SCHEMA_VERSION まで、未適用の Migration を順に適用し、適用後の版数を返す。"""
```

### 7.2 手順

1. `PRAGMA user_version` を読む（新規ファイルは `0`）
2. `current > SCHEMA_VERSION` なら `DatabaseVersionError` を送出する（**新しい DB を古い実装で開いた場合。壊さずに止める**）
3. `current < SCHEMA_VERSION` の間、`version == current + 1` の Migration を**1つのトランザクションで**適用し、末尾で `PRAGMA user_version = <version>` を設定する
4. 何も適用しなかった場合を含め、適用後の版数を返す

### 7.3 満たす性質

| 性質 | どう満たすか |
| --- | --- |
| **何度実行しても壊れない**（T-005 完了条件3） | 版数が一致していれば SQL を1つも実行しない。`CREATE TABLE IF NOT EXISTS` に頼らない |
| 部分適用が残らない | Migration ごとに1トランザクション。失敗したら版数も更新されない |
| 版数を DB 自身が持つ | `PRAGMA user_version`（方式設計 3.4 補足の制約） |
| アプリ版数から独立 | `SCHEMA_VERSION` はパッケージ版数と別（方式設計12章） |

### 7.4 却下案

| 却下案 | 却下理由 |
| --- | --- |
| Alembic | SQLAlchemy が前提。方式設計 3.4 で ORM を却下済み。単独では使えない |
| 独自の `schema_migrations` テーブル | 「テーブルが無い状態」を扱うための分岐が最初に必要になる。`user_version` は DB ヘッダの一部で、テーブルが1つも無くても読める |
| `CREATE TABLE IF NOT EXISTS` だけ | 列の追加・変更を表現できない。**既存 DB がどの形かを判定できないまま実装が進む**ため、Stage 1 で必ず行き詰まる |
| `.sql` ファイルをパッケージデータとして同梱 | テンプレート（罠 T-4）と同じ資源読み込みの問題を DB 層にも持ち込む。Migration は SQL 文字列の並びであれば足り、型チェックの対象にもなる |
| 版数を `config.yaml` に持たせる | 設定ファイルを消したり編集したりすると DB の実体と食い違う。**DB の状態は DB が持つ** |

### 7.5 Config スキーマの移行

- `config.version` は DB 版数とは独立（方式設計12章）
- Stage 0 に存在する版数は `1` のみであるため、**移行処理は実装しない**
- 将来 `2` を作るときの方式だけ決めておく: `load_config` が `version` を見て、`1 → 2` の変換関数を適用してから検証する。**利用者のファイルを自動で書き換えない**（読み込み時に変換するだけ）。書き換えは `media-agent config migrate` 相当の明示的なコマンドで行う（Stage 8 以降）

---

## 8. Agent Interface

### 8.1 型

```python
class AgentInput(BaseModel):            # frozen
    payload: dict[str, Any] = {}        # JSON 化できる値のみ

class AgentOutput(BaseModel):           # frozen
    payload: dict[str, Any] = {}        # JSON 化できる値のみ
    decision: str                       # 必須。何を判断したか（1行、120文字以内）
    reason: str                         # 必須。なぜそう判断したか

@dataclass(frozen=True)
class AgentContext:
    project_root: Path                  # ProjectLayout ではなく root だけを渡す（Q7）
    config: Config
    task_id: str
    logger: logging.Logger

class Agent(ABC):
    name: ClassVar[str]                 # ^[a-z][a-z0-9-]{0,31}$
    version: ClassVar[int]              # 1 以上。Agent の実装が変わったら上げる（要件20.5）
    description: ClassVar[str]

    @abstractmethod
    def run(self, input: AgentInput, ctx: AgentContext) -> AgentOutput: ...
```

- **`decision` と `reason` を Agent の戻り値に含めるのが本設計の要点である。** 要件定義書5.5節が Audit に `decision` / `reason` を要求している以上、
  それを知っているのは Agent 自身しかない。戻り値に無いと、Runner が推測で埋めるか、空欄になる
- `AgentContext` に DB 接続・Repository・AuditRecorder を**渡さない**。Agent は自分で永続化しない（要件2.4「Decision と Action を分離」、品質基準 Q9）。
  記録するのは Runner の責務
- `AgentContext.project_root` は Stage 1 以降で Agent が `.media-agent/memory/` 等を読むための足場。Stage 0 の組み込み Agent は使わない
- 却下案: `typing.Protocol` による構造的部分型 → 登録時に「Agent として妥当か」を実行時に確認できず、`name` / `version` の欠落が実行時まで判明しない。
  ABC なら `issubclass` と抽象メソッドで登録時に弾ける
- 却下案: `run(self, **kwargs) -> dict` のような素の辞書 → 入出力の形が Agent ごとにばらつき、Audit の項目が Agent 依存になる

### 8.2 Registry

```python
class AgentRegistry:
    def register(self, agent: Agent) -> None
    def get(self, name: str) -> Agent
    def names(self) -> list[str]              # 名前の昇順
    def all(self) -> list[Agent]              # 名前の昇順
    def __contains__(self, name: str) -> bool
    def __len__(self) -> int

def build_default_registry() -> AgentRegistry:
    """組み込み Agent（8.4）だけを登録した Registry を返す。"""
```

| 事象 | 挙動 |
| --- | --- |
| 同じ `name` を2回登録 | `DuplicateAgentError`（`MediaAgentError`、終了コード 1） |
| `name` が命名規則に合わない | `InvalidAgentError`（同上） |
| 未登録の名前で `get` | `AgentNotFoundError`（同上）。メッセージに**要求した名前**と**登録済みの名前一覧**を含める |
| `register` に `Agent` の派生でないものを渡す | `InvalidAgentError` |

- **Custom Agent（`.media-agent/agents/*.md`）は Stage 0 では読み込まない**（方式設計9章、T-006 完了条件7）。
  `build_default_registry()` は組み込み Agent だけを返す。将来 Project 層がこの Registry へ追加登録する（拡張点 E-6）

### 8.3 Runner

```python
@dataclass(frozen=True)
class TaskRunResult:
    task: Task
    output: AgentOutput | None      # 失敗時 None
    error: str | None               # 失敗時 "<例外クラス名>: <メッセージ>"（1行）

class AgentRunner:
    def __init__(self, *, registry: AgentRegistry, tasks: TaskService,
                 audit: AuditRecorder, logger: logging.Logger,
                 config: Config, project_root: Path,
                 clock: Callable[[], datetime] = utcnow) -> None: ...

    def run(self, agent_name: str, payload: dict[str, Any] | None = None,
            *, task_type: str = "agent_run") -> TaskRunResult: ...
```

`run()` の手順（**この順序が S-F / S-H の期待値である**）:

1. `registry.get(agent_name)`（未登録なら `AgentNotFoundError` を送出する。**Task は作らない**）
2. `tasks.create(agent=..., type=task_type, input=payload or {})` → `status='pending'`
3. `tasks.transition(task_id, TaskStatus.running)` → `started_at` を記録
4. 運用ログへ `INFO agent=... task=... started`
5. `agent.run(AgentInput(payload=...), AgentContext(...))` を呼ぶ
6. 正常終了時:
   1. `tasks.transition(task_id, TaskStatus.completed, output=output.payload)` → `completed_at`
   2. `audit.record_agent_run(...)`（`decision` / `reason` / `result` は Agent の戻り値、`error=None`）
   3. 運用ログへ `INFO ... completed`
7. `Exception` を捕捉した場合:
   1. `tasks.transition(task_id, TaskStatus.failed, error="<例外クラス名>: <メッセージ>")` → `completed_at`
   2. `audit.record_agent_run(...)`（`decision="error"`、`reason="<例外クラス名>: <メッセージ>"`、`result=None`、`error` に同じ1行）
   3. 運用ログへ `ERROR ... failed`（**トレースバックは運用ログにだけ出す**。Audit には出さない）
   4. **例外を再送出しない**（T-006 完了条件2「例外がそのまま外へ漏れない」）
8. `TaskRunResult` を返す

- 捕捉するのは `Exception` であり、`BaseException`（`KeyboardInterrupt` / `SystemExit`）は捕捉しない。**利用者の中断を握り潰さない**
- 手順2〜3で失敗した場合（DB 障害等）は例外がそのまま外へ出る。これは Agent の失敗ではなく基盤の失敗であり、Task に記録する手段自体が無い
- 却下案: 失敗時に例外を送出する → 呼び出し側が毎回 try/except を書くことになり、書き忘れた経路で Task が `running` のまま残る

### 8.4 組み込み Agent（検証用）

| name | version | description | 挙動 |
| --- | --- | --- | --- |
| `echo` | 1 | 入力をそのまま返す検証用の組み込み Agent | `AgentOutput(payload=<入力 payload をそのまま>, decision="echo", reason="組み込みの検証用 Agent のため、入力をそのまま返した")` |
| `fail` | 1 | 常に失敗する検証用の組み込み Agent | `AgentFailedForVerificationError("検証用 Agent 'fail' は常に失敗します")` を送出する |

- **`fail` を製品に同梱する理由**: 異常系（Task が `failed` になる、Audit に `error` が残る）を、**受け入れテストが製品コードを書かずに CLI から確認できる**ようにするため（T-003 の禁止事項と両立させる）
- `fail` は `agent list` にも表示する。隠すと「登録されている Agent の一覧」が実体と食い違う
- どちらも **AI を呼ばない・ネットワークへ出ない・ファイルを書かない**（PO 制約 C-1〜C-3、品質基準 Q6・Q9）
- `AgentFailedForVerificationError` は `MediaAgentError` の派生ではなく **`RuntimeError` の派生**とする。理由: Runner が「Agent が投げた任意の例外」を扱えることを、組み込み Agent 自身で検証するため

---

## 9. Task Model

### 9.1 型

```python
class TaskStatus(StrEnum):
    pending = "pending"; running = "running"; completed = "completed"
    failed = "failed"; cancelled = "cancelled"

class Task(BaseModel):          # frozen
    task_id: str
    agent: str
    type: str                   # Stage 0 は "agent_run"
    status: TaskStatus
    input: dict[str, Any]
    output: dict[str, Any] | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @property
    def is_terminal(self) -> bool
```

### 9.2 許される状態遷移

```
              ┌──────────────┐
              │   pending    │  ← 生成直後（TaskService.create）
              └──┬────────┬──┘
       start     │        │     cancel
                 ▼        ▼
          ┌───────────┐  ┌────────────┐
          │  running  │  │ cancelled  │（終端）
          └──┬─────┬──┘  └────────────┘
    complete │     │ fail
             ▼     ▼
   ┌───────────┐  ┌──────────┐
   │ completed │  │  failed  │（いずれも終端）
   └───────────┘  └──────────┘
```

| # | 遷移前 | 遷移後 | 許可 | 付随して記録するもの |
| --- | --- | --- | --- | --- |
| 1 | （無） | `pending` | 生成 | `created_at` |
| 2 | `pending` | `running` | **許可** | `started_at` |
| 3 | `pending` | `cancelled` | **許可** | `completed_at` |
| 4 | `running` | `completed` | **許可** | `output`, `completed_at` |
| 5 | `running` | `failed` | **許可** | `error`, `completed_at` |
| 6 | `running` | `cancelled` | **禁止**（Stage 0） | — |
| 7 | `pending` | `completed` / `failed` | **禁止** | — |
| 8 | `completed` / `failed` / `cancelled` からのすべて | **禁止** | — |
| 9 | 同じ状態への遷移（`running`→`running` 等） | **禁止** | — |

**上の表に無い遷移はすべて禁止である。** 禁止された遷移を要求したら `InvalidTaskTransitionError`（`MediaAgentError`、終了コード 1）を送出し、
**DB を書き換えない**（検査は書き込みより前）。メッセージには遷移元と遷移先を含める（安定文字列: `pending` `running` 等の状態名と `task_id`）。

- **`running` → `cancelled` を Stage 0 で禁止する理由**: Stage 0 の Agent 実行は同一プロセス内の同期呼び出しであり、
  走っている Agent を中断する手段が存在しない。許すと「`cancelled` と記録されているのに Agent は最後まで動いた」状態を作れてしまう。
  却下案: 許可して「中断要求」の意味にする → 状態名と実態が食い違う。Scheduler / 非同期実行（Stage 3 以降）が入った時点で、
  中断機構と**同時に**解禁する（拡張点 E-9）
- `completed_at` は `completed` だけでなく **`failed` / `cancelled` でも設定する**。「終端に達した時刻」を意味する。
  要件定義書16節は `completed_at` しか挙げていないが、失敗した Task の終了時刻が残らないと `task list` で経過が説明できない

### 9.3 TaskService

```python
class TaskService:
    def __init__(self, repo: TaskRepository, *, clock: Callable[[], datetime] = utcnow) -> None
    def create(self, *, agent: str, type: str, input: dict[str, Any]) -> Task
    def transition(self, task_id: str, to: TaskStatus, *,
                   output: dict[str, Any] | None = None,
                   error: str | None = None) -> Task
    def get(self, task_id: str) -> Task
    def list(self, *, status: TaskStatus | None = None, limit: int = 20) -> list[Task]
    def counts(self) -> dict[TaskStatus, int]

ALLOWED_TRANSITIONS: Mapping[TaskStatus, frozenset[TaskStatus]]   # 9.2 の表そのもの
```

- **状態遷移の判定は `ALLOWED_TRANSITIONS` の一箇所だけで行う。** 呼び出し側に `if status == ...` を書かない
- `transition` の引数不整合（`completed` なのに `output=None`、`failed` なのに `error=None`）は許す。**Agent が出力を返さないこともある**ため。
  ただし `failed` で `error=None` の場合は `error="unknown error"` を補う（Audit の `error` 項目が空になるのを防ぐ）

---

## 10. Policy Model

### 10.1 位置づけ

- 要件定義書2.4節「Agent Decision → Policy Check → Action → External Service」の **Policy Check の部分だけ**を Stage 0 で作る
- **Stage 0 に Action の実行先は存在しない。** Policy Engine は判定結果を返し、判定を Audit へ記録する。それ以上のことはしない（T-002 完了条件1）
- `media-agent run` は Policy Check を**呼ばない**（15.4 に理由）

### 10.2 型

```python
class PolicyOutcome(StrEnum):
    allow = "allow"
    require_approval = "require_approval"
    deny = "deny"

class PolicyReasonCode(StrEnum):
    mode_auto               = "mode_auto"                # allow
    mode_approval           = "mode_approval"            # require_approval
    global_approval_required= "global_approval_required" # require_approval
    mode_disabled           = "mode_disabled"            # deny
    limit_exceeded_per_day  = "limit_exceeded_per_day"   # deny
    limit_exceeded_per_hour = "limit_exceeded_per_hour"  # deny
    topic_forbidden         = "topic_forbidden"          # deny
    user_forbidden          = "user_forbidden"           # deny
    unknown_action          = "unknown_action"           # deny

class PolicyRequest(BaseModel):     # frozen
    action: str                     # ActionName の値。未知の文字列も受け取る（unknown_action で返すため）
    topic: str | None = None
    target_user: str | None = None
    requested_by: str = "policy-engine"    # 呼び出し元 Agent 名。Audit の agent 項目になる
    task_id: str | None = None
    requested_at: datetime | None = None   # None なら clock() を使う

class PolicyDecision(BaseModel):    # frozen
    outcome: PolicyOutcome
    reason_code: PolicyReasonCode
    message: str                    # 人間向け。テストの判定対象にしない
    detail: dict[str, Any] = {}     # 例: {"limit": 3, "observed": 3, "window": "24h"}
```

**`outcome` と `reason_code` は独立した2軸である**（用語集「PolicyDecision」）。`outcome` は「どうするか」、`reason_code` は「なぜか」。
`reason_code` から `outcome` は一意に決まるが、逆は決まらない。

### 10.3 4通り（受け入れテスト S-G の判定対象）

| 区分 | `outcome` | `reason_code` | 発生させる設定 |
| --- | --- | --- | --- |
| 許可 | `allow` | `mode_auto` | `actions.post.mode: auto` かつ上限未達、`automation.require_approval: false` |
| 承認が必要 | `require_approval` | `mode_approval` | `actions.reply.mode: approval` |
| 禁止 | `deny` | `mode_disabled` | `actions.like.mode: disabled` |
| 上限超過 | `deny` | `limit_exceeded_per_day` | `actions.post.mode: auto` かつ `max_per_day: N` に対して直近24時間の `allow` が N 件以上 |

**「禁止」と「上限超過」はどちらも `outcome=deny` であり、`reason_code` でのみ区別できる。** これが2要素にした理由である。

### 10.4 判定順序

`PolicyEngine.check()` は**必ずこの順で評価し、最初に該当した規則で確定する**。

| 順 | 条件 | 結果 |
| --- | --- | --- |
| 1 | `request.action` が `ActionName` の4値のいずれでもない | `deny` / `unknown_action` |
| 2 | 当該 Action の `mode == disabled` | `deny` / `mode_disabled` |
| 3 | `topic` が `limits.forbidden_topics` に一致（大文字小文字を無視した完全一致、前後空白は除去） | `deny` / `topic_forbidden` |
| 4 | `target_user` が `limits.forbidden_users` に一致（先頭 `@` を除去し、大文字小文字を無視した完全一致） | `deny` / `user_forbidden` |
| 5 | `max_per_day` が設定されており、直近24時間の当該 Action の `allow` 件数 `>= max_per_day` | `deny` / `limit_exceeded_per_day` |
| 6 | `max_per_hour`（Action 個別）または `limits.max_actions_per_hour`（全 Action 合計）が設定されており、直近1時間の該当件数が上限以上 | `deny` / `limit_exceeded_per_hour` |
| 7 | `automation.require_approval == true` | `require_approval` / `global_approval_required` |
| 8 | 当該 Action の `mode == approval` | `require_approval` / `mode_approval` |
| 9 | 上記のいずれでもない（`mode == auto`） | `allow` / `mode_auto` |

- **順序を固定する理由**: 同じ設定で違う結果が出ないようにするため。実装ごとに順序が違うと、テストは通るのに挙動が説明できなくなる
- **禁止（2〜6）が承認（7〜8）より先である。** 承認を求めれば通るのか、そもそも通らないのかを混同しないため。
  却下案: `require_approval` を先に評価する → 「承認すれば禁止トピックを投稿できる」という設計になってしまい、要件13節の「特定トピック禁止」が骨抜きになる
- 6 で Action 個別と全体の両方が上限に達している場合、`detail` には**先に評価した Action 個別**の値を入れる

### 10.5 上限の数え方

- **窓は「判定時刻からさかのぼる固定長」**（ローリングウィンドウ）。`per_day` = 24時間、`per_hour` = 1時間
  - 却下案: カレンダー日（0時区切り） → 利用者のタイムゾーンに依存し、`config.yaml` にタイムゾーン項目を増やすことになる。
    UTC 固定にすると「日本時間の朝に上限が切り替わらない」という説明のつかない挙動になる
- 数える対象は **`decisions` テーブルの `kind='policy_check'` かつ `decision='allow'` の記録**（`DecisionRepository.count_allowed_actions`）
- **Stage 0 では「許可された回数」を「実行された回数」の代理とする。** Stage 0 に Action の実行が無いため、これ以外に数えられる事実が無い。
  Stage 3 で Action を実装したら、**実行された Action を数える**ように差し替える（拡張点 E-4）。この差し替え点は `count_allowed_actions` の1メソッドに閉じている
- したがって `check()` は**既定で判定を記録する**（記録が上限判定の入力になるため、記録しないと上限が永遠に来ない）

### 10.6 PolicyEngine

```python
class PolicyEngine:
    def __init__(self, *, config: Config, decisions: DecisionRepository,
                 audit: AuditRecorder, clock: Callable[[], datetime] = utcnow) -> None
    def check(self, request: PolicyRequest, *, record: bool = True) -> PolicyDecision
```

- `record=True`（既定）: 判定結果を **AuditRecorder 経由で** `kind='policy_check'` として記録する（11.3）。この記録が 10.5 の計数対象になる
- `record=False`: 記録しない。**計数にも影響しない。** 「いま判定したらどうなるか」を副作用なく調べる用途（`doctor` の `policy.config` 検査など）
- Policy Engine は `config` を**受け取るだけ**であり、自分で `config.yaml` を読まない（方式設計 17.2 の O-3、T-006 完了条件5）
- `PolicyEngine` は例外を投げない（未知の Action も `deny` として返す）。**判定は必ず `PolicyDecision` で表現する**
- `PolicyDeniedError`（終了コード 6）は、**Action の実行経路が `deny` を受け取ったときに送出する例外**である。Stage 0 には実行経路が無いため、
  この例外は定義するだけで送出箇所を持たない。定義しておく理由は方式設計 6.5 の終了コード表を Stage 3 で変えずに済ませるため

---

## 11. Logging / Audit

### 11.1 Logger と Audit は別物である

| 観点 | 運用ログ（Logger） | 監査記録（Audit） |
| --- | --- | --- |
| 目的 | 人間が動作を追う・障害を切り分ける | AI の判断を追跡し、再現できるようにする（要件20.3・20.5） |
| 出力先 | `.media-agent/logs/media-agent.log` と stderr | `.media-agent/logs/audit.jsonl` と `decisions` テーブル |
| 形式 | 1行のテキスト | JSON Lines / リレーショナルな行 |
| 書き込み口 | 標準ライブラリ `logging` | **`AuditRecorder` ただ1つ** |
| レベルによる抑制 | **する**（`logging.level`） | **しない。常に全件記録する** |
| 欠落 | 許容する | 許容しない |
| ローテーション | **する**（1 MiB × 3世代） | **しない**（追記専用） |
| トレースバック | 出す | **出さない**（1行の `error` のみ） |
| 秘密値 | 出さない | 出さない（11.4 のマスク） |
| 正本 | ファイルが正本 | **`decisions` テーブルが正本**、`audit.jsonl` は写し |

**この表が「別物として実装されている」（T-005 完了条件6）の判定基準である。**

却下案: Audit を運用ログの1レベル（`AUDIT` レベル等）として実装する → `logging.level` の設定で監査記録が消える経路が生まれる。
監査記録が設定で消せるなら、それは監査記録ではない。

### 11.2 Logger

```python
def setup_logging(*, level: LogLevel = LogLevel.info, log_path: Path | None = None,
                  verbose: bool = False, quiet: bool = False) -> None
def get_logger(name: str) -> logging.Logger      # logging.getLogger(f"media_agent.{name}")
```

| 項目 | 決定 |
| --- | --- |
| ルートロガー名 | `media_agent`（アプリのロガーはすべてこの配下） |
| ファイル出力 | `RotatingFileHandler(log_path, maxBytes=1_048_576, backupCount=3, encoding="utf-8")`。レベルは `logging.level` |
| ファイル書式 | `%(asctime)s %(levelname)-8s %(name)s %(message)s`、`asctime` は UTC の 6.2 形式 |
| stderr 出力 | 既定 `WARNING` 以上。`-v/--verbose` で `DEBUG` 以上。`-q/--quiet` で `ERROR` 以上 |
| stderr 書式 | `%(levelname)s: %(message)s`（時刻を出さない。人が読む前提） |
| ハンドラ追加の時機 | **プロジェクトルートが解決できた後**にファイルハンドラを追加する。解決前のログは stderr のみ |
| 伝播 | `media_agent` ロガーの `propagate = False`。ルートロガーへ二重に流さない |
| ライブラリのログ | 他パッケージのロガーには触れない |

- ログ本文には **`task_id` / `agent` / `action` を `key=value` 形式で含める**（例: `agent=echo task=6f1c... started`）。
  行の grep で追跡できるようにするため
- 却下案: `TimedRotatingFileHandler`（日次） → Stage 0 の実行回数では日次ファイルの大半が空になる。サイズ基準のほうが実態に合う
- 却下案: 回転しない → ローカルのディスクを黙って埋める。運用ログは「消えてよい」記録である

### 11.3 Audit

```python
class AuditRecord(BaseModel):           # frozen
    timestamp: datetime
    agent: str
    task: str | None                    # task_id
    input: dict[str, Any]
    decision: str
    reason: str
    action: str | None
    result: dict[str, Any] | None
    error: str | None
    kind: Literal["agent_run", "policy_check"]
    decision_id: str

class AuditRecorder:
    def __init__(self, *, decisions: DecisionRepository, audit_path: Path,
                 logger: logging.Logger, clock: Callable[[], datetime] = utcnow) -> None
    def record(self, record: AuditRecord) -> AuditRecord            # 唯一の書き込み口
    def record_agent_run(self, *, agent: str, task_id: str, input: dict[str, Any],
                         decision: str, reason: str,
                         result: dict[str, Any] | None = None,
                         error: str | None = None) -> AuditRecord
    def record_policy_check(self, *, request: PolicyRequest,
                            decision: PolicyDecision) -> AuditRecord
```

**要件定義書5.5節の9項目との対応**（この対応表が T-005 完了条件5・S-H の判定基準である）:

| # | 要件の項目 | `AuditRecord` | `decisions` の列 | JSONL のキー |
| --- | --- | --- | --- | --- |
| 1 | timestamp | `timestamp` | `timestamp` | `timestamp` |
| 2 | agent | `agent` | `agent` | `agent` |
| 3 | task | `task` | `task_id` | `task` |
| 4 | input | `input` | `input`（JSON） | `input` |
| 5 | decision | `decision` | `decision` | `decision` |
| 6 | reason | `reason` | `reason` | `reason` |
| 7 | action | `action` | `action` | `action` |
| 8 | result | `result` | `result`（JSON） | `result` |
| 9 | error | `error` | `error` | `error` |

**JSONL の各行は、上の9キーを必ず全て持つ**（値が無い場合は `null`）。加えてメタ情報として `kind` / `decision_id` / `schema_version`（整数 `1`）を持つ。
**キーを省略しない。** 「キーが無い」と「値が null」を読み手が区別できなくなるため。

種別ごとの値の入れ方:

| 項目 | `kind="agent_run"` | `kind="policy_check"` |
| --- | --- | --- |
| `agent` | 実行した Agent 名 | `request.requested_by`（既定 `policy-engine`） |
| `task` | 実行中の `task_id` | `request.task_id`（無ければ `null`） |
| `input` | Agent へ渡した `payload` | `{"action":…, "topic":…, "target_user":…}` |
| `decision` | `AgentOutput.decision`、失敗時は `"error"` | `outcome` の値（`allow` / `require_approval` / `deny`） |
| `reason` | `AgentOutput.reason`、失敗時は `"<例外クラス名>: <メッセージ>"` | **`"<reason_code>: <message>"` の形**（先頭が `reason_code` であることを保証する） |
| `action` | `null` | Action 名 |
| `result` | `AgentOutput.payload`、失敗時は `null` | `PolicyDecision.detail`（空なら `{}`） |
| `error` | 失敗時のみ1行の文字列 | 常に `null` |

書き込み順序と失敗時の扱い:

1. `decisions` テーブルへ INSERT し、**コミットする**（正本）
2. `audit.jsonl` へ1行 append する（`ensure_ascii=False`、`sort_keys=True`、末尾改行、ファイルは `a` モードで都度 open/close）
3. 2 が失敗したら、運用ログへ `ERROR` を出すが**例外にしない**（正本は残っているため）
4. 1 が失敗したら例外を送出する（記録できない実行を進めない）

- 却下案: JSONL を先に書く → DB 側が失敗したとき、Task と結び付かない監査行が残る
- 却下案: JSONL だけ / DB だけ → JSONL だけでは `status` の集計や上限判定（10.5）ができない。DB だけでは、DB を開けない状況で監査を目視できない。
  **正本を DB と決めたうえで両方書く**

### 11.4 秘密値のマスク（品質基準 Q10）

- `input` / `result` の**キー名**が `(?i)(token|secret|password|passwd|api[_-]?key|credential|authorization)` に一致する場合、値を `"***"` に置き換えてから記録する
- ネストした辞書・リストの中も再帰的に適用する
- Stage 0 に秘密値を扱う機能は無い。**先に入れておく理由は、Stage 3 で認証情報が入った瞬間に監査記録へ漏れるのを防ぐため**（拡張点 E-8）
- 運用ログにも同じ規則を適用する（`Config` を丸ごとログへ出さない。出してよいのは `project.name` / `version` / `primary_platform` 等の非秘密項目）

---

## 12. `media-agent init` の詳細

### 12.1 生成物

`init` が作るのは次の8つ（方式設計7章）。

| # | パス | 種別 | Git | 生成元 |
| --- | --- | --- | --- | --- |
| 1 | `.media-agent/config.yaml` | ファイル | 追跡する | テンプレート（12.2） |
| 2 | `.media-agent/strategy.md` | ファイル | 追跡する | テンプレート |
| 3 | `.media-agent/rules.md` | ファイル | 追跡する | テンプレート |
| 4 | `.media-agent/agents/.gitkeep` | ファイル（空） | 追跡する | 空ファイル |
| 5 | `.media-agent/memory/.gitkeep` | ファイル（空） | 追跡する | 空ファイル |
| 6 | `.media-agent/data/` | ディレクトリ | 追跡しない | — |
| 7 | `.media-agent/logs/` | ディレクトリ | 追跡しない | — |
| 8 | `.media-agent/.gitignore` | ファイル | 追跡する | テンプレート |

- `data/media-agent.db` は **12.4 の接続点で作られる**。生成物の一覧には含めない（前提 D-P4）
- `logs/media-agent.log` と `logs/audit.jsonl` は、最初に記録が発生したときに作られる。`init` では作らない
- **`.claude/` には一切触れない**（方式設計8章、罠 T-1）
- **プロジェクトルート直下の `.gitignore` を書き換えない**（方式設計7章）

### 12.2 テンプレートの中身

置き場所は `media_agent/project/templates/`。読み込みは `importlib.resources`（罠 T-4）。
`config.yaml` のテンプレートだけが置換対象を持つ。置換は `{{PROJECT_NAME}}` の1箇所のみで、`str.replace` で行う
（却下案: Jinja2 → 置換1箇所のために依存を1つ増やすことになる）。

**`config.yaml`**（`{{PROJECT_NAME}}` はプロジェクトルートのディレクトリ名で置換する。12.3）

```yaml
# Media Agent プロジェクト設定
# 項目の意味: docs/design/stage0-detail.md 5章
# このファイルは Git で追跡してよい（認証情報を書かないこと）

version: 1

project:
  name: "{{PROJECT_NAME}}"
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

**`strategy.md`**

```markdown
# メディア戦略

> `media-agent init` が生成した雛形。プロジェクトに合わせて書き換えること。
> 自然言語で書く。**Stage 0 の Media Agent はこのファイルを解釈しない**（Stage 4 の Strategy Agent が読む）。

## ターゲット

（誰に届けるか）

## ブランドトーン

（どんな語り口か）

## メディアの目的

（このメディアで何を達成するか）

## 投稿方針

（何を、どのくらいの頻度で投稿するか）

## コンテンツ方針

（扱うテーマ / 扱わないテーマ）
```

**`rules.md`**

```markdown
# 運用ルール

> `media-agent init` が生成した雛形。プロジェクトに合わせて書き換えること。
> 自然言語で書く。**Stage 0 の Media Agent はこのファイルを解釈しない**（Stage 1 の Content Agent が読む）。
> 機械的に強制したい制限は `config.yaml` の `actions` / `limits` に書くこと。

## 禁止事項

- 事実確認ができていない情報を、断定的に書かない
- 他者の著作物を無断で転載しない

## ブランドルール

（表記ゆれ、使ってよい語 / 使わない語）

## 投稿ルール

（文字数、ハッシュタグ、リンクの扱い）

## エスカレーション

（人間の判断が必要になる条件）
```

**`.media-agent/.gitignore`**

```gitignore
# Media Agent が生成する実行時の産物（要件定義書14.2）
data/
logs/

# 認証情報。Stage 0 では生成しないが、将来置かれても追跡しない
.env
.env.*
```

### 12.3 `{{PROJECT_NAME}}` の決め方

1. プロジェクトルートのディレクトリ名（`root.resolve().name`）
2. 前後の空白を除去する
3. 空文字になる場合（ファイルシステムのルート等）は `my-project` を使う
4. YAML のスカラとして安全にするため、`\` と `"` をエスケープして**必ずダブルクォートで囲む**（テンプレート側が `"` を含んでいる）

**生成した `config.yaml` は、`init` の最後に自分で `load_config()` を通して検証する。** 通らなければ `ScaffoldError`（終了コード 1）。
理由: 生成物が自分の検証を通らない状態は、利用者が最初に踏む最悪の罠である。

### 12.4 DB の生成（順序制約 O-1 の接続点）

- `init` は生成物を書いたあと、**`ensure_project_db(layout, config)` を呼ぶ**。この関数は `connect` + `ensure_schema` + `ProjectRepository.sync` を行う
- **この呼び出しは T-005 が追加する。** T-004 の時点では DB 層が存在しないため、`init` は呼ばない（前提 D-P4、方式設計 17.2 の O-1）
- したがって受け入れテスト S-A は、**`data/media-agent.db` の存在を判定対象にしない**（19章）。DB の存在は S-B（`doctor`）で判定する

### 12.5 既に `.media-agent/` が存在する場合

**既定は「不足しているものだけを作り、既存のファイルには一切触れない」。冪等であり、終了コードは 0。**

| 対象の状態 | 既定（`--force` なし） | `--force` |
| --- | --- | --- |
| 存在しない | 作る（`created`） | 作る（`created`） |
| 存在する（1〜3, 8 のテンプレート由来ファイル） | **触らない**（`skipped`） | **テンプレートで上書きする**（`updated`） |
| 存在する（4, 5 の `.gitkeep`） | 触らない（`skipped`） | 触らない（`skipped`） |
| 存在する（6, 7 のディレクトリ） | 触らない（`skipped`） | 触らない（`skipped`） |
| `data/` `logs/` の中身、`agents/` の利用者ファイル、`memory/` の中身 | **絶対に触らない** | **絶対に触らない** |

- `--force` は**テンプレート由来の4ファイルだけ**を上書きする。データとログと利用者が書いたファイルは対象外。この境界を実装で緩めないこと
- `.media-agent` が**ファイルとして存在する**（ディレクトリでない）場合は `ScaffoldError`（終了コード 1）。安定文字列: パスと `ディレクトリではありません`
- 却下案A: 既存があればエラーで終了する → 「あとから足された生成物（将来 `.media-agent/` に増えるファイル）を補えない」。方式設計7章が `init` に冪等性を要求している
- 却下案B: 既定で上書きする → 利用者が書いた `strategy.md` / `rules.md` / `config.yaml` を、警告なしに失わせる。**最も避けるべき挙動**

### 12.6 出力

stdout（`--json` は無視する。方式設計 6.2）:

```
created  .media-agent/config.yaml
created  .media-agent/strategy.md
created  .media-agent/rules.md
created  .media-agent/agents/.gitkeep
created  .media-agent/memory/.gitkeep
created  .media-agent/data/
created  .media-agent/logs/
created  .media-agent/.gitignore
Media Agent を初期化しました: /abs/path/to/project
```

- 各行は `created  <相対パス>` / `skipped  <相対パス>` / `updated  <相対パス>` のいずれか（動詞と相対パスの間は空白2つ、相対パスの区切りは `/`）
- 最終行は `Media Agent を初期化しました: <絶対パス>`
- **行の集合の完全一致を判定しない**（T-005 で DB の行が1つ増えるため）。安定しているのは「各行の先頭の動詞」「相対パス」「最終行の形」
- `init` は**プロジェクトルートを上方探索しない**（方式設計 6.3）。`-C` またはカレントディレクトリそのものに作る
- 終了コード: 0

### 12.7 シグネチャ

```python
@dataclass(frozen=True)
class ScaffoldEntry:
    path: Path            # 絶対パス
    relative: str         # root からの相対（'/' 区切り）
    action: Literal["created", "skipped", "updated"]

@dataclass(frozen=True)
class ScaffoldResult:
    layout: ProjectLayout
    entries: tuple[ScaffoldEntry, ...]

def init_project(root: Path, *, force: bool = False) -> ScaffoldResult: ...
```

---

## 13. `media-agent doctor` の検査項目

### 13.1 原則

- **`doctor` は副作用を持たない。** ファイルを作らない・直さない・DB を作らない・マイグレーションを実行しない。書き込み可否の検査（`logs.writable`）だけは一時ファイルを作り、**必ず削除する**
- **`doctor` はネットワークへ出ない。認証情報を探さない。**「認証情報が無いこと」を異常として報告しない（T-002 完了条件4、T-007 完了条件2、PO 制約 C-2）
- **最初の異常で打ち切らない。** 全項目を実行してから結果をまとめる
- プロジェクトが未初期化のときだけは検査に入らず、`ProjectNotInitializedError`（終了コード 3）で終わる（17章）

### 13.2 検査項目

`status` は `ok` / `warn` / `skipped` / `fail` の4値。**`fail` が1件でもあれば終了コード 5、それ以外は 0。**

| # | check id | 合格（`ok`）条件 | `warn` / `skipped` になる場合 | `fail` のときの `hint` |
| --- | --- | --- | --- | --- |
| 1 | `structure.files` | `config.yaml` / `strategy.md` / `rules.md` が存在し、読み取れる | — | `media-agent init` を実行してください（既存ファイルは変更されません） |
| 2 | `structure.dirs` | `agents/` `memory/` `data/` `logs/` の4つが存在する（ディレクトリである） | — | 同上 |
| 3 | `config.syntax` | `config.yaml` が `yaml.safe_load` で読め、mapping である | — | YAML の構文を確認してください |
| 4 | `config.schema` | 5章のスキーマ検証を通る | — | 違反したキーパスを `message` に列挙する |
| 5 | `config.version` | `version == 1` | `version` キーが無い場合は `warn`（`1` とみなす） | サポートする config 版数は 1 です |
| 6 | `config.consistency` | `content.posts_per_day <= actions.post.max_per_day`（`max_per_day` が `null` なら常に `ok`） | 上回る場合は `warn` | — |
| 7 | `db.file` | `data/media-agent.db` が存在し、SQLite として開ける | — | `media-agent init` を実行してください |
| 8 | `db.schema` | `PRAGMA user_version == SCHEMA_VERSION` かつ6テーブルがすべて存在する | — | 版数が古い場合: `media-agent init` で移行されます／新しい場合: Media Agent を更新してください |
| 9 | `db.foreign_keys` | 検査用の接続で `PRAGMA foreign_keys` が `1` を返す | — | 実装の不具合（罠 T-2）。報告してください |
| 10 | `logs.writable` | `logs/` に一時ファイルを作成して削除できる | — | ディレクトリの権限を確認してください |
| 11 | `security.gitignore` | `.media-agent/.gitignore` が存在し、`data/` `logs/` `.env` の3つを**行として**含む | — | 要件14.2。`media-agent init --force` で復元できます |
| 12 | `security.env_not_tracked` | `.media-agent/` 配下に `.env*` が**存在しない**、または存在して Git の追跡対象でない | `.env*` が無い場合は **`skipped`**（メッセージ: Stage 0 では認証情報を使いません）／Git リポジトリでない場合も `skipped` | `.env` が Git の追跡対象です。`git rm --cached` で外してください |
| 13 | `agents.registry` | `build_default_registry()` が1つ以上の Agent を返し、`echo` が引ける | — | 実装の不具合。報告してください |
| 14 | `policy.config` | 4 Action すべてについて `PolicyEngine.check(..., record=False)` が `PolicyDecision` を返す | — | `actions` の設定を確認してください |
| 15 | `runtime.python` | 実行中の Python が 3.11 以上 | — | Python 3.11 以上で実行してください |

- **検査 12 が「認証情報の不在を異常としない」ことの実体である。** `.env` が無いのは正常（`skipped`）。**`fail` になるのは「あって、しかも Git に追跡されている」場合だけ**
- 検査 12 の Git 判定は `git ls-files --error-unmatch <path>` 相当の確認で行う。`git` コマンドが無い環境では `skipped`
- 検査 9 は罠 T-2（外部キーが黙って効かない）の再発をコマンドで検出するために置く
- **Stage 0 では検査しないもの**: 外部サービスへの疎通、API キーの有無・妥当性、依存パッケージのバージョン整合（`pip check` 相当）、`.claude/` の有無

### 13.3 出力

テキスト（stdout）:

```
Media Agent doctor — /abs/path/to/project
[ok]      structure.files      config.yaml / strategy.md / rules.md がそろっています
[ok]      structure.dirs       agents / memory / data / logs がそろっています
...
[skipped] security.env_not_tracked  .env はありません（Stage 0 では認証情報を使いません）
[warn]    config.consistency   content.posts_per_day (5) が actions.post.max_per_day (3) を超えています
結果: 13 ok / 1 warn / 1 skipped / 0 fail
```

- 各行は `[<status>]` で始まり、続いて **check id をそのまま**出す。**15項目すべてが必ず1行ずつ出る**（`fail` があっても他を省略しない）
- `fail` の行の直後に `          → 対処: <hint>` の行を出す
- 最終行は `結果: <n> ok / <n> warn / <n> skipped / <n> fail`
- `fail` が1件以上のときだけ、stderr へ `Error: doctor の検査に <n> 件の不合格があります` を出し、終了コード 5

JSON（`--json`）:

```json
{
  "project_root": "/abs/path/to/project",
  "overall": "ok",
  "checks": [
    {"id": "structure.files", "status": "ok", "message": "...", "hint": null}
  ],
  "summary": {"ok": 13, "warn": 1, "skipped": 1, "fail": 0}
}
```

- `overall` は `fail` が1件以上なら `"fail"`、それ以外は `"ok"`
- JSON 出力のときも終了コードの規則は同じ

### 13.4 設定が壊れている場合の `doctor`

- `config.syntax` / `config.schema` / `config.version` が `fail` になり、**それらに依存する検査（6, 14）は `skipped`** になる
- **`ConfigError` を送出しない。** したがって終了コードは 4 ではなく **5**
- これは意図した非対称である。`doctor` は異常を**列挙する**コマンドであり、最初の1件で落ちてはならない

---

## 14. `media-agent status` の出力

- 対象: 現在の Agent / Task の状態（要件定義書10節「現在のAgent / Task / Workflow状態を確認する」）
- **`status` は `ensure_project_db` を呼ぶ**（DB が無ければ作る）。`doctor` と違い、状態を見るために DB が必要であり、
  無い場合に失敗するより作るほうが利用者の意図に合う
- Config が読めない場合は `ConfigError`（終了コード 4）。未初期化なら終了コード 3
- 終了コード: 0

テキスト（stdout）:

```
Media Agent status — /abs/path/to/project
project      : my-project
config       : version 1 / platform x / posts_per_day 3
automation   : require_approval=false  post=auto reply=approval repost=approval like=disabled
database     : .media-agent/data/media-agent.db (schema 1)
agents       : 2 registered — echo, fail
tasks        : total 3 — pending 0 / running 0 / completed 2 / failed 1 / cancelled 0
recent tasks :
  2026-08-23T10:00:00.123456Z  completed  echo  0a1b2c3d-...
  2026-08-23T09:59:00.000000Z  failed     fail  4e5f6a7b-...
```

- ラベルは左詰め13文字 + `: `。**ラベル名（`project` / `config` / `automation` / `database` / `agents` / `tasks` / `recent tasks`）が安定文字列である**
- `recent tasks` は `created_at` の降順で最大5件。0件のときはラベル行の次に `  (タスクはありません)` を出す
- **5つの状態名すべてを、件数 0 でも出す**（`tasks` の行）。「出ていない＝0」を読み手に推測させない

JSON（`--json`）:

```json
{
  "project_root": "/abs/path/to/project",
  "project_name": "my-project",
  "config": {"version": 1, "primary_platform": "x", "posts_per_day": 3,
             "require_approval": false,
             "actions": {"post": "auto", "reply": "approval", "repost": "approval", "like": "disabled"}},
  "database": {"path": ".media-agent/data/media-agent.db", "schema_version": 1},
  "agents": [{"name": "echo", "version": 1, "description": "..."},
             {"name": "fail", "version": 1, "description": "..."}],
  "tasks": {"total": 3,
            "by_status": {"pending": 0, "running": 0, "completed": 2, "failed": 1, "cancelled": 0}},
  "recent_tasks": [{"task_id": "...", "agent": "echo", "type": "agent_run", "status": "completed",
                    "created_at": "...", "started_at": "...", "completed_at": "..."}]
}
```

---

## 15. `media-agent run` の Stage 0 での挙動

### 15.1 決定

**Stage 0 の `run` は、組み込み Agent を1本実行し、Task と Audit を残して終わる。**（方式設計 6.4 の枠を具体化したもの）

```
media-agent run [--agent NAME] [--input JSON] [--json]
```

| オプション | 既定 | 意味 |
| --- | --- | --- |
| `--agent NAME` | `echo` | 実行する Agent 名。未登録なら `AgentNotFoundError`（終了コード 1） |
| `--input JSON` | `{"message": "hello"}` | Agent へ渡す payload。JSON オブジェクトの文字列。壊れていれば `UsageError`（終了コード 2） |
| `--json` | off | 機械可読出力（15.3） |

手順:

1. プロジェクトルート解決（未初期化なら終了コード 3）
2. `load_config()`（不正なら終了コード 4）
3. `setup_logging()` にファイルハンドラを追加
4. `ensure_project_db(layout, config)`
5. `build_default_registry()` → `TaskService` / `AuditRecorder` / `AgentRunner` を組み立てる
6. `runner.run(agent_name, payload)`
7. 結果を出力し、終了コードを決める

| Task の最終状態 | 終了コード | 例外 |
| --- | --- | --- |
| `completed` | 0 | — |
| `failed` | 1 | `AgentExecutionFailedError`（`MediaAgentError`） |

- **`run` は「Workflow を実行する」コマンド（要件定義書10節）だが、Stage 0 に Workflow は存在しない。** 存在しない Workflow を装わず、
  「Agent Runtime が動くことを示す最小の実行」に留める
- 却下案A: `run` を未実装スタブ（終了コード 10）にする → 方式設計 6.4 が `run` を実装対象と決めている。要件定義書18節 Stage 0 の検証条件も
  Agent 実行の検証を含む。**Runtime を作ったのに CLI から一度も動かせない**のは、要件定義書26節の開発原則2（各Stageで動くものを作る）に反する
- 却下案B: 登録されている全 Agent を順に実行する → `fail` が必ず失敗するため `run` が常に非ゼロで終わる。既定の体験として不適切

### 15.2 テキスト出力

```
Media Agent run — /abs/path/to/project
agent   : echo
task    : 0a1b2c3d-89ab-4cde-8f01-23456789abcd
status  : completed
output  : {"message":"hello"}
```

失敗時（終了コード 1）:

```
Media Agent run — /abs/path/to/project
agent   : fail
task    : 4e5f6a7b-...
status  : failed
error   : AgentFailedForVerificationError: 検証用 Agent 'fail' は常に失敗します
```

に加えて stderr へ `Error: Agent の実行が失敗しました (task=<task_id>)`。

- 安定文字列: 行ラベル `agent` / `task` / `status` / `output` / `error` と、`status` の値（`completed` / `failed`）

### 15.3 JSON 出力

```json
{"project_root": "/abs/...", "agent": "echo", "task_id": "0a1b...", "status": "completed",
 "output": {"message": "hello"}, "error": null,
 "created_at": "...", "started_at": "...", "completed_at": "..."}
```

**方式設計 6.2 では `--json` の対応を `doctor` / `status` の2つとしていたが、本設計はこれを `run` / `agent list` / `task list` へ広げる。**
追記であり、変更ではない（6.2 の理由「機械可読形式を後付けしない」がそのまま当てはまる）。受け入れテストが `task_id` を人間向け出力の
パースで取り出す必要がなくなる。

### 15.4 `run` は Policy Check を呼ばない

- Stage 0 の `run` は **Action を1つも発行しない**（投稿しない・返信しない・いいねしない）。Policy Check は Action の直前に置く関門であり、
  Action が無い場所に関門を置くと、「何も守っていないのに通過記録だけが残る」ことになる
- Policy Engine はライブラリとして完成させ、単体テストと受け入れテスト S-G が **公開 API 経由で**検証する（前提 D-P6）
- Stage 3 で Action を実装するとき、**Action の発行点は必ず `PolicyEngine.check()` を通す**（拡張点 E-4）。この関門を後から差し込むのではなく、
  Action を足す側が通す
- 却下案: `run` の中で形だけ Policy Check を呼ぶ → 判定結果が何にも影響しないため、監査記録に「意味のない allow」が積もる。
  さらにそれが 10.5 の計数対象になり、**上限判定が実行していない Action で消費される**
- 却下案: `media-agent policy check <action>` コマンドを足して CLI から検証できるようにする → **T-007 の変更範囲（doctor / status / run / agent list / task list）を超える。**
  必要なら別タスクとして起こすべきであり、詳細設計が勝手に増やさない（20.3 に申し送り）

---

## 16. `agent list` / `task list`

いずれも**読み取り専用**（方式設計 6.4、T-007 完了条件4-b）。未初期化なら終了コード 3。

### 16.1 `media-agent agent list`

```
NAME  VERSION  DESCRIPTION
echo  1        入力をそのまま返す検証用の組み込み Agent
fail  1        常に失敗する検証用の組み込み Agent
```

- 名前の昇順。ヘッダ行を必ず出す。安定文字列: ヘッダの `NAME` / `VERSION` / `DESCRIPTION` と Agent 名
- `--json`: `{"agents": [{"name": "echo", "version": 1, "description": "..."}]}`

### 16.2 `media-agent task list [--status STATUS] [--limit N]`

```
TASK_ID                               AGENT  TYPE       STATUS     CREATED_AT                   COMPLETED_AT
0a1b2c3d-89ab-4cde-8f01-23456789abcd  echo   agent_run  completed  2026-08-23T10:00:00.123456Z  2026-08-23T10:00:00.234567Z
```

- 既定 `--limit 20`、`created_at` の降順。`--status` は5つの状態名のいずれか（他は `UsageError` / 終了コード 2）
- 0件のときは `(タスクはありません)` の1行（ヘッダは出す）
- `--json`: `{"tasks": [ ... 14章 `recent_tasks` と同じ項目 ... ]}`
- **`task cancel` 等の書き込み系サブコマンドは Stage 0 では作らない**（方式設計 6.4）。したがって Stage 0 で `cancelled` を作る経路は
  公開 API（`TaskService.transition`）だけである

---

## 17. 例外・終了コード・安定文字列

### 17.1 例外階層

すべて `media_agent.errors` に置き、`MediaAgentError` を基底とし、**クラス属性 `exit_code` を持つ**（方式設計 6.5、品質基準 Q8）。

```
MediaAgentError (exit_code = 1)
├── ProjectNotInitializedError            (3)
├── ScaffoldError                         (1)
├── ConfigError                           (4)
│   ├── ConfigNotFoundError               (4)
│   ├── ConfigParseError                  (4)
│   ├── ConfigValidationError             (4)
│   └── ConfigVersionError                (4)
├── DatabaseError                         (1)
│   └── DatabaseVersionError              (1)
├── AgentError                            (1)
│   ├── AgentNotFoundError                (1)
│   ├── DuplicateAgentError               (1)
│   ├── InvalidAgentError                 (1)
│   └── AgentExecutionFailedError         (1)
├── InvalidTaskTransitionError            (1)
├── PolicyDeniedError                     (6)     # Stage 0 では送出されない（10.6）
├── DoctorCheckFailedError                (5)
└── NotImplementedInStageError            (10)
```

`AgentFailedForVerificationError` は **この階層に属さない**（`RuntimeError` の派生。8.4 の理由による）。

### 17.2 コマンド × 状況の一覧（受け入れテスト S-D / S-I の期待値）

| 状況 | `init` | `doctor` | `status` | `run` | `agent list` / `task list` | スタブ4種 | `--help` / `--version` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 未初期化のディレクトリ | 0（作る） | **3** | **3** | **3** | **3** | **10** | 0 |
| 初期化済み・正常 | 0（冪等） | 0 | 0 | 0 | 0 | **10** | 0 |
| `config.yaml` が壊れている | 0（触らない） | **5** | **4** | **4** | `agent list`=0 / `task list`=**4** | **10** | 0 |
| `-C` の指定先が存在しない | 2 | 2 | 2 | 2 | 2 | 2 | 0 |

- **スタブコマンド（`setup` / `post` / `research` / `analyze`）は、プロジェクトの状態を見る前に終了コード 10 で終わる。**
  未実装であることは環境に依存しないため。安定文字列: `Stage` と `未実装`
- `agent list` は Config を読まない（Registry は組み込みのみで、設定に依存しない）。`task list` は DB を読むため Config が要る
- `--help` / `--version` は Click が処理し、プロジェクトの解決より前に終了する（終了コード 0）

### 17.3 エラー出力の形（stderr）

```
Error: <一行の要約>
  <詳細（省略可、複数行可）>
Hint: <対処（省略可）>
```

| 状況 | 安定文字列（テストが判定してよいもの） |
| --- | --- |
| 未初期化 | `Media Agent が初期化されていません` と対象の絶対パス、`media-agent init` |
| Config 検証エラー | `config.yaml`、違反したキーパス（`project.name` 等） |
| Config 構文エラー | `config.yaml`、`構文` |
| Agent 未登録 | 要求した Agent 名と、登録済みの名前一覧 |
| 遷移違反 | 遷移元と遷移先の状態名、`task_id` |
| スタブ | `Stage`、`未実装` |
| doctor 不合格 | `doctor`、不合格件数 |

**テストは「終了コード」と「この表の安定文字列」だけを判定する。** 文面全体を判定対象にしない（方式設計の用語集「終了コード表」）。

---

## 18. Security（要件定義書14節）への対応

### 18.1 Stage 0 の立場

- **Stage 0 に認証情報を必要とする機能は存在しない**（PO 制約 C-2、要件定義書28節）。よって、
  **認証情報を読むコードを書かない**（環境変数も `.env` も読まない）
- `init` は `.env` を**生成しない**（方式設計7章）
- `doctor` は認証情報を**探さない**。「無いこと」を異常として報告しない（13.2 の検査 12）

### 18.2 Git へコミットさせないための仕組み

| # | 仕組み | 実体 | 実装タスク |
| --- | --- | --- | --- |
| 1 | 利用者プロジェクト側の除外 | `.media-agent/.gitignore` に `data/` `logs/` `.env` `.env.*`（12.2） | T-004 |
| 2 | Media Agent リポジトリ側の除外 | リポジトリルートの `.gitignore`（18.3） | T-004 |
| 3 | 設定検証 | `doctor` の `security.gitignore` 検査（除外設定が消えていないか） | T-007 |
| 4 | 追跡の検査 | `doctor` の `security.env_not_tracked` 検査（`.env` が Git に追跡されていないか） | T-007 |
| 5 | 記録への漏洩防止 | Audit / 運用ログの秘密値マスク（11.4） | T-005 |
| 6 | 設定ファイルへの記載防止 | `config.yaml` のスキーマに認証情報の項目を**置かない**（`extra="forbid"` により、書いても検証エラーになる） | T-004 |

**6 が最も効く。** 置き場所が無い設定は書かれない。将来 `.env` を読むようになっても、**認証情報が `config.yaml` へ入る経路は塞いだままにする**（拡張点 E-8）。

### 18.3 Media Agent リポジトリの `.gitignore`（T-004 完了条件8）

最低限、次を含める。

```gitignore
.venv/
__pycache__/
*.py[cod]
*.egg-info/
build/
dist/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
coverage.xml
.env
.env.*
```

---

## 19. 受け入れテスト S-A〜S-I への対応（T-003 への引き渡し）

**各シナリオについて、二値で判定できる期待値の所在を示す。** ここに無い期待値は設計に書かれていないため、T-003 は推測せず問い合わせること。

| ID | 期待値の所在 | 二値で判定できる形（要点） |
| --- | --- | --- |
| **S-A** | 12.1 / 12.5 / 12.6 | 空ディレクトリで `init` → 終了コード 0。**12.1 の8つの生成物が存在する**（`config.yaml` / `strategy.md` / `rules.md` / `agents/.gitkeep` / `memory/.gitkeep` / `data/` / `logs/` / `.gitignore`）。`config.yaml` は `load_config()` を通り、`project.name` がディレクトリ名。**`data/media-agent.db` は判定対象にしない**（12.4）。2回目の `init` も終了コード 0 で、既存ファイルの内容が変わらない（`--force` 無し） |
| **S-B** | 13.2 / 13.3 | `init` 済みで `doctor` → 終了コード 0。stdout に**15項目の check id がすべて現れる**。`fail` の行が0件（`結果:` 行の `fail` が `0`）。`security.env_not_tracked` の行が `[skipped]` または `[ok]` であり、**`[fail]` でないこと**が「認証情報の不在を異常としない」の判定 |
| **S-C** | 14章 | `init` 済みで `status` → 終了コード 0。ラベル `project` / `config` / `database` / `agents` / `tasks` / `recent tasks` がすべて出る。`--json` で `agents` に `echo` が含まれ、`tasks.by_status` に**5状態すべてのキー**がある |
| **S-D** | 17.2 | 未初期化ディレクトリで `doctor` / `status` / `run` / `agent list` / `task list` → **終了コード 3**、stderr に `Media Agent が初期化されていません`。スタブ4種は**終了コード 10**。いずれも stdout に成功を示す出力を出さない |
| **S-E** | 8.1〜8.4 | `build_default_registry()` に `echo` があり、`AgentRunner.run("echo", {"message": "hi"})` の `TaskRunResult.output.payload == {"message": "hi"}`、`decision` と `reason` が空でない。CLI 経由なら `run --agent echo --input '{"message":"hi"}' --json` の `status == "completed"` かつ `output == {"message":"hi"}` |
| **S-F** | 9.2 / 8.3 | `echo` 実行後の Task が `completed`、`started_at` と `completed_at` が非 null。`fail` 実行後の Task が `failed` で `error` が非 null、**Runner が例外を送出しない**。`TaskService.transition` が 9.2 の表に無い遷移（例 `pending`→`completed`、`completed`→`running`、`running`→`cancelled`）に対して `InvalidTaskTransitionError` を送出し、**DB 上の状態が変わらない** |
| **S-G** | 10.3 / 10.4 | 10.3 の表の4行を、`(outcome, reason_code)` の組で判定する。上限超過は `max_per_day: 1` の設定で `check()` を2回呼び、**1回目 `(allow, mode_auto)` / 2回目 `(deny, limit_exceeded_per_day)`**（`record=True` の既定で計数される）。加えて `automation.require_approval: true` で `(require_approval, global_approval_required)` |
| **S-H** | 11.3 | `run` 後、`audit.jsonl` の最終行が JSON として読め、**9キー（timestamp/agent/task/input/decision/reason/action/result/error）がすべて存在する**。同じ内容が `decisions` テーブルに1行ある。`fail` 実行時は `error` が非 null かつ `decision == "error"`。**運用ログ（`media-agent.log`）とは別のファイルであること** |
| **S-I** | 5.4 / 17.2 / 17.3 | `config.yaml` を壊す（YAML 構文崩し / `project.name` 削除 / 未知キー追加 / `actions.post.mode: autoo`）→ `status` または `run` が**終了コード 4**、stderr に**該当キーパス**（構文崩しの場合は `構文`）。同じ状態で `doctor` は**終了コード 5** であり、`config.schema` の行が `[fail]` |

補足（T-003 が迷いやすい点）:

- **S-E / S-F / S-G / S-H は、CLI と公開 API のどちらで書いてもよい**（前提 D-P6）。Stage 0 の CLI には Policy と遷移違反を観測する面が無いため、S-F の遷移違反と S-G は公開 API で書くことになる
- **テストは必ず `tmp_path` を使い、`-C/--project-dir` で対象を明示する**（罠 T-3）。`os.chdir` を使わない
- 実行順序に依存する期待値を書かない。10.5 の上限判定は**同じ DB 内の履歴**に依存するため、テストごとに新しい一時プロジェクトを使う

---

## 20. 実装タスクへの割当と順序

### 20.1 割当（方式設計 16章の U-1〜U-4 = T-004〜T-007 に対応）

| タスク | 本文書のうち実装する章 |
| --- | --- |
| **T-004**（U-1） | 4章（`errors` / `ProjectLayout`）、5章（Config Schema 全体）、12章（`init` とテンプレート。**12.4 の DB 呼び出しを除く**）、17章（例外階層と終了コード変換）、18.3 |
| **T-005**（U-2） | 6章（DB Schema と Repository）、7章（Migration）、11章（Logger / Audit）、12.4（`init` へ `ensure_project_db` の呼び出しを1行足す） |
| **T-006**（U-3） | 8章（Agent Interface / Registry / Runner / 組み込み Agent）、9章（Task Model）、10章（Policy Model） |
| **T-007**（U-4） | 13章（doctor）、14章（status）、15章（run）、16章（agent list / task list）、および 15.3 の `--json` 拡張 |

### 20.2 順序の制約（方式設計 17.2 に本文書分を追加）

| # | 制約 |
| --- | --- |
| O-1 | （既出）DB の生成を `init` の実装に埋め込まない。T-005 が 12.4 の1行を足す |
| O-3 | （既出）Policy Engine は Config から設定を読む。独自の設定読み込みを作らない |
| O-4 | （既出）Audit は Runtime より先に存在する |
| **D-O5** | **`AuditRecorder` は `DecisionRepository` に依存し、`PolicyEngine` は両方に依存する。** よって T-005（DB + Audit）は T-006（Policy）より前でなければならない。既定の直列順（T-005 → T-006）と一致する |
| **D-O6** | **`AgentRunner` は `TaskService` と `AuditRecorder` を引数で受け取る**（自分で作らない）。T-006 が T-005 の実体をコンストラクタ経由で受け取る形にすることで、T-006 の単体テストが偽の Recorder を差し込める |

### 20.3 オーケストレーターへの申し送り

| # | 内容 |
| --- | --- |
| 1 | 15.3 で `--json` の対応コマンドを `run` / `agent list` / `task list` へ広げた。**T-007 の実装範囲に含まれる**（方式設計 6.2 の追記） |
| 2 | 15.4 で `media-agent policy check` コマンドを**採らなかった**。CLI から Policy を観測する面が Stage 0 に無いことは、受け入れテスト S-G が公開 API を使う理由になる。CLI からの観測が必要と判断されるなら**別タスク**として起こすこと |
| 3 | 12.5 の `--force` オプションを新設した。**T-004 の実装範囲に含まれる**（既存 `.media-agent/` の扱いは T-004 完了条件4 の対象） |
| 4 | 8.4 の組み込み Agent `fail` は**製品に同梱される**。T-006 の実装範囲。異常系を受け入れテストが製品コードなしで検証するために必要 |

---

## 21. 実装時の注意点（本文書分）

方式設計 17.1 の罠 T-1〜T-8 に加えて、次を守ること。

| # | 罠 | 対処 |
| --- | --- | --- |
| **D-T9** | `datetime.now()`（naive）を使うと、DB の文字列と比較したときに1時間ずれても気付けない | 時刻は必ず `core/clock.py` の `utcnow()` / `to_iso()` を通す（6.2） |
| **D-T10** | Pydantic v2 の `extra` は既定で `ignore`。設定の打ち間違いが黙って無視される | すべての Config モデルに `extra="forbid"` を明示する（5.1） |
| **D-T11** | `sqlite3.Row` をモジュールの外へ返すと、DB 方式の差し替え（E-2）が呼び出し側へ波及する | Repository は Pydantic モデル（`*Row`）を返す（6.6） |
| **D-T12** | Audit の JSONL を `json.dumps` の既定（`ensure_ascii=True`, キー順不定）で書くと、日本語がエスケープされ、差分が読めず、再現性の比較もできない | `ensure_ascii=False, sort_keys=True`（6.2 / 11.3） |
| **D-T13** | Task の状態遷移を Repository の `update_status` で直接呼ぶと、遷移表を迂回できる | 状態を変えてよいのは `TaskService.transition` だけ。Repository の `update_status` は `TaskService` からのみ呼ぶ（9.3） |
| **D-T14** | `PolicyEngine.check()` を `record=True`（既定）のまま何度も試すと、上限が消費される | 試験・診断目的では `record=False` を使う（10.6）。`doctor` の `policy.config` 検査は必ず `record=False` |
| **D-T15** | `doctor` が config を読むときに `ConfigError` を送出すると、終了コードが 5 ではなく 4 になり、S-I の期待値と食い違う | `doctor` の中では Config の読み込みを検査結果へ変換する（13.4） |
| **D-T16** | ログのファイルハンドラをプロジェクト解決前に追加すると、未初期化ディレクトリに `logs/` を作ってしまう | ファイルハンドラは解決後に追加する（11.2） |
| **D-T17** | `init` のテンプレートを `__file__` 相対で読む（罠 T-4 の再掲）。加えて、テンプレートを `pyproject.toml` のパッケージデータに含め忘れると wheel から消える | `importlib.resources` で読み、`media-agent init` を**インストール済み環境**で1回実行して確認する |

---

## 22. 未解決の不確実性

| # | 事項 | 扱い |
| --- | --- | --- |
| **D-X1** | 10.5 の「許可された回数」を「実行された回数」の代理とする近似 | **Stage 0 の間だけ有効。** Stage 3 で Action を実装する際に `count_allowed_actions` を差し替える。差し替えないまま Action を実装すると、上限が二重に消費される |
| **D-X2** | `limits.forbidden_topics` / `forbidden_users` の一致判定を「大文字小文字を無視した完全一致」とした | 部分一致・正規表現・類似判定が要るかは、実際に運用する Stage 4 以降で判断する。Stage 0 で決め打つ材料が無い |
| **D-X3** | `running` → `cancelled` の禁止（9.2） | 非同期実行・Scheduler が入る Stage 3 以降で、中断機構と同時に解禁する |
| **D-X4** | 同時実行（複数プロセスからの `run`）の正しさ | 前提 D-P3 により Stage 0 では考慮しない。`busy_timeout` と WAL で「即座に壊れない」ところまで |
| **D-X5** | `audit.jsonl` を回転させないため、長期運用でファイルが単調増加する | Stage 0 の実行回数では問題にならない。運用の長期化に備えたアーカイブ方式は Stage 5 以降で決める（**削除ではなくアーカイブ**であること） |
| **D-X6** | 方式設計 X-2（GitHub Actions の実行）・X-4（Windows） | 本文書でも解消しない。持ち越し |

---

## 23. 新しく定義した語

**用語集（`docs/glossary.md`）への登録はオーケストレーターが行う。** T-001 が定義済みの9語（プロジェクトルート / スタブコマンド /
スキャフォールド / 組み込み Agent / AgentRegistry・AgentRunner / PolicyDecision / 運用ログ・監査記録 / 拡張点 / 終了コード表）と
**同じ意味で使っている**。ここに挙げるのは本文書で新しく名前を付けたものだけである。

| 語 | 定義 | 一般的な意味で受け取ると何を間違えるか |
| --- | --- | --- |
| **ProjectLayout** | `.media-agent/` 配下のパスを1つのオブジェクトへまとめた解決結果（4.1）。`core/` はこれか個別の `Path` を**引数で受け取る** | 「ディレクトリ構造の説明」と取ると、Core が自分でパスを組み立ててしまい、品質基準 Q7 が壊れる |
| **AuditRecorder** | 監査記録の**唯一の書き込み口**（11.3）。`decisions` テーブルと `audit.jsonl` の両方へ、この順で書く | 「ログの一種」と取ると、`logging` へ流す実装になり、`logging.level` で監査が消せてしまう |
| **check id** | `doctor` の各検査に付けた安定した識別子（`structure.files` 等、13.2 の15個）。**出力に必ず現れ、テストはこれを判定する** | 「表示名」と取って文言と一緒に変えてしまうと、受け入れテストが壊れる。**文言は変えてよいが id は契約である** |
| **安定文字列** | 受け入れテストが `in` で判定してよい文字列（3章・17.3）。これ以外の文言は実装が自由に変えてよい | 「エラーメッセージ全文」を判定対象と取ると、文面の改善のたびにテストが落ちる |
| **ローリングウィンドウ（上限判定の窓）** | 判定時刻からさかのぼる固定長の時間窓（`per_day`=24時間、`per_hour`=1時間）（10.5） | 「1日」をカレンダー日（0時区切り）と取ると、タイムゾーンの扱いが必要になり、判定結果が実行時刻で変わる |
| **代理計数（Stage 0 の上限計数）** | Action の実行回数の代わりに、`allow` と判定した回数を数えること（10.5 / D-X1） | 「実行回数を数えている」と取ると、Stage 3 で Action を実装したときに二重計上する |
| **スキーマ版数（`SCHEMA_VERSION` / `config.version`）** | DB の構造版数（`PRAGMA user_version`）と、設定ファイルの構造版数。**互いに独立で、パッケージ版数とも独立**（7章） | どれか1つを「バージョン」と総称すると、コードだけ直したいときに設定移行が要るように見える |

---

## 24. 採用しなかった案（一覧）

各章に書いた却下案の索引。**「なぜこうなっているか」を後から辿るための入口である。**

| 論点 | 採用 | 主な却下案 | 却下の要点 | 章 |
| --- | --- | --- | --- | --- |
| `actions` の置き場所 | トップレベル | `automation.actions` へネスト | 要件定義書5.3・13節が `actions:` をトップレベルのキーとして示している。設計側でキー階層を変えると、要件の例をそのまま貼った設定が動かない | 5.1 |
| 未知のキー | `extra="forbid"` | 無視する | 打ち間違えた設定が黙って効かない状態が最も追いにくい | 5.1 |
| `mode` の既定 | 書いたなら必須 | 省略時 `auto` | 危険側の既定になる | 5.2.5 |
| 検証エラーの報告 | 全件まとめて | 1件目で打ち切り | 直しては再実行を繰り返させる | 5.4 |
| Entity の作成範囲 | 6つ全部 | Stage 0 で使う3つだけ | Migration 機構が一度も使われないまま Stage 0 を終える | 6.1 |
| Audit の永続先 | `decisions` テーブル（+JSONL の写し） | `audit_records` テーブルを別に作る | 同じ事実が2か所に書かれ、正本が決まらない | 6.4 |
| Migration | `PRAGMA user_version` | Alembic / 独自テーブル / `IF NOT EXISTS` だけ | 依存過大 / 初回の分岐が要る / 列変更を表現できない | 7.4 |
| Agent の型 | ABC | `Protocol` | 登録時に妥当性を確認できない | 8.1 |
| Agent の戻り値 | `decision` / `reason` を必須 | `dict` を返すだけ | Audit の必須項目を Runner が推測することになる | 8.1 |
| Agent 失敗時 | Runner が捕捉して `TaskRunResult` を返す | 例外を再送出 | 呼び出し側の書き忘れで Task が `running` のまま残る | 8.3 |
| `running`→`cancelled` | 禁止（Stage 0） | 許可して「中断要求」の意味にする | 状態名と実態が食い違う | 9.2 |
| Policy の判定順 | 禁止 → 上限 → 承認 | 承認を先に評価 | 「承認すれば禁止トピックも通る」設計になる | 10.4 |
| 上限の窓 | ローリング | カレンダー日 | タイムゾーン項目が必要になり、結果が実行時刻で変わる | 10.5 |
| Policy の記録 | `check()` が既定で記録 | 純関数にして外部で計数 | 記録しないと上限が永遠に来ない。計数と記録の整合が崩れる | 10.6 |
| Audit の実装 | 独立した `AuditRecorder` | `logging` の1レベル | `logging.level` で監査記録が消せてしまう | 11.1 |
| 運用ログの回転 | サイズ基準 1MiB×3 | 日次 / 回転しない | 空ファイルが並ぶ / ディスクを黙って埋める | 11.2 |
| Audit の回転 | しない | 運用ログと同じ回転 | 監査記録が消える。それは監査記録ではない | 11.1 |
| 書き込み順 | DB → JSONL | JSONL → DB | Task と結び付かない監査行が残る | 11.3 |
| 既存 `.media-agent/` | 不足分のみ作成（冪等） | エラーで終了 / 既定で上書き | 生成物を補えない / 利用者の記述を警告なく失う | 12.5 |
| `doctor` の副作用 | 無し | 不足を自動で直す | 「検査」と「修復」が混ざると、doctor が通った理由が説明できない | 13.1 |
| `doctor` の設定エラー | 検査結果 `fail`（終了コード 5） | `ConfigError`（終了コード 4） | 最初の1件で落ち、残りの検査結果が見えない | 13.4 |
| `run` の Stage 0 挙動 | 組み込み Agent を1本実行 | 未実装スタブ / 全 Agent 実行 | Runtime を作ったのに CLI から動かせない / 既定で必ず失敗する | 15.1 |
| `run` と Policy | 呼ばない | 形だけ呼ぶ / `policy check` コマンドを新設 | 意味のない `allow` が上限を消費する / T-007 の変更範囲を超える | 15.4 |
| テンプレートの置換 | `str.replace` | Jinja2 | 置換1箇所のために依存が増える | 12.2 |
