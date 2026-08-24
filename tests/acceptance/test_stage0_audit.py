"""S-H: Agent の実行が Audit へ記録され、要件定義書5.5節の9項目が追跡できる。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-003 完了条件3 S-H / 要件定義書5.5節・20.3節・20.5節 |
| 期待値の正典 | 詳細設計 19章 S-H 行 → 詳細設計 11.1（運用ログとの別物性）/ 11.3（9項目の対応表）/ 11.4 |
| 正本 | `decisions` テーブル。`audit.jsonl` はその写し（詳細設計 11.1） |
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from media_agent.core.policy import PolicyRequest
from tests.acceptance.expectations import (
    AUDIT_KEYS,
    EXIT_OK,
    EXIT_RUNTIME_ERROR,
    CliInvoke,
    audit_path,
    base_config,
    build_policy_engine,
    log_path,
    parse_json,
    query_db,
    read_audit_records,
    write_config,
)

pytestmark = pytest.mark.acceptance


def test_agent_run_is_recorded_with_all_nine_items(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`run` の後、`audit.jsonl` の最終行が9キーをすべて持つ（詳細設計 11.3）。"""
    result = cli(
        "run",
        "--agent",
        "echo",
        "--input",
        '{"message":"hi"}',
        "--json",
        project=initialized_project,
    )
    assert result.exit_code == EXIT_OK, result.output
    task_id = parse_json(result.stdout)["task_id"]

    record = read_audit_records(initialized_project)[-1]

    assert set(AUDIT_KEYS) <= set(record), f"欠落: {set(AUDIT_KEYS) - set(record)}"
    assert record["agent"] == "echo"
    assert record["task"] == task_id
    assert record["input"] == {"message": "hi"}
    assert record["decision"]
    assert record["reason"]
    assert record["result"] == {"message": "hi"}
    assert record["error"] is None
    assert record["kind"] == "agent_run"
    assert record["decision_id"]
    assert record["schema_version"] == 1


def test_audit_record_is_persisted_in_the_decisions_table(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """同じ内容が `decisions` テーブルに1行ある（詳細設計 11.3 / 6.4。正本は DB）。"""
    result = cli("run", "--agent", "echo", "--json", project=initialized_project)
    task_id = parse_json(result.stdout)["task_id"]
    record = read_audit_records(initialized_project)[-1]

    rows = query_db(
        initialized_project,
        "SELECT * FROM decisions WHERE task_id = ? AND kind = 'agent_run'",
        (task_id,),
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["decision_id"] == record["decision_id"]
    assert row["agent"] == record["agent"]
    assert row["decision"] == record["decision"]
    assert row["reason"] == record["reason"]
    assert row["timestamp"] == record["timestamp"]
    assert json.loads(row["input"]) == record["input"]
    assert json.loads(row["result"]) == record["result"]


def test_audit_is_a_separate_file_from_the_operational_log(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """監査記録と運用ログは別物である（詳細設計 11.1 / 用語集「運用ログ / 監査記録」）。"""
    assert (
        cli("run", "--agent", "echo", project=initialized_project).exit_code == EXIT_OK
    )

    assert audit_path(initialized_project).is_file()
    assert log_path(initialized_project).is_file()
    assert audit_path(initialized_project) != log_path(initialized_project)

    for line in log_path(initialized_project).read_text(encoding="utf-8").splitlines():
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        assert not (isinstance(parsed, dict) and set(AUDIT_KEYS) <= set(parsed)), (
            "監査記録が運用ログへ流れている"
        )


def test_failed_run_is_recorded_as_an_error(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`fail` 実行時は `decision == "error"` かつ `error` が非 null（詳細設計 8.3 の手順7 / 11.3）。"""
    result = cli("run", "--agent", "fail", project=initialized_project)
    assert result.exit_code == EXIT_RUNTIME_ERROR

    record = read_audit_records(initialized_project)[-1]

    assert record["agent"] == "fail"
    assert record["decision"] == "error"
    assert record["error"] is not None and record["error"] != ""
    assert record["error"].count("\n") == 0, "監査記録にトレースバックを出さない"
    assert record["result"] is None


def test_audit_is_not_suppressed_by_log_level(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """監査記録は `logging.level` で抑制されない。常に全件記録する（詳細設計 11.1 / 11.2）。"""
    config = base_config(initialized_project.name)
    config["logging"] = {"level": "error"}
    write_config(initialized_project, config)

    assert (
        cli("run", "--agent", "echo", project=initialized_project).exit_code == EXIT_OK
    )

    records = read_audit_records(initialized_project)
    assert len(records) == 1
    assert records[-1]["agent"] == "echo"


def test_secret_looking_keys_are_masked(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """秘密値らしいキーの値はマスクしてから記録する（詳細設計 11.4 / 品質基準 Q10）。"""
    result = cli(
        "run",
        "--agent",
        "echo",
        "--input",
        '{"api_key":"s3cret-value"}',
        project=initialized_project,
    )
    assert result.exit_code == EXIT_OK, result.output

    record = read_audit_records(initialized_project)[-1]

    assert record["input"]["api_key"] == "***"
    assert "s3cret-value" not in audit_path(initialized_project).read_text(
        encoding="utf-8"
    )
    assert "s3cret-value" not in log_path(initialized_project).read_text(
        encoding="utf-8"
    )


def test_policy_check_is_recorded_with_its_reason_code(
    initialized_project: Path,
) -> None:
    """Policy の判定も同じ書き込み口へ記録される（詳細設計 11.3 の種別ごとの値の入れ方）。"""
    config = base_config(initialized_project.name)
    config["actions"] = {"post": {"mode": "auto"}}
    write_config(initialized_project, config)
    engine = build_policy_engine(initialized_project)

    decision = engine.check(PolicyRequest(action="post", topic="ai"))

    record = read_audit_records(initialized_project)[-1]
    assert set(AUDIT_KEYS) <= set(record)
    assert record["kind"] == "policy_check"
    assert record["agent"] == "policy-engine"
    assert record["action"] == "post"
    assert record["decision"] == decision.outcome.value
    assert record["reason"].startswith(decision.reason_code.value)
    assert record["error"] is None
