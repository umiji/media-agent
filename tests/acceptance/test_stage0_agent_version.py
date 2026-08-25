"""S-K（T-012 / 19.1）: `Agent.version` の永続化（D-2）。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-013 完了条件1 / 詳細設計 19.1 の S-K 行 |
| 期待値の正典 | 詳細設計 6.4（スキーマ版数 2 の差分）/ 7.1（Migration）/ 11.3（Audit の項目） |
| 由来 | T-009 の指摘 RV-3。`Agent.version` が表示にしか使われず、`decisions` にも `AuditRecord` にも受け皿が無かった |
| 要件 | 要件定義書 20.5「同じ Input・設定・Agent Version から実行内容を追跡可能とする」 |

**記号の衝突についての注記**: 詳細設計 19.1 は本シナリオを `S-K` と呼ぶが、T-008 が
`S-K`（連続実行・`test_stage0_lifecycle_sequence.py`）を先に使っている。**別物である。**
本ファイルが指すのは 19.1 の S-K（`agent_version` の永続化）である。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from media_agent.core.policy import PolicyRequest
from tests.acceptance.expectations import (
    EXIT_OK,
    CliInvoke,
    base_config,
    build_policy_engine,
    parse_json,
    query_db,
    read_audit_records,
    write_config,
)

pytestmark = pytest.mark.acceptance


def _echo_version(cli: CliInvoke, project: Path) -> int:
    """`agent list --json` が公開している `echo` の version（詳細設計 16.1）。"""
    result = cli("agent", "list", "--json", project=project)
    assert result.exit_code == EXIT_OK, result.output
    agents = {agent["name"]: agent for agent in parse_json(result.stdout)["agents"]}
    version = agents["echo"]["version"]
    assert isinstance(version, int)
    return version


def test_schema_versions_are_bumped_to_two() -> None:
    """DB と Audit の版数がどちらも 2 である（詳細設計 6.4 / 7.1 / 11.3）。

    **行の形が変わったため据え置かない。** 据え置くと、読み手が「古い行にキーが無い」のか
    「その実行で値が無かった」のかを判別できない（11.3 の却下案）。

    **リテラルの 2 を書いてよいのはここだけである。** 他のテストは定数と比較する
    （19.1 の「版数を上げるたびにテストを直さずに済む形が正しい」）。
    """
    from media_agent.core.db.migrations import SCHEMA_VERSION
    from media_agent.core.observability.audit import AUDIT_SCHEMA_VERSION

    assert SCHEMA_VERSION == 2
    assert AUDIT_SCHEMA_VERSION == 2


def test_initialized_database_reports_the_current_schema_version(
    initialized_project: Path,
) -> None:
    """`init` した DB の `PRAGMA user_version` が `SCHEMA_VERSION` と一致する（7.1）。"""
    from media_agent.core.db.migrations import SCHEMA_VERSION

    rows = query_db(initialized_project, "PRAGMA user_version")

    assert rows[0][0] == SCHEMA_VERSION


def test_decisions_table_has_the_agent_version_column(
    initialized_project: Path,
) -> None:
    """`decisions` に `agent_version` 列がある（詳細設計 6.4 の版数 2 の差分）。"""
    columns = {
        row["name"]
        for row in query_db(initialized_project, "PRAGMA table_info(decisions)")
    }

    assert "agent_version" in columns


def test_agent_run_records_the_agent_version_in_the_audit_log(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`audit.jsonl` の最終行の `agent_version` が `agent list` の version と一致する。

    出所: 詳細設計 11.3。**値の出どころは `AgentRunner` である**（Runner 以外が組み立てない）。
    """
    expected = _echo_version(cli, initialized_project)
    result = cli("run", "--agent", "echo", "--json", project=initialized_project)
    assert result.exit_code == EXIT_OK, result.output

    record = read_audit_records(initialized_project)[-1]

    assert record["kind"] == "agent_run"
    assert record["agent_version"] == expected


def test_agent_run_records_the_agent_version_in_the_decisions_table(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """正本（`decisions`）の同じ行にも同じ値がある（詳細設計 6.4 / 11.3）。

    **JSONL は写しである。** 正本から辿れない項目は、JSONL を消した瞬間に失われる。
    """
    expected = _echo_version(cli, initialized_project)
    result = cli("run", "--agent", "echo", "--json", project=initialized_project)
    assert result.exit_code == EXIT_OK, result.output
    task_id = parse_json(result.stdout)["task_id"]

    rows = query_db(
        initialized_project,
        "SELECT agent_version FROM decisions WHERE task_id = ? AND kind = 'agent_run'",
        (task_id,),
    )

    assert [row["agent_version"] for row in rows] == [expected]


def test_policy_check_records_a_null_agent_version(initialized_project: Path) -> None:
    """`kind='policy_check'` の行の `agent_version` は `NULL`（詳細設計 6.4 / 11.3）。

    Agent が実行していないためである。JSONL 側もキーは省略せず `null` を持つ。
    """
    config = base_config(initialized_project.name)
    config["actions"] = {"post": {"mode": "auto"}}
    write_config(initialized_project, config)
    engine = build_policy_engine(initialized_project)

    engine.check(PolicyRequest(action="post", topic="ai"))

    record = read_audit_records(initialized_project)[-1]
    assert record["kind"] == "policy_check"
    assert "agent_version" in record, "キーを省略しない（詳細設計 11.3）"
    assert record["agent_version"] is None

    rows = query_db(
        initialized_project,
        "SELECT agent_version FROM decisions WHERE kind = 'policy_check'",
    )
    assert [row["agent_version"] for row in rows] == [None]


def test_audit_record_declares_the_audit_schema_version(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """JSONL の `schema_version` が `AUDIT_SCHEMA_VERSION` と一致する（詳細設計 11.3）。"""
    from media_agent.core.observability.audit import AUDIT_SCHEMA_VERSION

    assert (
        cli("run", "--agent", "echo", project=initialized_project).exit_code == EXIT_OK
    )

    record = read_audit_records(initialized_project)[-1]

    assert record["schema_version"] == AUDIT_SCHEMA_VERSION


def test_doctor_accepts_the_new_schema_version(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """版数を上げても `doctor` は 0 で、`db.schema` が `ok`（詳細設計 13.2 の検査8）。

    **`init` が作った DB を `doctor` が不合格にする状態を作らない**（D-2 の却下案
    「版数1の DDL に列を直接足す」が招く失敗の形）。
    """
    result = cli("doctor", "--json", project=initialized_project)

    assert result.exit_code == EXIT_OK, result.output
    checks = {check["id"]: check for check in parse_json(result.stdout)["checks"]}
    assert checks["db.schema"]["status"] == "ok", checks["db.schema"]
