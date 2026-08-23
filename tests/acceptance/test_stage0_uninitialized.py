"""S-D: 未初期化ディレクトリでの挙動と、スタブコマンド。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-003 完了条件2 S-D / 要件定義書18節 Stage 0 |
| 期待値の正典 | 詳細設計 19章 S-D 行 → 詳細設計 17.2（コマンド × 状況の一覧）/ 17.3 |
| 終了コード | 方式設計 6.5 の終了コード表 |
| 判定の軸 | 終了コードと 17.3 の安定文字列だけ（申し送り N-4）。文面全体は判定しない |
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.acceptance.expectations import (
    EXIT_NOT_IMPLEMENTED,
    EXIT_NOT_INITIALIZED,
    EXIT_OK,
    EXIT_USAGE,
    MSG_INIT_HINT,
    MSG_NOT_INITIALIZED,
    MSG_STUB_STAGE,
    MSG_STUB_UNIMPLEMENTED,
    STUB_COMMANDS,
    CliInvoke,
)

pytestmark = pytest.mark.acceptance

#: 未初期化のときに終了コード 3 で終わるコマンド（詳細設計 17.2 の1行目）。
PROJECT_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("doctor",),
    ("status",),
    ("run",),
    ("agent", "list"),
    ("task", "list"),
)


@pytest.mark.parametrize("command", PROJECT_COMMANDS, ids=lambda c: " ".join(c))
def test_commands_fail_clearly_when_not_initialized(
    project_dir: Path, cli: CliInvoke, command: tuple[str, ...]
) -> None:
    """未初期化ディレクトリでは終了コード 3 と明確なエラーで終わる。沈黙して成功しない。"""
    result = cli(*command, project=project_dir)

    assert result.exit_code == EXIT_NOT_INITIALIZED, result.output
    assert MSG_NOT_INITIALIZED in result.stderr
    assert (
        str(project_dir) in result.stderr or str(project_dir.resolve()) in result.stderr
    )
    assert MSG_INIT_HINT in result.stderr
    assert result.stdout.strip() == "", "失敗時に成功を示す出力を出さないこと"


@pytest.mark.parametrize("command", STUB_COMMANDS)
def test_stub_commands_exit_with_code_10_when_not_initialized(
    project_dir: Path, cli: CliInvoke, command: str
) -> None:
    """スタブ4種はプロジェクトの状態を見る前に終了コード 10 で終わる（詳細設計 17.2）。"""
    result = cli(command, project=project_dir)

    assert result.exit_code == EXIT_NOT_IMPLEMENTED, result.output
    assert MSG_STUB_STAGE in result.stderr
    assert MSG_STUB_UNIMPLEMENTED in result.stderr
    assert result.stdout.strip() == ""


@pytest.mark.parametrize("command", STUB_COMMANDS)
def test_stub_commands_exit_with_code_10_on_initialized_project(
    initialized_project: Path, cli: CliInvoke, command: str
) -> None:
    """初期化済みでもスタブは 10。未実装であることは環境に依存しない（詳細設計 17.2）。"""
    result = cli(command, project=initialized_project)

    assert result.exit_code == EXIT_NOT_IMPLEMENTED, result.output
    assert MSG_STUB_UNIMPLEMENTED in result.stderr


def test_help_and_version_succeed_without_a_project(
    project_dir: Path, cli: CliInvoke
) -> None:
    """`--help` / `--version` はプロジェクトの解決より前に終了する（詳細設計 17.2）。"""
    assert cli("--help", project=project_dir).exit_code == EXIT_OK
    assert cli("--version", project=project_dir).exit_code == EXIT_OK


@pytest.mark.parametrize(
    "command", [*PROJECT_COMMANDS, ("init",)], ids=lambda c: " ".join(c)
)
def test_missing_project_dir_is_a_usage_error(
    tmp_path: Path, cli: CliInvoke, command: tuple[str, ...]
) -> None:
    """`-C` の指定先が存在しなければ終了コード 2（詳細設計 17.2 の4行目）。"""
    result = cli(*command, project=tmp_path / "does-not-exist")

    assert result.exit_code == EXIT_USAGE, result.output
