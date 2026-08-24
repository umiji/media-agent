"""プロジェクトルートの探索と `.media-agent/` 配下のパス解決（詳細設計 4.1）。

`core/` は `.media-agent` というパスを組み立てない。必ず `ProjectLayout` か
個別の `Path` を引数で受け取る（品質基準 Q7）。**その規約を守れるようにするのが本モジュールである。**
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from media_agent.errors import ProjectNotInitializedError

#: `.media-agent/` ディレクトリの名前。**この文字列はこのモジュールにだけ置く。**
BASE_DIR_NAME = ".media-agent"


@dataclass(frozen=True)
class ProjectLayout:
    """`.media-agent/` 配下のパスをまとめた解決結果（詳細設計 4.1）。"""

    root: Path
    base: Path
    config_path: Path
    strategy_path: Path
    rules_path: Path
    agents_dir: Path
    memory_dir: Path
    data_dir: Path
    db_path: Path
    logs_dir: Path
    log_path: Path
    audit_path: Path
    gitignore_path: Path

    def relative(self, path: Path) -> str:
        """`root` からの相対表示（区切りは常に `/`。詳細設計 4.1）。"""
        try:
            relative = path.relative_to(self.root)
        except ValueError:
            return str(path)
        return str(PurePosixPath(*relative.parts))


def layout_for(root: Path) -> ProjectLayout:
    """プロジェクトルートから `ProjectLayout` を作る。

    `root` は `resolve()` してから保持する。表示・比較に現れるパスを1つに定めるため
    （申し送り K-6）。
    """
    resolved = root.resolve()
    base = resolved / BASE_DIR_NAME
    data_dir = base / "data"
    logs_dir = base / "logs"
    return ProjectLayout(
        root=resolved,
        base=base,
        config_path=base / "config.yaml",
        strategy_path=base / "strategy.md",
        rules_path=base / "rules.md",
        agents_dir=base / "agents",
        memory_dir=base / "memory",
        data_dir=data_dir,
        db_path=data_dir / "media-agent.db",
        logs_dir=logs_dir,
        log_path=logs_dir / "media-agent.log",
        audit_path=logs_dir / "audit.jsonl",
        gitignore_path=base / ".gitignore",
    )


def is_initialized(root: Path) -> bool:
    """`root` が初期化済み（`.media-agent/` を持つ）か。"""
    return (root / BASE_DIR_NAME).is_dir()


def find_project_root(start: Path) -> Path:
    """`start` から上位へ `.media-agent/` を探索する（方式設計 6.3 の2番）。

    ファイルシステムのルートまで見つからなければ `ProjectNotInitializedError`。
    """
    current = start.resolve()
    for candidate in (current, *current.parents):
        if is_initialized(candidate):
            return candidate
    raise _not_initialized(current)


def resolve_project_root(explicit: Path | None, *, cwd: Path) -> Path:
    """CLI のプロジェクトルート決定（方式設計 6.3 の1番・2番）。

    `-C/--project-dir`（または `MEDIA_AGENT_PROJECT_DIR`）が与えられていれば
    **上方探索せず**そのディレクトリを対象にする。与えられていなければ `cwd` から上方探索する。
    """
    if explicit is None:
        return find_project_root(cwd)
    root = explicit.resolve()
    if not is_initialized(root):
        raise _not_initialized(root)
    return root


def _not_initialized(root: Path) -> ProjectNotInitializedError:
    """未初期化エラー（安定文字列は詳細設計 17.3）。"""
    return ProjectNotInitializedError(
        f"Media Agent が初期化されていません: {root}",
        hint="media-agent init を実行してプロジェクトを初期化してください",
    )
