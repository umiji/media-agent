"""CLI のグローバルオプションと、プロジェクト解決の入口（方式設計 6.2・6.3）。

各コマンドは `CliContext` を受け取り、**必要なものだけ**を解決する。

- `doctor` / `status` / `run` / `agent list` / `task list` は `project_root()` を呼ぶ（未初期化なら終了コード 3）
- Config が要るコマンドだけが `config()` を呼ぶ（不正なら終了コード 4）。
  `agent list` は Config を読まない（詳細設計 17.2 の注記）
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import click

from media_agent.core.config.loader import load_config
from media_agent.core.config.models import Config
from media_agent.project.layout import ProjectLayout, layout_for, resolve_project_root


@dataclass
class CliContext:
    """グローバルオプションの値と、そこから導かれる解決結果（方式設計 6.2）。"""

    project_dir: Path | None
    verbose: bool = False
    quiet: bool = False
    json_output: bool = False
    cwd: Path = Path()

    def target_dir(self) -> Path:
        """`init` の対象ディレクトリ。**上方探索しない**（方式設計 6.3 の3番）。"""
        return self.project_dir if self.project_dir is not None else self.cwd

    def project_root(self) -> Path:
        """プロジェクトルートを解決する。未初期化なら `ProjectNotInitializedError`。"""
        return resolve_project_root(self.project_dir, cwd=self.cwd)

    def layout(self) -> ProjectLayout:
        """解決済みプロジェクトの `ProjectLayout`。"""
        return layout_for(self.project_root())

    def config(self) -> Config:
        """`config.yaml` を読む。不正なら `ConfigError`（終了コード 4）。"""
        return load_config(self.layout().config_path)

    def wants_json(self, local: bool = False) -> bool:
        """`--json` はグローバルにもコマンドにも置ける（方式設計 6.2 / 詳細設計 15.3）。"""
        return self.json_output or local


#: コマンド関数へ `CliContext` を渡すデコレータ。
pass_cli_context = click.make_pass_decorator(CliContext)
