"""`project/layout.py` の単体テスト（詳細設計 4.1 / 方式設計 6.3）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from media_agent.errors import ProjectNotInitializedError, ProjectStructureError
from media_agent.project.layout import (
    find_project_root,
    is_initialized,
    layout_for,
    resolve_project_root,
    verify_not_a_directory,
    verify_project_structure,
)


def _initialize(root: Path) -> Path:
    (root / ".media-agent").mkdir(parents=True)
    return root


def test_layout_covers_every_designed_path(tmp_path: Path) -> None:
    """詳細設計 4.1 の13項目が、`.media-agent/` 配下を指す。"""
    layout = layout_for(tmp_path)
    base = tmp_path.resolve() / ".media-agent"

    assert layout.root == tmp_path.resolve()
    assert layout.base == base
    assert layout.config_path == base / "config.yaml"
    assert layout.strategy_path == base / "strategy.md"
    assert layout.rules_path == base / "rules.md"
    assert layout.agents_dir == base / "agents"
    assert layout.memory_dir == base / "memory"
    assert layout.data_dir == base / "data"
    assert layout.db_path == base / "data" / "media-agent.db"
    assert layout.logs_dir == base / "logs"
    assert layout.log_path == base / "logs" / "media-agent.log"
    assert layout.audit_path == base / "logs" / "audit.jsonl"
    assert layout.gitignore_path == base / ".gitignore"


def test_root_is_resolved(tmp_path: Path) -> None:
    """`root` は `resolve()` 済み（申し送り K-6）。"""
    layout = layout_for(tmp_path / "sub" / "..")

    assert layout.root == tmp_path.resolve()


def test_relative_uses_posix_separators(tmp_path: Path) -> None:
    """相対表示の区切りは常に `/`（詳細設計 4.1）。"""
    layout = layout_for(tmp_path)

    assert layout.relative(layout.config_path) == ".media-agent/config.yaml"
    assert layout.relative(Path("/elsewhere/x")) == "/elsewhere/x"


def test_find_project_root_searches_upward(tmp_path: Path) -> None:
    """カレントから上位へ探索する（方式設計 6.3 の2番）。"""
    root = _initialize(tmp_path / "project")
    child = root / "a" / "b"
    child.mkdir(parents=True)

    assert find_project_root(child) == root.resolve()


def test_find_project_root_raises_when_absent(tmp_path: Path) -> None:
    """見つからなければ `ProjectNotInitializedError`（終了コード 3）。"""
    with pytest.raises(ProjectNotInitializedError) as caught:
        find_project_root(tmp_path)

    assert "Media Agent が初期化されていません" in caught.value.message
    assert str(tmp_path.resolve()) in caught.value.message
    assert caught.value.hint is not None
    assert "media-agent init" in caught.value.hint


def test_resolve_project_root_does_not_search_upward_when_explicit(
    tmp_path: Path,
) -> None:
    """`-C` があればそのディレクトリだけを見る（方式設計 6.3 の1番）。"""
    parent = _initialize(tmp_path / "parent")
    child = parent / "child"
    child.mkdir()

    assert resolve_project_root(parent, cwd=tmp_path) == parent.resolve()
    with pytest.raises(ProjectNotInitializedError):
        resolve_project_root(child, cwd=tmp_path)


def test_resolve_project_root_falls_back_to_cwd(tmp_path: Path) -> None:
    """`-C` が無ければ `cwd` から上方探索する。"""
    root = _initialize(tmp_path / "project")

    assert resolve_project_root(None, cwd=root / "deep") == root.resolve()


def test_is_initialized(tmp_path: Path) -> None:
    assert is_initialized(tmp_path) is False
    assert is_initialized(_initialize(tmp_path)) is True


# --- 構造破損の検査（詳細設計 4.1 / 17.4。T-014） ---------------------------------------


def test_verify_project_structure_passes_when_the_paths_are_directories(
    tmp_path: Path,
) -> None:
    """ディレクトリであれば何も起きない（詳細設計 17.4 の R-4）。"""
    layout = layout_for(_initialize(tmp_path))
    layout.data_dir.mkdir()
    layout.logs_dir.mkdir()

    verify_project_structure(layout, paths=(layout.data_dir, layout.logs_dir))


def test_verify_project_structure_ignores_missing_paths(tmp_path: Path) -> None:
    """**存在しないパスは異常としない**（詳細設計 17.4.1）。

    「無い」は `init` が補える不足であり、構造破損（形が違う）とは別の状況である。
    """
    layout = layout_for(_initialize(tmp_path))

    verify_project_structure(layout, paths=(layout.data_dir, layout.logs_dir))


def test_verify_project_structure_rejects_a_regular_file(tmp_path: Path) -> None:
    """通常ファイルなら `ProjectStructureError`（詳細設計 17.4 の R-1）。

    安定文字列は**絶対パス**と `ディレクトリではありません`、Hint の `退避` と
    `media-agent init`（17.3 / 17.4.3）。
    """
    layout = layout_for(_initialize(tmp_path))
    layout.logs_dir.write_text("これはディレクトリではありません\n", encoding="utf-8")

    with pytest.raises(ProjectStructureError) as excinfo:
        verify_project_structure(layout, paths=(layout.data_dir, layout.logs_dir))

    assert str(layout.logs_dir) in excinfo.value.message
    assert "ディレクトリではありません" in excinfo.value.message
    assert "退避" in (excinfo.value.hint or "")
    assert "media-agent init" in (excinfo.value.hint or "")
    assert excinfo.value.exit_code == 1


def test_verify_project_structure_does_not_repair_anything(tmp_path: Path) -> None:
    """**壊れた対象を削除も移動もしない**（詳細設計 17.4 の R-2）。復旧の主語は利用者。"""
    layout = layout_for(_initialize(tmp_path))
    layout.data_dir.write_text("利用者のファイルかもしれない\n", encoding="utf-8")

    with pytest.raises(ProjectStructureError):
        verify_project_structure(layout, paths=(layout.data_dir,))

    assert layout.data_dir.is_file()
    assert (
        layout.data_dir.read_text(encoding="utf-8") == "利用者のファイルかもしれない\n"
    )


def test_verify_project_structure_only_checks_what_it_is_given(tmp_path: Path) -> None:
    """渡されなかったパスは見ない（詳細設計 17.4 の R-4 / 17.2 の最終行）。

    `agents/` が壊れていても、`status` が検査する3つに含まれなければ止まらない。
    """
    layout = layout_for(_initialize(tmp_path))
    layout.agents_dir.write_text("壊れている\n", encoding="utf-8")

    verify_project_structure(layout, paths=(layout.data_dir, layout.logs_dir))


def test_verify_not_a_directory_rejects_a_directory(tmp_path: Path) -> None:
    """ファイルであるべき `db_path` がディレクトリなら止める（詳細設計 12.5 の preflight）。"""
    layout = layout_for(_initialize(tmp_path))
    layout.db_path.mkdir(parents=True)

    with pytest.raises(ProjectStructureError) as excinfo:
        verify_not_a_directory(layout.db_path)

    assert str(layout.db_path) in excinfo.value.message
    assert "退避" in (excinfo.value.hint or "")


def test_verify_not_a_directory_allows_a_missing_or_regular_file(
    tmp_path: Path,
) -> None:
    """無い場合と通常ファイルの場合は通す（中身の検査はここでは行わない）。"""
    layout = layout_for(_initialize(tmp_path))

    verify_not_a_directory(layout.db_path)

    layout.db_path.parent.mkdir(parents=True)
    layout.db_path.write_text("中身は見ない\n", encoding="utf-8")
    verify_not_a_directory(layout.db_path)
