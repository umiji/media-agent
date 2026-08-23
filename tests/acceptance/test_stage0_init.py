"""S-A: `media-agent init` によるプロジェクト生成。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-003 完了条件2 S-A / 要件定義書18節 Stage 0 の検証条件 |
| 期待値の正典 | 詳細設計 19章 S-A 行 → 詳細設計 12.1 / 12.3 / 12.5 / 12.6 |
| 構造 | 方式設計7章（`.media-agent/` 構造）/ 要件定義書8.1節 |
| 判定しないもの | `data/media-agent.db` の有無（申し送り N-1 / 詳細設計 12.4。DB は S-B で判定） |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.acceptance.expectations import (
    EXIT_OK,
    EXIT_RUNTIME_ERROR,
    MSG_NOT_A_DIRECTORY,
    SCAFFOLD_DIRS,
    SCAFFOLD_FILES,
    TEMPLATE_FILES,
    CliInvoke,
    base_dir,
    config_path,
    parse_scaffold_output,
    read_config,
)

pytestmark = pytest.mark.acceptance


def test_init_creates_all_scaffold_entries(project_dir: Path, cli: CliInvoke) -> None:
    """空のディレクトリで `init` すると、詳細設計 12.1 の8つの生成物が揃う。"""
    result = cli("init", project=project_dir)

    assert result.exit_code == EXIT_OK, result.output
    for relative in SCAFFOLD_FILES:
        assert (project_dir / relative).is_file(), f"{relative} が生成されていない"
    for relative in SCAFFOLD_DIRS:
        assert (project_dir / relative).is_dir(), f"{relative} が生成されていない"


def test_init_output_reports_created_for_each_entry(
    project_dir: Path, cli: CliInvoke
) -> None:
    """出力は `created  <相対パス>` の形で全生成物を報告する（詳細設計 12.6）。

    行の集合の完全一致は判定しない（T-005 で DB の行が増えるため）。
    """
    result = cli("init", project=project_dir)

    reported = parse_scaffold_output(result.stdout)
    for relative in SCAFFOLD_FILES:
        assert reported.get(relative) == "created", (
            f"{relative}: {reported.get(relative)}"
        )
    for relative in SCAFFOLD_DIRS:
        assert reported.get(f"{relative}/") == "created", (
            f"{relative}/ が報告されていない"
        )

    prefix = "Media Agent を初期化しました: "
    last_line = result.stdout.strip().splitlines()[-1]
    assert last_line.startswith(prefix)
    assert Path(last_line[len(prefix) :]).resolve() == project_dir.resolve()


def test_init_generated_config_is_valid_and_named_after_directory(
    project_dir: Path, cli: CliInvoke
) -> None:
    """生成された `config.yaml` は `load_config()` を通り、`project.name` がディレクトリ名になる。

    出所: 詳細設計 12.3（`{{PROJECT_NAME}}` の決め方）/ 5.2.1。
    """
    assert cli("init", project=project_dir).exit_code == EXIT_OK

    config = read_config(project_dir)
    assert config.project.name == project_dir.resolve().name


def test_init_is_idempotent_and_preserves_existing_files(
    project_dir: Path, cli: CliInvoke
) -> None:
    """2回目の `init` も終了コード 0 で、既存ファイルの内容が変わらない（詳細設計 12.5）。"""
    assert cli("init", project=project_dir).exit_code == EXIT_OK

    edited = project_dir / ".media-agent" / "strategy.md"
    edited.write_text("# 利用者が書き換えた戦略\n", encoding="utf-8")
    before = {
        rel: (project_dir / rel).read_text(encoding="utf-8") for rel in TEMPLATE_FILES
    }

    result = cli("init", project=project_dir)

    assert result.exit_code == EXIT_OK, result.output
    for relative, content in before.items():
        assert (project_dir / relative).read_text(encoding="utf-8") == content, relative

    reported = parse_scaffold_output(result.stdout)
    for relative in SCAFFOLD_FILES:
        assert reported.get(relative) == "skipped", (
            f"{relative}: {reported.get(relative)}"
        )


def test_init_force_restores_templates_without_touching_user_data(
    project_dir: Path, cli: CliInvoke
) -> None:
    """`--force` はテンプレート由来の4ファイルだけを上書きする（詳細設計 12.5）。

    `data/` `logs/` の中身、`agents/` の利用者ファイル、`memory/` の中身には触れない。
    """
    assert cli("init", project=project_dir).exit_code == EXIT_OK
    original = {
        rel: (project_dir / rel).read_text(encoding="utf-8") for rel in TEMPLATE_FILES
    }

    for relative in TEMPLATE_FILES:
        (project_dir / relative).write_text("# 壊した\n", encoding="utf-8")
    user_agent = base_dir(project_dir) / "agents" / "my-agent.md"
    user_agent.write_text("# 利用者の Custom Agent\n", encoding="utf-8")
    user_memory = base_dir(project_dir) / "memory" / "note.md"
    user_memory.write_text("記憶\n", encoding="utf-8")
    user_data = base_dir(project_dir) / "data" / "keep.txt"
    user_data.write_text("データ\n", encoding="utf-8")

    result = cli("init", "--force", project=project_dir)

    assert result.exit_code == EXIT_OK, result.output
    for relative, content in original.items():
        assert (project_dir / relative).read_text(encoding="utf-8") == content, relative
    assert user_agent.read_text(encoding="utf-8") == "# 利用者の Custom Agent\n"
    assert user_memory.read_text(encoding="utf-8") == "記憶\n"
    assert user_data.read_text(encoding="utf-8") == "データ\n"

    reported = parse_scaffold_output(result.stdout)
    for relative in TEMPLATE_FILES:
        assert reported.get(relative) == "updated", (
            f"{relative}: {reported.get(relative)}"
        )


def test_init_does_not_touch_claude_dir_or_root_gitignore(
    project_dir: Path, cli: CliInvoke
) -> None:
    """`init` は `.claude/` とプロジェクトルート直下の `.gitignore` に触れない。

    出所: 方式設計7章・罠 T-1、詳細設計 12.1。
    """
    root_gitignore = project_dir / ".gitignore"
    root_gitignore.write_text("*.log\n", encoding="utf-8")

    assert cli("init", project=project_dir).exit_code == EXIT_OK

    assert root_gitignore.read_text(encoding="utf-8") == "*.log\n"
    assert not (project_dir / ".claude").exists()


def test_init_does_not_search_upward(tmp_path: Path, cli: CliInvoke) -> None:
    """`init` はプロジェクトルートを上方探索せず、対象ディレクトリ自身に作る。

    出所: 方式設計 6.3（3番）/ 詳細設計 12.6。
    """
    parent = tmp_path / "parent"
    child = parent / "child"
    child.mkdir(parents=True)
    assert cli("init", project=parent).exit_code == EXIT_OK

    assert cli("init", project=child).exit_code == EXIT_OK

    assert base_dir(child).is_dir()
    assert config_path(child).is_file()


def test_init_fails_when_media_agent_is_a_file(
    project_dir: Path, cli: CliInvoke
) -> None:
    """`.media-agent` がファイルとして存在する場合は `ScaffoldError`（終了コード 1）。

    出所: 詳細設計 12.5 / 17.1。安定文字列は `ディレクトリではありません`。
    """
    base_dir(project_dir).write_text("これはファイル\n", encoding="utf-8")

    result = cli("init", project=project_dir)

    assert result.exit_code == EXIT_RUNTIME_ERROR
    assert MSG_NOT_A_DIRECTORY in result.stderr
