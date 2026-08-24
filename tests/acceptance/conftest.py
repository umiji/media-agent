"""受け入れテスト共通の fixture（S-A〜S-I）。

判定してよい契約と共通ヘルパは `tests/acceptance/expectations.py` にある。
**このファイルは `media_agent` をモジュール先頭で import しない**（fixture の内側で行う）。
理由は方式設計 17.2 の順序制約 O-2（T-003 の時点でパッケージが存在しない）。
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.acceptance.expectations import (
    EXIT_OK,
    CliInvoke,
    RuntimeStack,
    build_runtime_stack,
)


def _cli_runner() -> Any:
    """`click.testing.CliRunner` を返す（方式設計 10.2 / 罠 T-5）。"""
    from click.testing import CliRunner

    return CliRunner()


@pytest.fixture()
def cli() -> CliInvoke:
    """`media-agent` をインプロセスで実行する（方式設計 10.2）。

    `project` を渡すとグローバルオプション `-C/--project-dir` を前置する（方式設計 6.2）。
    `catch_exceptions=False`: 例外→終了コードの変換は CLI 層の責務（品質基準 Q8）であり、
    外へ漏れた例外を CliRunner が終了コード 1 へ丸めると不具合が見えなくなる。

    製品が未実装のうちは `ModuleNotFoundError` になる。これが T-003 時点の正しい状態である
    （方式設計 17.2 の順序制約 O-2）。
    """
    from media_agent.cli.app import main

    runner = _cli_runner()

    def _invoke(*args: Any, project: Path | str | None = None) -> Any:
        argv: list[str] = []
        if project is not None:
            argv += ["-C", str(project)]
        argv += [str(a) for a in args]
        return runner.invoke(main, argv, catch_exceptions=False)

    return _invoke


@pytest.fixture()
def initialized_project(tmp_path: Path, cli: CliInvoke) -> Path:
    """`media-agent init` 済みの一時プロジェクト（方式設計 10.3）。

    S-B / S-C / S-E〜S-I が共有する。ディレクトリ名がそのまま `project.name` になる
    （詳細設計 12.3）ため、名前を固定して判定に使えるようにする。
    """
    project = tmp_path / "sample-project"
    project.mkdir()
    result = cli("init", project=project)
    assert result.exit_code == EXIT_OK, result.output
    return project


@pytest.fixture()
def runtime_stack(initialized_project: Path) -> Iterator[RuntimeStack]:
    """公開 API で組み立てた Runtime 一式（S-E / S-F / S-H）。"""
    stack = build_runtime_stack(initialized_project)
    try:
        yield stack
    finally:
        stack.conn.close()
