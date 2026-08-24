"""S-I: `config.yaml` が壊れている／必須項目が欠けている場合の挙動。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-003 完了条件3 S-I / 要件定義書8.2節・13節 |
| 期待値の正典 | 詳細設計 19章 S-I 行 → 詳細設計 5.4（C-1〜C-7）/ 13.4 / 17.2 / 17.3 |
| 判定の軸 | 終了コードと**キーパス**。日本語の文面は判定対象にしない（5.4 / 申し送り N-4） |
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from tests.acceptance.expectations import (
    CHECK_IDS,
    EXIT_CONFIG_ERROR,
    EXIT_DOCTOR_FAILED,
    EXIT_OK,
    MSG_CONFIG_FILE,
    MSG_CONFIG_SYNTAX,
    CliInvoke,
    base_config,
    config_path,
    parse_doctor_output,
    parse_json,
    write_config,
    write_config_text,
)

pytestmark = pytest.mark.acceptance

Mutation = Callable[[Path], None]


def break_yaml_syntax(project: Path) -> None:
    """YAML として解析できない状態にする（詳細設計 5.4 の C-2）。"""
    write_config_text(project, 'version: 1\nproject:\n  name: "unclosed\n   - [\n')


def remove_required_key(project: Path) -> None:
    """唯一の必須項目 `project.name` を落とす（詳細設計 5.2.1 / 5.4 の C-4）。"""
    write_config_text(project, "version: 1\nproject:\n  description: 説明だけ\n")


def add_unknown_key(project: Path) -> None:
    """未知のキーを足す（`extra=\"forbid\"`。詳細設計 5.1 / 5.4 の C-6）。"""
    config = base_config("sample-project")
    config["projet"] = {"name": "打ち間違い"}
    write_config(project, config)


def set_invalid_enum(project: Path) -> None:
    """列挙外の値を入れる（詳細設計 5.2.5 / 5.4 の C-5）。"""
    config = base_config("sample-project")
    config["actions"] = {"post": {"mode": "autoo"}}
    write_config(project, config)


def set_unsupported_version(project: Path) -> None:
    """サポートされていない config 版数（詳細設計 5.4 の C-7）。"""
    config = base_config("sample-project")
    config["version"] = 2
    write_config(project, config)


def remove_config_file(project: Path) -> None:
    """`config.yaml` を消す（詳細設計 5.4 の C-1）。"""
    config_path(project).unlink()


#: (テストID, 壊し方, stderr に必ず現れる文字列, doctor で `fail` になる check id)
#: ID は ASCII にする（pytest が非 ASCII の ID をエスケープして読めなくなるため）。
BROKEN_CONFIGS: tuple[tuple[str, Mutation, tuple[str, ...], str], ...] = (
    (
        "yaml-syntax",
        break_yaml_syntax,
        (MSG_CONFIG_FILE, MSG_CONFIG_SYNTAX),
        "config.syntax",
    ),
    ("missing-required-key", remove_required_key, ("project.name",), "config.schema"),
    ("unknown-key", add_unknown_key, ("projet",), "config.schema"),
    ("invalid-enum", set_invalid_enum, ("actions.post.mode",), "config.schema"),
    ("unsupported-version", set_unsupported_version, ("version",), "config.version"),
    ("missing-file", remove_config_file, (MSG_CONFIG_FILE,), "structure.files"),
)

_IDS = [case[0] for case in BROKEN_CONFIGS]


@pytest.mark.parametrize(
    ("label", "mutate", "fragments", "check_id"), BROKEN_CONFIGS, ids=_IDS
)
def test_status_fails_with_config_exit_code(
    initialized_project: Path,
    cli: CliInvoke,
    label: str,
    mutate: Mutation,
    fragments: tuple[str, ...],
    check_id: str,
) -> None:
    """設定が読めない状態では `status` は終了コード 4 で終わる（詳細設計 17.2 / 5.4）。"""
    mutate(initialized_project)

    result = cli("status", project=initialized_project)

    assert result.exit_code == EXIT_CONFIG_ERROR, result.output
    for fragment in fragments:
        assert fragment in result.stderr, (
            f"{fragment} が stderr にない: {result.stderr}"
        )


@pytest.mark.parametrize(
    ("label", "mutate", "fragments", "check_id"), BROKEN_CONFIGS, ids=_IDS
)
def test_run_fails_with_config_exit_code(
    initialized_project: Path,
    cli: CliInvoke,
    label: str,
    mutate: Mutation,
    fragments: tuple[str, ...],
    check_id: str,
) -> None:
    """`run` も同じく終了コード 4（詳細設計 17.2）。"""
    mutate(initialized_project)

    result = cli("run", project=initialized_project)

    assert result.exit_code == EXIT_CONFIG_ERROR, result.output


@pytest.mark.parametrize(
    ("label", "mutate", "fragments", "check_id"), BROKEN_CONFIGS, ids=_IDS
)
def test_doctor_reports_config_problems_as_failed_checks(
    initialized_project: Path,
    cli: CliInvoke,
    label: str,
    mutate: Mutation,
    fragments: tuple[str, ...],
    check_id: str,
) -> None:
    """`doctor` は `ConfigError` を送出せず、検査結果 `fail` として終了コード 5 で終わる。

    出所: 詳細設計 13.4（意図した非対称）/ 罠 D-T15。
    """
    mutate(initialized_project)

    result = cli("doctor", project=initialized_project)

    assert result.exit_code == EXIT_DOCTOR_FAILED, result.output
    checks = parse_doctor_output(result.stdout)
    assert set(checks) == set(CHECK_IDS), "設定が壊れていても15項目すべてを出すこと"
    assert checks[check_id] == "fail"


def test_all_violations_are_reported_together(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """複数の違反を1件目で打ち切らない（詳細設計 5.4）。"""
    write_config_text(
        initialized_project,
        "version: 1\nproject:\n  description: ''\nactions:\n  post:\n    mode: autoo\n",
    )

    result = cli("status", project=initialized_project)

    assert result.exit_code == EXIT_CONFIG_ERROR
    assert "project.name" in result.stderr
    assert "actions.post.mode" in result.stderr


@pytest.mark.parametrize(
    ("label", "mutate", "fragments", "check_id"), BROKEN_CONFIGS, ids=_IDS
)
def test_init_does_not_touch_a_broken_config(
    initialized_project: Path,
    cli: CliInvoke,
    label: str,
    mutate: Mutation,
    fragments: tuple[str, ...],
    check_id: str,
) -> None:
    """壊れた設定があっても `init` は終了コード 0 で、既存ファイルを書き換えない。

    出所: 詳細設計 17.2 の3行目 / 12.5（`--force` なしでは触らない）。
    """
    mutate(initialized_project)
    before = (
        config_path(initialized_project).read_text(encoding="utf-8")
        if (config_path(initialized_project).exists())
        else None
    )

    result = cli("init", project=initialized_project)

    assert result.exit_code == EXIT_OK, result.output
    if before is None:
        assert config_path(initialized_project).is_file(), "欠けた生成物は補うこと"
    else:
        assert config_path(initialized_project).read_text(encoding="utf-8") == before


def test_agent_list_works_but_task_list_fails_on_broken_config(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`agent list` は Config を読まない。`task list` は DB を読むため Config が要る。

    出所: 詳細設計 17.2 の3行目とその注記。
    """
    set_invalid_enum(initialized_project)

    agents = cli("agent", "list", "--json", project=initialized_project)
    tasks = cli("task", "list", project=initialized_project)

    assert agents.exit_code == EXIT_OK, agents.output
    assert parse_json(agents.stdout)["agents"]
    assert tasks.exit_code == EXIT_CONFIG_ERROR, tasks.output
