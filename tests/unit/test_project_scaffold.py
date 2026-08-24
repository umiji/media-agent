"""`project/scaffold.py` の単体テスト（詳細設計12章）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from media_agent.core.config.loader import load_config
from media_agent.errors import ScaffoldError
from media_agent.project.scaffold import (
    FALLBACK_PROJECT_NAME,
    init_project,
    project_name_for,
    read_template,
    render_config_template,
)

#: 詳細設計 12.1 の8つの生成物（相対パス）。
EXPECTED_ENTRIES: tuple[str, ...] = (
    ".media-agent/config.yaml",
    ".media-agent/strategy.md",
    ".media-agent/rules.md",
    ".media-agent/agents/.gitkeep",
    ".media-agent/memory/.gitkeep",
    ".media-agent/data/",
    ".media-agent/logs/",
    ".media-agent/.gitignore",
)

TEMPLATE_ENTRIES: tuple[str, ...] = (
    ".media-agent/config.yaml",
    ".media-agent/strategy.md",
    ".media-agent/rules.md",
    ".media-agent/.gitignore",
)


def test_creates_the_designed_entries_in_order(tmp_path: Path) -> None:
    """8つの生成物を、詳細設計 12.6 の順で報告する。"""
    result = init_project(tmp_path)

    assert tuple(entry.relative for entry in result.entries) == EXPECTED_ENTRIES
    assert all(entry.action == "created" for entry in result.entries)
    for entry in result.entries:
        assert entry.path.exists()


def test_templates_are_read_from_package_data() -> None:
    """テンプレートは `importlib.resources` で読む（罠 T-4 / D-T17）。"""
    assert "{{PROJECT_NAME}}" in read_template("config.yaml")
    assert read_template("gitignore").splitlines()[1:3] == ["data/", "logs/"]
    assert read_template("strategy.md").startswith("# メディア戦略")
    assert read_template("rules.md").startswith("# 運用ルール")


def test_generated_config_is_named_after_the_directory(tmp_path: Path) -> None:
    """`{{PROJECT_NAME}}` はディレクトリ名（詳細設計 12.3）。"""
    project = tmp_path / "my-media"
    project.mkdir()

    result = init_project(project)

    assert load_config(result.layout.config_path).project.name == "my-media"


def test_project_name_falls_back_when_empty(tmp_path: Path) -> None:
    """ディレクトリ名が取れないときは `my-project`（詳細設計 12.3）。"""
    assert project_name_for(Path("/")) == FALLBACK_PROJECT_NAME
    assert project_name_for(tmp_path) == tmp_path.name


def test_project_name_is_escaped_for_yaml(tmp_path: Path) -> None:
    """`\\` と `"` をエスケープしてダブルクォートの中へ入れる（詳細設計 12.3）。"""
    rendered = render_config_template('a"b\\c')

    assert 'name: "a\\"b\\\\c"' in rendered

    project = tmp_path / 'quo"te'
    project.mkdir()
    result = init_project(project)
    assert load_config(result.layout.config_path).project.name == 'quo"te'


def test_second_run_skips_everything(tmp_path: Path) -> None:
    """冪等。既存には触れない（詳細設計 12.5）。"""
    init_project(tmp_path)
    edited = tmp_path / ".media-agent" / "strategy.md"
    edited.write_text("書き換えた\n", encoding="utf-8")

    result = init_project(tmp_path)

    assert all(entry.action == "skipped" for entry in result.entries)
    assert edited.read_text(encoding="utf-8") == "書き換えた\n"


def test_missing_entries_are_restored(tmp_path: Path) -> None:
    """不足しているものだけを作る（詳細設計 12.5）。"""
    init_project(tmp_path)
    (tmp_path / ".media-agent" / "rules.md").unlink()

    result = init_project(tmp_path)

    assert result.action_for(".media-agent/rules.md") == "created"
    assert result.action_for(".media-agent/config.yaml") == "skipped"


def test_force_updates_only_template_files(tmp_path: Path) -> None:
    """`--force` の対象はテンプレート由来の4ファイルだけ（詳細設計 12.5）。"""
    init_project(tmp_path)
    for relative in TEMPLATE_ENTRIES:
        (tmp_path / relative).write_text("壊した\n", encoding="utf-8")
    gitkeep = tmp_path / ".media-agent" / "agents" / ".gitkeep"
    gitkeep.write_text("利用者が書いた\n", encoding="utf-8")

    result = init_project(tmp_path, force=True)

    for relative in TEMPLATE_ENTRIES:
        assert result.action_for(relative) == "updated"
        assert (tmp_path / relative).read_text(encoding="utf-8") != "壊した\n"
    assert result.action_for(".media-agent/agents/.gitkeep") == "skipped"
    assert gitkeep.read_text(encoding="utf-8") == "利用者が書いた\n"


def test_user_data_is_never_touched(tmp_path: Path) -> None:
    """`data/` `logs/` `agents/` `memory/` の中身は `--force` でも触らない。"""
    init_project(tmp_path)
    files = {
        tmp_path / ".media-agent" / "data" / "keep.txt": "データ\n",
        tmp_path / ".media-agent" / "logs" / "keep.log": "ログ\n",
        tmp_path / ".media-agent" / "memory" / "note.md": "記憶\n",
        tmp_path / ".media-agent" / "agents" / "my-agent.md": "定義\n",
    }
    for path, content in files.items():
        path.write_text(content, encoding="utf-8")

    init_project(tmp_path, force=True)

    for path, content in files.items():
        assert path.read_text(encoding="utf-8") == content


def test_root_gitignore_and_claude_dir_are_untouched(tmp_path: Path) -> None:
    """プロジェクト直下の `.gitignore` と `.claude/` に触れない（罠 T-1）。"""
    root_gitignore = tmp_path / ".gitignore"
    root_gitignore.write_text("*.log\n", encoding="utf-8")

    init_project(tmp_path)

    assert root_gitignore.read_text(encoding="utf-8") == "*.log\n"
    assert not (tmp_path / ".claude").exists()


def test_base_path_as_file_is_an_error(tmp_path: Path) -> None:
    """`.media-agent` がファイルなら `ScaffoldError`（詳細設計 12.5）。"""
    (tmp_path / ".media-agent").write_text("ファイル\n", encoding="utf-8")

    with pytest.raises(ScaffoldError) as caught:
        init_project(tmp_path)

    assert "ディレクトリではありません" in caught.value.message


def test_existing_broken_config_is_not_validated(tmp_path: Path) -> None:
    """検証するのは **`init` 自身が生成したもの**だけ（申し送り M-4 / 詳細設計 12.3）。"""
    init_project(tmp_path)
    broken = tmp_path / ".media-agent" / "config.yaml"
    broken.write_text("- 壊れている\n", encoding="utf-8")

    result = init_project(tmp_path)

    assert result.action_for(".media-agent/config.yaml") == "skipped"
    assert broken.read_text(encoding="utf-8") == "- 壊れている\n"


def test_generated_config_is_validated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """生成した `config.yaml` が検証を通らなければ `ScaffoldError`（詳細設計 12.3）。"""
    monkeypatch.setattr(
        "media_agent.project.scaffold.render_config_template",
        lambda name: "version: 1\nproject:\n  namae: typo\n",
    )

    with pytest.raises(ScaffoldError) as caught:
        init_project(tmp_path)

    assert "config.yaml" in caught.value.message


def test_db_file_is_not_created(tmp_path: Path) -> None:
    """DB は `init` の生成物に含めない（順序制約 O-1 / 詳細設計 12.4。T-005 が接続する）。"""
    result = init_project(tmp_path)

    assert not result.layout.db_path.exists()
