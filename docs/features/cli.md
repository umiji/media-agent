# CLI リファレンス

## 実行の経路

| 書き方 | 前提 |
| --- | --- |
| `media-agent ...` | パッケージをインストールした環境（`pip install` 済み） |
| `python -m media_agent ...` | 同上。コンソールスクリプトへパスが通っていない場合に使える |

どちらも同じ実装を呼ぶ。

## グローバルオプション

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

## コマンド一覧

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

## `media-agent init`

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

## `media-agent doctor`

プロジェクトが正しく初期化され、設定が壊れていないかを 15 項目で検査する。
各行の左にある識別子（`structure.files` など）は**安定した ID** であり、表示文言が変わっても ID は変わらない。

```
$ media-agent doctor
Media Agent doctor — /path/to/my-project
[ok]      structure.files           config.yaml / strategy.md / rules.md がそろっています
[ok]      structure.dirs            agents / memory / data / logs がそろっています
[ok]      config.syntax             config.yaml を YAML として読めます
[ok]      config.schema             設定はスキーマを満たしています
[ok]      config.version            config 版数 1
[ok]      config.consistency        content.posts_per_day (3) <= actions.post.max_per_day (3)
[ok]      db.file                   media-agent.db を SQLite として開けます
[ok]      db.schema                 スキーマ版数 1 / 6 テーブルがそろっています
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

## `media-agent status`

プロジェクト名・設定の要約・DB・登録 Agent・Task の集計を表示する。

```
$ media-agent status
Media Agent status — /path/to/my-project
project      : demo
config       : version 1 / platform x / posts_per_day 3
automation   : require_approval=false  post=auto reply=approval repost=approval like=disabled
database     : .media-agent/data/media-agent.db (schema 1)
agents       : 2 registered — echo, fail
tasks        : total 1 — pending 0 / running 0 / completed 1 / failed 0 / cancelled 0
recent tasks :
  2026-08-24T23:42:43.237954Z  completed  echo  c4b9eb04-109a-4fba-b249-7f8546fd45a5
```

Task が 1 件も無い場合、`recent tasks` は `(タスクはありません)` になる。
`--json` を付けると `project_name` / `config` / `database` / `agents` / `tasks` / `recent_tasks` を持つ JSON になる。

## `media-agent run`

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

## `media-agent agent list`

登録された Agent を一覧する。Stage 0 では組み込みの 2 種だけが登録される。

```
$ media-agent agent list
NAME  VERSION  DESCRIPTION
echo  1        入力をそのまま返す検証用の組み込み Agent
fail  1        常に失敗する検証用の組み込み Agent
```

## `media-agent task list`

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

## 終了コード

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
