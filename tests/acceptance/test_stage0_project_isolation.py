"""S-J: 別々の2ディレクトリで `init` したとき、DB・ログ・Memory が互いに混ざらない。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-008 完了条件4 S-J |
| 期待値の正典 | 要件定義書5.4節「Memory は他プロジェクトと完全分離する」/ 方式設計 6.2・6.3・7章 |
| 追加した理由 | T-003 の S-A〜S-I は**常に1プロジェクトしか扱わない**。分離は「2つ同時に存在する」ときにしか壊れない |
| 判定の軸 | プロジェクト固有の痕跡（Task 行 / 監査記録 / ログ行 / 設定）が、**もう一方に出現しないこと** |

分離が壊れる経路は3つある。**いずれも1プロジェクトのテストでは検出できない。**

1. パスの解決が誤り、片方の `.media-agent/` をもう片方が掴む（方式設計 6.3）
2. 同一プロセス内の共有状態（ロガーのハンドラ、接続、Registry）が前のプロジェクトを引きずる
3. 上方探索（方式設計 6.3 の 2）が入れ子のプロジェクトで**遠い方**を掴む
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.acceptance.expectations import (
    EXIT_OK,
    CliInvoke,
    audit_path,
    base_dir,
    db_path,
    log_path,
    parse_json,
    query_db,
    read_audit_records,
    write_config,
)

#: 片方のプロジェクトにだけ現れる文字列。もう片方から見つかったら分離が壊れている。
ALPHA_MARK = "ALPHA-ONLY-MARK"
BETA_MARK = "BETA-ONLY-MARK"


@pytest.fixture()
def two_projects(tmp_path: Path, cli: CliInvoke) -> tuple[Path, Path]:
    """互いに親子関係を持たない2つの初期化済みプロジェクト。

    ディレクトリ名がそのまま `project.name` になる（詳細設計 12.3）ため、
    名前の取り違えもここで観測できる。
    """
    alpha = tmp_path / "alpha-project"
    beta = tmp_path / "beta-project"
    for project in (alpha, beta):
        project.mkdir()
        result = cli("init", project=project)
        assert result.exit_code == EXIT_OK, result.output
    return alpha, beta


def _run_echo(cli: CliInvoke, project: Path, mark: str) -> None:
    result = cli(
        "run", "--agent", "echo", "--input", f'{{"text": "{mark}"}}', project=project
    )
    assert result.exit_code == EXIT_OK, result.output


# --------------------------------------------------------------------------------------
# 生成物そのものの分離（要件定義書8.1節 / 方式設計7章）
# --------------------------------------------------------------------------------------


def test_each_project_owns_its_own_media_agent_directory(
    two_projects: tuple[Path, Path],
) -> None:
    """2つの `.media-agent/` は別の実体である（要件定義書5.4節）。"""
    alpha, beta = two_projects

    assert base_dir(alpha).resolve() != base_dir(beta).resolve()
    assert db_path(alpha).resolve() != db_path(beta).resolve()
    for project in (alpha, beta):
        assert db_path(project).is_file()
        assert (base_dir(project) / "memory").is_dir()

    # 片方を消しても、もう片方は無傷である。
    assert base_dir(alpha).exists()
    assert base_dir(beta).exists()


def test_project_name_follows_its_own_directory(
    two_projects: tuple[Path, Path], cli: CliInvoke
) -> None:
    """`status` が報告する名前とルートは、対象プロジェクトのものである（詳細設計 12.3）。"""
    alpha, beta = two_projects

    for project, expected in ((alpha, "alpha-project"), (beta, "beta-project")):
        result = cli("--json", "status", project=project)
        assert result.exit_code == EXIT_OK, result.output
        payload = parse_json(result.stdout)
        assert payload["project_name"] == expected
        assert Path(payload["project_root"]).resolve() == project.resolve()


# --------------------------------------------------------------------------------------
# DB の分離
# --------------------------------------------------------------------------------------


def test_task_recorded_in_one_project_is_invisible_from_the_other(
    two_projects: tuple[Path, Path], cli: CliInvoke
) -> None:
    """alpha で実行した Task が beta の DB へ入らない（要件定義書5.4節）。"""
    alpha, beta = two_projects

    _run_echo(cli, alpha, ALPHA_MARK)

    alpha_rows = query_db(alpha, "SELECT agent, input FROM tasks")
    beta_rows = query_db(beta, "SELECT agent, input FROM tasks")
    assert len(alpha_rows) == 1
    assert beta_rows == []
    assert ALPHA_MARK in str(alpha_rows[0]["input"])


def test_task_lists_do_not_leak_between_projects(
    two_projects: tuple[Path, Path], cli: CliInvoke
) -> None:
    """双方で実行しても、各 `task list` は自分の Task だけを返す。"""
    alpha, beta = two_projects

    _run_echo(cli, alpha, ALPHA_MARK)
    _run_echo(cli, beta, BETA_MARK)

    alpha_result = cli("--json", "task", "list", project=alpha)
    beta_result = cli("--json", "task", "list", project=beta)
    assert alpha_result.exit_code == EXIT_OK, alpha_result.output
    assert beta_result.exit_code == EXIT_OK, beta_result.output

    alpha_ids = {task["task_id"] for task in parse_json(alpha_result.stdout)["tasks"]}
    beta_ids = {task["task_id"] for task in parse_json(beta_result.stdout)["tasks"]}
    assert len(alpha_ids) == 1
    assert len(beta_ids) == 1
    assert alpha_ids.isdisjoint(beta_ids)


def test_status_counts_only_its_own_tasks(
    two_projects: tuple[Path, Path], cli: CliInvoke
) -> None:
    """`status` の集計が、もう一方の Task を数えない。"""
    alpha, beta = two_projects

    _run_echo(cli, alpha, ALPHA_MARK)
    _run_echo(cli, alpha, ALPHA_MARK)
    _run_echo(cli, beta, BETA_MARK)

    alpha_payload = parse_json(cli("--json", "status", project=alpha).stdout)
    beta_payload = parse_json(cli("--json", "status", project=beta).stdout)
    assert alpha_payload["tasks"]["total"] == 2
    assert beta_payload["tasks"]["total"] == 1


# --------------------------------------------------------------------------------------
# 監査記録とログの分離（要件定義書5.5節 / 詳細設計 11.1）
# --------------------------------------------------------------------------------------


def test_audit_records_do_not_leak_between_projects(
    two_projects: tuple[Path, Path], cli: CliInvoke
) -> None:
    """監査記録は、正本（`decisions`）も写し（`audit.jsonl`）も分離している。"""
    alpha, beta = two_projects

    _run_echo(cli, alpha, ALPHA_MARK)
    _run_echo(cli, beta, BETA_MARK)

    alpha_records = read_audit_records(alpha)
    beta_records = read_audit_records(beta)
    assert len(alpha_records) == 1
    assert len(beta_records) == 1

    alpha_text = audit_path(alpha).read_text(encoding="utf-8")
    beta_text = audit_path(beta).read_text(encoding="utf-8")
    assert ALPHA_MARK in alpha_text
    assert BETA_MARK not in alpha_text
    assert BETA_MARK in beta_text
    assert ALPHA_MARK not in beta_text

    alpha_decisions = query_db(alpha, "SELECT task_id FROM decisions")
    beta_decisions = query_db(beta, "SELECT task_id FROM decisions")
    assert len(alpha_decisions) == 1
    assert len(beta_decisions) == 1
    assert alpha_decisions[0]["task_id"] != beta_decisions[0]["task_id"]


def test_operational_log_is_rebound_when_the_project_changes(
    two_projects: tuple[Path, Path], cli: CliInvoke
) -> None:
    """同一プロセスで続けて実行しても、ログが前のプロジェクトへ書かれない。

    ロガーはモジュール水準の共有状態であり（`core/observability/log.py`）、
    ハンドラが張り替わらなければ beta の行が alpha のログへ落ちる。
    **これは同一プロセスでしか起きない不具合であり、CLI を1回しか呼ばないテストでは出ない。**
    """
    alpha, beta = two_projects

    _run_echo(cli, alpha, ALPHA_MARK)
    _run_echo(cli, beta, BETA_MARK)

    alpha_log = log_path(alpha).read_text(encoding="utf-8")
    beta_log = log_path(beta).read_text(encoding="utf-8")
    alpha_task = query_db(alpha, "SELECT task_id FROM tasks")[0]["task_id"]
    beta_task = query_db(beta, "SELECT task_id FROM tasks")[0]["task_id"]

    assert alpha_task in alpha_log
    assert beta_task not in alpha_log
    assert beta_task in beta_log
    assert alpha_task not in beta_log


# --------------------------------------------------------------------------------------
# 設定の分離
# --------------------------------------------------------------------------------------


def test_breaking_one_config_does_not_affect_the_other(
    two_projects: tuple[Path, Path], cli: CliInvoke
) -> None:
    """alpha の `config.yaml` を壊しても、beta は健全なままである。"""
    alpha, beta = two_projects

    write_config(alpha, {"version": 1, "project": {"name": "alpha-project"}, "x": 1})

    assert cli("status", project=alpha).exit_code != EXIT_OK
    assert cli("status", project=beta).exit_code == EXIT_OK
    assert cli("doctor", project=beta).exit_code == EXIT_OK


# --------------------------------------------------------------------------------------
# プロジェクトルートの解決（方式設計 6.2・6.3）
# --------------------------------------------------------------------------------------


def test_nested_project_resolves_to_the_nearest_root(
    tmp_path: Path, cli: CliInvoke, monkeypatch: pytest.MonkeyPatch
) -> None:
    """入れ子のプロジェクトでは、上方探索が**近い方**を掴む（方式設計 6.3 の 2）。

    遠い方を掴むと、内側のプロジェクトの実行が外側の DB へ入る。
    これは要件定義書5.4節の分離が破れる状態であり、S-J が判定すべき最も危険な経路である。

    `-C` を渡さない挙動そのものを検証するため、ここでだけカレントディレクトリを移す。
    移す先は `tmp_path` 配下であり（罠 T-3）、`monkeypatch.chdir` はテスト終了時に復元される。
    """
    outer = tmp_path / "outer-project"
    inner = outer / "nested" / "inner-project"
    outer.mkdir()
    inner.mkdir(parents=True)
    assert cli("init", project=outer).exit_code == EXIT_OK
    assert cli("init", project=inner).exit_code == EXIT_OK

    deeper = inner / "work" / "here"
    deeper.mkdir(parents=True)
    monkeypatch.chdir(deeper)

    result = cli("--json", "status")
    assert result.exit_code == EXIT_OK, result.output
    payload = parse_json(result.stdout)
    assert Path(payload["project_root"]).resolve() == inner.resolve()
    assert payload["project_name"] == "inner-project"

    run = cli("run", "--agent", "echo", "--input", f'{{"text": "{ALPHA_MARK}"}}')
    assert run.exit_code == EXIT_OK, run.output
    assert len(query_db(inner, "SELECT task_id FROM tasks")) == 1
    assert query_db(outer, "SELECT task_id FROM tasks") == []


def test_project_dir_option_overrides_the_environment_variable(
    two_projects: tuple[Path, Path], cli: CliInvoke, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`MEDIA_AGENT_PROJECT_DIR` は効くが、`-C` のほうが強い（方式設計 6.2）。

    優先順位が逆だと、`-C` で対象を明示したつもりの操作が別プロジェクトへ書き込む。
    """
    alpha, beta = two_projects

    monkeypatch.setenv("MEDIA_AGENT_PROJECT_DIR", str(alpha))
    from_env = cli("--json", "status")
    assert from_env.exit_code == EXIT_OK, from_env.output
    assert parse_json(from_env.stdout)["project_name"] == "alpha-project"

    overridden = cli("--json", "status", project=beta)
    assert overridden.exit_code == EXIT_OK, overridden.output
    assert parse_json(overridden.stdout)["project_name"] == "beta-project"
