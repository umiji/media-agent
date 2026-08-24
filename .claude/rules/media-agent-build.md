# 技術スタックとビルド・テスト・リント（media-agent）

`CLAUDE.md` が200行を超えたため分割した（2026-08-24）。**内容は変えていない。**
ここは**実際に実行して通ったコマンドだけ**を置く場所である。動かないコマンドを書かない。

---

## 技術スタック

`docs/design/stage0-architecture.md` 3章で確定（却下案つき）。

| | |
| --- | --- |
| Python | >= 3.11（CI matrix 3.11 / 3.12 / 3.13） |
| CLI | Click >=8.1,<9 |
| 設定 | PyYAML `safe_load` + Pydantic v2 |
| DB | 標準ライブラリ `sqlite3` + 手書き SQL の Repository 層 |
| テスト | pytest |
| lint / format | Ruff |
| 型 | mypy（`src` のみ・非 strict） |
| ビルド | hatchling + src レイアウト |

## ビルド・テスト・リント

**下記は T-004（2026-08-24）で実際に実行して通ったコマンドである。**

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"   # 開発環境の準備

.venv/bin/pytest tests/unit                   # 単体テスト
.venv/bin/pytest tests/acceptance             # 受け入れテスト
.venv/bin/ruff check .                        # lint
.venv/bin/ruff format --check .               # 整形の検査
.venv/bin/mypy src                            # 型検査
```

**`--continue-on-collection-errors` を既定に足さないこと。** 収集エラー1件で pytest 全体が中断するのは
正しい挙動であり、本物の収集エラーを隠す。（T-006 完了までは実際に中断していた。T-007 以降は
引数なしの `pytest` が通る。）

**`.venv/bin` を PATH に置かずに実行すると、コンソールスクリプトの疎通テスト1件が落ちる。**
`shutil.which("media-agent")` が解決できないためで、不具合ではない。判定は
`PATH="$PWD/.venv/bin:$PATH" .venv/bin/pytest` の形で行うこと。

`ruff` は `docs/` を対象外にしてある。**`ruff format` が Markdown 中の Python コードブロックを
書き換えてしまうため**（T-004 が実地で確認）。この除外を外さないこと。

コンソールスクリプトの疎通テストは、**仮想環境を有効化した状態**（`.venv/bin` が PATH にある状態）で
実行すること。`.venv/bin/pytest` と前置しただけでは `shutil.which("media-agent")` が解決できない。
