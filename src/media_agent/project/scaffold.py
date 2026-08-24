"""`media-agent init` の生成処理（詳細設計12章）。

**触ってよいのは `.media-agent/` 配下だけ**である（用語集「スキャフォールド」）。
プロジェクトルート直下の `.gitignore` にも `.claude/` にも触れない（罠 T-1）。

既存の扱い（詳細設計 12.5）:

- 既定は「不足しているものだけを作り、既存のファイルには一切触れない」（冪等）
- `--force` は**テンプレート由来の4ファイルだけ**を上書きする。
  `data/` `logs/` の中身、`agents/` の利用者ファイル、`memory/` の中身は対象外
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Literal

from media_agent.core.config.loader import load_config
from media_agent.errors import ConfigError, ScaffoldError
from media_agent.project.layout import ProjectLayout, layout_for

#: `{{PROJECT_NAME}}` が決まらないときの代替（詳細設計 12.3）。
FALLBACK_PROJECT_NAME = "my-project"

_PLACEHOLDER = "{{PROJECT_NAME}}"
_TEMPLATE_PACKAGE = "media_agent.project"
_TEMPLATE_DIR = "templates"

ScaffoldAction = Literal["created", "skipped", "updated"]


@dataclass(frozen=True)
class ScaffoldEntry:
    """生成物1件の結果（詳細設計 12.7）。"""

    path: Path
    relative: str
    action: ScaffoldAction


@dataclass(frozen=True)
class ScaffoldResult:
    """`init` の結果（詳細設計 12.7）。"""

    layout: ProjectLayout
    entries: tuple[ScaffoldEntry, ...]

    def action_for(self, relative: str) -> ScaffoldAction | None:
        """相対パスに対応する結果を返す（単体テストと `init` コマンドが使う）。"""
        for entry in self.entries:
            if entry.relative == relative:
                return entry.action
        return None


def read_template(name: str) -> str:
    """テンプレートを読む。

    `importlib.resources` を使う（罠 T-4 / D-T17）。`__file__` 相対で読むと、
    将来 zip 配布や別の実行形態で壊れる。
    """
    return (
        resources.files(_TEMPLATE_PACKAGE)
        .joinpath(_TEMPLATE_DIR, name)
        .read_text(encoding="utf-8")
    )


def project_name_for(root: Path) -> str:
    """`{{PROJECT_NAME}}` に入れる値を決める（詳細設計 12.3）。"""
    name = root.resolve().name.strip()
    return name or FALLBACK_PROJECT_NAME


def render_config_template(project_name: str) -> str:
    """`config.yaml` のテンプレートへプロジェクト名を埋める（詳細設計 12.3）。

    テンプレート側が `"` を含むため、YAML のスカラとして安全になるよう
    `\\` と `"` をエスケープしてから差し込む。
    """
    escaped = project_name.replace("\\", "\\\\").replace('"', '\\"')
    return read_template("config.yaml").replace(_PLACEHOLDER, escaped)


def init_project(root: Path, *, force: bool = False) -> ScaffoldResult:
    """`.media-agent/` を生成する（詳細設計 12.1・12.5）。

    Raises:
        ScaffoldError: `.media-agent` がディレクトリでない、または
            **自分が生成した** `config.yaml` が検証を通らない（詳細設計 12.3）
    """
    layout = layout_for(root)
    _ensure_base_dir(layout)

    entries: list[ScaffoldEntry] = []
    entries.append(
        _write_file(
            layout,
            layout.config_path,
            render_config_template(project_name_for(root)),
            force=force,
        )
    )
    entries.append(
        _write_file(
            layout, layout.strategy_path, read_template("strategy.md"), force=force
        )
    )
    entries.append(
        _write_file(layout, layout.rules_path, read_template("rules.md"), force=force)
    )
    entries.append(_write_file(layout, layout.agents_dir / ".gitkeep", "", force=False))
    entries.append(_write_file(layout, layout.memory_dir / ".gitkeep", "", force=False))
    entries.append(_make_dir(layout, layout.data_dir))
    entries.append(_make_dir(layout, layout.logs_dir))
    entries.append(
        _write_file(
            layout, layout.gitignore_path, read_template("gitignore"), force=force
        )
    )

    result = ScaffoldResult(layout=layout, entries=tuple(entries))
    _verify_generated_config(result)
    return result


def _ensure_base_dir(layout: ProjectLayout) -> None:
    """`.media-agent/` を用意する。ファイルとして存在する場合は `ScaffoldError`。"""
    if layout.base.exists() and not layout.base.is_dir():
        raise ScaffoldError(
            f"{layout.base} はディレクトリではありません",
            hint="このパスにあるファイルを退避してから、もう一度実行してください",
        )
    layout.base.mkdir(parents=True, exist_ok=True)


def _write_file(
    layout: ProjectLayout, path: Path, content: str, *, force: bool
) -> ScaffoldEntry:
    """ファイルを生成する。既存なら `skipped`（`force` 指定時のみ `updated`）。"""
    relative = layout.relative(path)
    if path.exists():
        if not force:
            return ScaffoldEntry(path=path, relative=relative, action="skipped")
        path.write_text(content, encoding="utf-8")
        return ScaffoldEntry(path=path, relative=relative, action="updated")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return ScaffoldEntry(path=path, relative=relative, action="created")


def _make_dir(layout: ProjectLayout, path: Path) -> ScaffoldEntry:
    """ディレクトリを生成する。相対パスは末尾に `/` を付けて表示する（詳細設計 12.6）。"""
    relative = f"{layout.relative(path)}/"
    if path.is_dir():
        return ScaffoldEntry(path=path, relative=relative, action="skipped")
    path.mkdir(parents=True, exist_ok=True)
    return ScaffoldEntry(path=path, relative=relative, action="created")


def _verify_generated_config(result: ScaffoldResult) -> None:
    """**自分が生成した** `config.yaml` だけを検証する（詳細設計 12.3 / 申し送り M-4）。

    既存の `config.yaml`（`skipped`）は検証しない。既存が壊れていても `init` は
    終了コード 0 で終わる（詳細設計 17.2 の3行目）。生成物を補う機会を奪わないため。
    """
    config_relative = result.layout.relative(result.layout.config_path)
    if result.action_for(config_relative) not in ("created", "updated"):
        return
    try:
        load_config(result.layout.config_path)
    except ConfigError as exc:
        raise ScaffoldError(
            f"生成した config.yaml が検証を通りませんでした: {result.layout.config_path}",
            details=list(exc.details),
        ) from exc
