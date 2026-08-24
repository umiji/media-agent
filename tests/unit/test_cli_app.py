"""CLI の枠の単体テスト（方式設計 6.1〜6.5 / 詳細設計 17章）。

受け入れテストと重ならない範囲、すなわち **CLI 層固有の責務**（例外 → 終了コード変換、
コマンドの登録、グローバルオプションの解釈）を対象にする。
"""

from __future__ import annotations

from pathlib import Path

import click
import pytest
from click.testing import CliRunner

from media_agent import __version__
from media_agent.cli.app import EXIT_INTERNAL_ERROR, main, render_error
from media_agent.cli.commands.stubs import STUB_COMMANDS
from media_agent.cli.context import CliContext
from media_agent.errors import MediaAgentError, NotImplementedInStageError

#: 要件定義書10節の10コマンド（方式設計 6.4）。
EXPECTED_COMMANDS: frozenset[str] = frozenset(
    {
        "init",
        "setup",
        "doctor",
        "run",
        "status",
        "research",
        "post",
        "analyze",
        "task",
        "agent",
    }
)


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_all_ten_commands_are_registered() -> None:
    """10コマンドが登録されている（完了条件2）。"""
    assert set(main.commands) == set(EXPECTED_COMMANDS)


def test_read_only_subcommands_exist() -> None:
    """`agent list` / `task list` の枠がある（方式設計 6.4）。書き込み系は作らない。"""
    agent_group = main.commands["agent"]
    task_group = main.commands["task"]
    assert isinstance(agent_group, click.Group)
    assert isinstance(task_group, click.Group)
    assert set(agent_group.commands) == {"list"}
    assert set(task_group.commands) == {"list"}


def test_version_option_reports_the_package_version(runner: CliRunner) -> None:
    """`--version` は `media_agent.__version__` を表示する（方式設計12章）。"""
    result = runner.invoke(main, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_help_lists_the_commands(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--help"])

    assert result.exit_code == 0
    for name in EXPECTED_COMMANDS:
        assert name in result.stdout


@pytest.mark.parametrize("name", sorted(STUB_COMMANDS))
def test_stub_commands_exit_with_ten(runner: CliRunner, name: str) -> None:
    """スタブは終了コード 10。**沈黙して成功しない**（罠 T-8）。"""
    result = runner.invoke(main, [name], catch_exceptions=False)

    assert result.exit_code == NotImplementedInStageError.exit_code
    assert result.stdout == ""
    assert "Stage" in result.stderr
    assert "未実装" in result.stderr


def test_unknown_command_is_a_usage_error(runner: CliRunner) -> None:
    """使い方の誤りは終了コード 2（Click 既定。方式設計 6.5）。"""
    assert runner.invoke(main, ["nope"]).exit_code == 2


def test_missing_project_dir_is_a_usage_error(
    runner: CliRunner, tmp_path: Path
) -> None:
    """`-C` の指定先が無ければ終了コード 2（詳細設計 17.2）。"""
    result = runner.invoke(main, ["-C", str(tmp_path / "absent"), "init"])

    assert result.exit_code == 2


def test_project_dir_can_come_from_the_environment(
    runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`MEDIA_AGENT_PROJECT_DIR` でも指定できる（方式設計 6.2）。"""
    monkeypatch.setenv("MEDIA_AGENT_PROJECT_DIR", str(tmp_path))

    result = runner.invoke(main, ["init"], catch_exceptions=False)

    assert result.exit_code == 0
    assert (tmp_path / ".media-agent" / "config.yaml").is_file()


def test_quiet_suppresses_stdout(runner: CliRunner, tmp_path: Path) -> None:
    """`-q` はエラー以外を抑制する（方式設計 6.2）。"""
    result = runner.invoke(
        main, ["-q", "-C", str(tmp_path), "init"], catch_exceptions=False
    )

    assert result.exit_code == 0
    assert result.stdout == ""


def test_media_agent_errors_are_converted_to_their_exit_code(runner: CliRunner) -> None:
    """例外 → 終了コードの変換は CLI 層だけが行う（品質基準 Q8）。"""

    class Boom(MediaAgentError):
        exit_code = 6

    @click.command("boom")
    def boom() -> None:
        raise Boom("失敗しました", details=["詳細"], hint="対処")

    main.add_command(boom)
    try:
        result = runner.invoke(main, ["boom"], catch_exceptions=False)
    finally:
        del main.commands["boom"]

    assert result.exit_code == 6
    assert result.stdout == ""
    assert result.stderr.splitlines() == [
        "Error: 失敗しました",
        "  - 詳細",
        "Hint: 対処",
    ]


def test_unexpected_errors_become_exit_code_70(runner: CliRunner) -> None:
    """想定外の内部エラーは 70。トレースは `--verbose` のときだけ（方式設計 6.5）。"""

    @click.command("kaboom")
    def kaboom() -> None:
        raise RuntimeError("想定外")

    main.add_command(kaboom)
    try:
        quiet = runner.invoke(main, ["kaboom"], catch_exceptions=False)
        verbose = runner.invoke(main, ["--verbose", "kaboom"], catch_exceptions=False)
    finally:
        del main.commands["kaboom"]

    assert quiet.exit_code == EXIT_INTERNAL_ERROR
    assert "Traceback" not in quiet.stderr
    assert verbose.exit_code == EXIT_INTERNAL_ERROR
    assert "Traceback" in verbose.stderr


def test_render_error_omits_optional_parts(capsys: pytest.CaptureFixture[str]) -> None:
    """詳細と Hint が無ければ1行だけ出す（詳細設計 17.3）。"""
    render_error(MediaAgentError("要約だけ"))

    captured = capsys.readouterr()
    assert captured.err == "Error: 要約だけ\n"
    assert captured.out == ""


def test_wants_json_merges_global_and_local_flags() -> None:
    """`--json` はグローバルにもコマンドにも置ける（詳細設計 15.3）。"""
    context = CliContext(project_dir=None)

    assert context.wants_json() is False
    assert context.wants_json(local=True) is True
    assert CliContext(project_dir=None, json_output=True).wants_json() is True


def test_target_dir_does_not_search_upward(tmp_path: Path) -> None:
    """`init` の対象は指定ディレクトリそのもの（方式設計 6.3 の3番）。"""
    assert CliContext(project_dir=tmp_path).target_dir() == tmp_path
    assert CliContext(project_dir=None, cwd=tmp_path).target_dir() == tmp_path
