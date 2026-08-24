# Stage 0 動作確認手順書

**この文書は、Media Agent の Stage 0（Media Agent Core）が手元で動くことを、自分で確かめるための手順書である。**
上から順にコピーして実行すれば終わる。所要時間は 5〜10 分（依存パッケージの取得時間を除く）。

## 確認する範囲

Stage 0 の検証条件は次の 1 行である。

> `media-agent init` → Project 生成 → `media-agent doctor` → `media-agent status` が正常動作すること。

本書は上記に加えて、Agent の実行・記録、未実装コマンドの扱い、外部接続が無いことまでを確認する。

## 確認しないこと（Stage 0 に無いもの）

- X（旧 Twitter）への投稿・返信 — **Stage 0 には投稿機能そのものが存在しない**
- ニュース・RSS からの情報収集、AI によるコンテンツ生成 — Stage 1 / Stage 2

## 認証情報は不要である

**この手順書のどこでも、API キー・アクセストークン・パスワードを入力しない。**
Media Agent は Stage 0 で外部サービスへ一切接続しないため、認証情報を置く場所も、要求する箇所も無い。
**もし手順の途中で認証情報の入力を求められたら、それは異常である。** 最後の「期待どおりにならなかった場合」を参照。

---

## 前提

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

## 手順 1 — リポジトリを取得する

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

## 手順 2 — 仮想環境を作り、インストールする

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

## 手順 3 — インストールされたことを確認する

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

## 手順 4 — 確認用のプロジェクトを作る

**Media Agent 本体のリポジトリの中ではなく、別のディレクトリで実行する。**
Media Agent は「導入先のプロジェクト」で使う道具だからである。

```sh
mkdir -p ~/media-agent-check/demo-project && cd ~/media-agent-check/demo-project
pwd
```

## 手順 5 — `media-agent init`（Project 生成）

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

## 手順 6 — `media-agent doctor`（検証）

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
EXIT=0
```

**確認すること**:

- 最終行が `0 fail` であること
- **`security.env_not_tracked` が `[skipped]` であること。** 認証情報が無いことを異常として扱っていない
- `runtime.python` の版数は環境により `3.12` / `3.13` になることがある。それでよい

## 手順 7 — `media-agent status`（状態表示）

```sh
media-agent status
echo "EXIT=$?"
```

期待される出力:

```
Media Agent status — /home/you/media-agent-check/demo-project
project      : demo-project
config       : version 1 / platform x / posts_per_day 3
automation   : require_approval=false  post=auto reply=approval repost=approval like=disabled
database     : .media-agent/data/media-agent.db (schema 1)
agents       : 2 registered — echo, fail
tasks        : total 0 — pending 0 / running 0 / completed 0 / failed 0 / cancelled 0
recent tasks :
  (タスクはありません)
EXIT=0
```

**ここまでで Stage 0 の検証条件（`init` → Project 生成 → `doctor` → `status`）を満たしている。**
以降は、Core が実際に動いていることの追加確認である。

## 手順 8 — Agent を実行し、記録されることを確認する

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

## 手順 9 — 失敗が失敗として記録されることを確認する

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

## 手順 10 — 未実装のコマンドが「未実装」として振る舞うことを確認する

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

## 手順 11 — 未初期化のディレクトリで正しく止まることを確認する

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

## 手順 12 — 外部へ接続していないことを確認する（任意）

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

## 手順 13 — テストが通ることを確認する（任意）

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

## 手順 14 — 後片付け

確認用に作ったものはすべて 1 か所にある。消せば元に戻る。

```sh
cd ~
rm -rf ~/media-agent-check
```

Media Agent 自身は `~/media-agent-check` の外へ何も書き込まない（仮想環境もリポジトリの中にある）。
**残るのは `pip` のダウンロードキャッシュ（`~/.cache/pip`）だけである。** 気になる場合は
`.venv/bin/python -m pip cache purge` で消せる。

---

## 確認結果のチェックリスト

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

## 期待どおりにならなかった場合

**手順書を書き換えて辻褄を合わせないこと。** 期待と違ったなら、手順書か実装のどちらかが誤っている。

### 1. 次の 4 つを控える

| 控えるもの | 取り方 |
| --- | --- |
| 実行したコマンド | 手順番号でよい |
| 実際の出力（全文） | 端末からコピーする |
| 実際の終了コード | 直後に `echo "EXIT=$?"` |
| 環境 | `python3 --version` と `uname -a`、`git log --oneline -1` |

### 2. 追加で取れると原因が早く分かるもの

```sh
media-agent doctor --json
media-agent -v status                      # 詳細な運用ログが標準エラーへ出る
cat .media-agent/logs/media-agent.log
```

**`audit.jsonl` と `media-agent.log` に秘密値は出力されない設計だが、共有する前に中身を一読すること。**

### 3. 渡す先

開発セッション（オーケストレーター）へ、上記を添えて伝える。
不具合として扱うか、手順書の誤りとして扱うかは、そこで切り分ける。
GitHub の Issue へ登録する場合も同じ内容を書く。

### よくある食い違い

| 症状 | 原因として考えられること |
| --- | --- |
| `media-agent: command not found` | 手順 2 の `export PATH=...` を実行していない。`.venv/bin/media-agent` と書けば動く |
| `doctor` / `status` が終了コード 3 | `.media-agent/` の無いディレクトリで実行している。手順 4 のディレクトリへ移動する |
| 終了コード 4 が出る | `config.yaml` を編集して壊した。`media-agent doctor` が該当キーを示す |
| `run --agent fail` でトレースバックが出る | **想定どおり。** `fail` は失敗を確認するための Agent である |
| `runtime.python` の版数が違う | 3.11 以上なら問題ない |
