# プロジェクトディレクトリ `.media-agent/`

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

## Git で追跡するもの・しないもの

`.media-agent/.gitignore` が次を除外する。

| 追跡する | 追跡しない |
| --- | --- |
| `config.yaml` / `strategy.md` / `rules.md` | `data/`（DB）、`logs/`（ログ・監査記録）、`.env` / `.env.*` |

**`config.yaml` に認証情報を書かないこと。** 追跡対象であり、リポジトリへ入る。

## `config.yaml`

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

## 運用ログと監査記録は別物

**「ログ」と一括りにしない。** 2 つは目的も保証も違う。

| | 運用ログ | 監査記録 |
| --- | --- | --- |
| ファイル | `logs/media-agent.log` | `logs/audit.jsonl` と DB の `decisions` テーブル |
| 目的 | 人が動作を追う | AI の判断を後から検証する |
| 設定の影響 | `logging.level` で量が変わる | **設定で消せない** |
| 形式 | 人が読むテキスト | 1 行 1 レコードの JSON（追記のみ） |

どちらにも**秘密値は出力しない。** 入力に含まれる `api_key` のような値はマスクされる。

## DB

`data/media-agent.db` は SQLite で、Stage 0 のスキーマ版数は 1、テーブルは 6 つ
（`projects` / `sources` / `posts` / `performances` / `tasks` / `decisions`）。
Stage 0 で実際に書き込まれるのは `projects`（プロジェクト 1 行）・`tasks`・`decisions` の 3 つである。
`sources` / `posts` / `performances` は Stage 1 以降のための枠であり、Stage 0 では空のままになる。
