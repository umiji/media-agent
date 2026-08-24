"""`project/layout.py` の単体テスト（詳細設計 4.1 / 方式設計 6.3）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from media_agent.errors import ProjectNotInitializedError
from media_agent.project.layout import (
    find_project_root,
    is_initialized,
    layout_for,
    resolve_project_root,
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
