# はじめての Media Agent

インストール済みであることを前提に、Stage 0 でできることを一通り動かす。**外部サービスへは接続しない。**

## 1. プロジェクトを初期化する

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

## 2. 健全性を確認する

```sh
media-agent doctor
```

15 項目の検査結果と `結果: 14 ok / 0 warn / 1 skipped / 0 fail` が出れば正常。
`.env` が無いことは異常ではない（`security.env_not_tracked` が `[skipped]`）。

## 3. 現在の状態を見る

```sh
media-agent status
```

```
project      : my-project
config       : version 1 / platform x / posts_per_day 3
automation   : require_approval=false  post=auto reply=approval repost=approval like=disabled
database     : .media-agent/data/media-agent.db (schema 1)
agents       : 2 registered — echo, fail
tasks        : total 0 — pending 0 / running 0 / completed 0 / failed 0 / cancelled 0
recent tasks :
  (タスクはありません)
```

## 4. Agent を実行する

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

## 5. 記録を確認する

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

```json
{"action": null, "agent": "echo", "decision": "echo", "decision_id": "e26c7f97-...", "error": null,
 "input": {"message": "hello"}, "kind": "agent_run",
 "reason": "組み込みの検証用 Agent のため、入力をそのまま返した", "result": {"message": "hello"},
 "schema_version": 1, "task": "c4b9eb04-...", "timestamp": "2026-08-24T23:42:43.238855Z"}
```

（実際は 1 行だが、ここでは読みやすさのために折り返している。）

人が動作を追うための運用ログは別のファイルにある。

```sh
tail .media-agent/logs/media-agent.log
```

```
2026-08-24T23:42:43.238370Z INFO     media_agent.cli agent=echo task=c4b9eb04-... started
2026-08-24T23:42:43.240740Z INFO     media_agent.cli agent=echo task=c4b9eb04-... completed elapsed=0.002s
```

## 6. 設定を変える

`.media-agent/config.yaml` を編集し、`media-agent doctor` で検証する。
壊れていれば `[fail]` の行が出て終了コード 5 になる。

```sh
media-agent doctor --json | head
```

`--json` は `doctor` / `status` / `run` / `agent list` / `task list` で使える。

## ここから先

- 何が動いて何が動かないか → 「Stage 0 でできること・できないこと」
- コマンドとオプションの一覧 → 「CLI リファレンス」
- `.media-agent/` の中身 → 「プロジェクトディレクトリ `.media-agent/`」
