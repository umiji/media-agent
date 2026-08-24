# 開発者向け

## 開発環境

```sh
git clone https://github.com/umiji/media-agent.git
cd media-agent
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## テスト・リント・型検査

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

## CI

`.github/workflows/ci.yml` が `push` と `pull_request` で走る。
Python 3.11 / 3.12 / 3.13 の 3 通りで、`ruff check` → `ruff format --check` → `mypy src` → `pytest` を実行する。
**CI は認証情報（secrets）を一切使わない。**

## ソース構成

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

## 技術スタック

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

## バージョン

`src/media_agent/__init__.py` の `__version__` が唯一の真実で、`pyproject.toml` はそこから読む。

**版数は 3 つあり、互いに独立している。混同しないこと。**

| 版数 | どこ | 何の版数か |
| --- | --- | --- |
| パッケージ版数 | `__version__` | Media Agent 本体 |
| 設定の構造版数 | `config.yaml` の `version` | 設定ファイルの構造 |
| DB のスキーマ版数 | SQLite の `user_version` | DB の構造 |

（監査記録の各行が持つ `schema_version` も、これらとは独立している。）

## 設計と決定の記録

**「なぜその方式にしたか」は README ではなく設計成果物にある。**

| 文書 | 内容 |
| --- | --- |
| `docs/design/stage0-architecture.md` | 方式設計。全体構成、技術選定と却下案、CLI 設計、終了コード |
| `docs/design/stage0-detail.md` | 詳細設計。Config / DB / Agent / Task / Policy / Logging・Audit |
| `docs/requirements-media-agent-v0.2.md` | 要件定義書 v0.2 |
| `docs/glossary.md` | このリポジトリで意味が決まっている語 |
