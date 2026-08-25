"""S-K: 同じディレクトリで `init` → `doctor` → `status` → `run` → `status` を続けても壊れない。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-008 完了条件4 S-K |
| 期待値の正典 | 要件定義書18節 Stage 0 の検証条件 / 詳細設計 12.5・13.2・14章・15章 |
| 追加した理由 | S-A〜S-I は**1コマンドずつ独立した状態**で判定する。状態を持ち越したときの破綻は出ない |
| 判定の軸 | 各段の終了コードと、**前段の結果が次段に反映されていること**（状態の持ち越し） |

Stage 0 の検証条件は「一連の流れが正常動作すること」である。個々のコマンドが単独で通っても、
**前のコマンドが残した状態（DB・ログ・接続）が次のコマンドを壊す**なら検証条件を満たさない。
"""

from __future__ import annotations

from pathlib import Path

from tests.acceptance.expectations import (
    BUILTIN_AGENTS,
    EXIT_OK,
    EXIT_RUNTIME_ERROR,
    CliInvoke,
    parse_doctor_summary,
    parse_json,
    parse_labelled_output,
    query_db,
)


def test_init_doctor_status_run_status_sequence(
    project_dir: Path, cli: CliInvoke
) -> None:
    """要件定義書18節の流れをそのまま順に実行し、各段の終了コードを判定する。

    `run` を挟んだ前後で `status` の集計が 0 → 1 に変わることまで見る。
    終了コードだけを見ると、`status` が状態を反映しなくても通ってしまう。
    """
    assert cli("init", project=project_dir).exit_code == EXIT_OK

    doctor_before = cli("doctor", project=project_dir)
    assert doctor_before.exit_code == EXIT_OK, doctor_before.output
    assert parse_doctor_summary(doctor_before.stdout)["fail"] == 0

    status_before = cli("--json", "status", project=project_dir)
    assert status_before.exit_code == EXIT_OK, status_before.output
    assert parse_json(status_before.stdout)["tasks"]["total"] == 0

    run = cli("run", "--agent", "echo", project=project_dir)
    assert run.exit_code == EXIT_OK, run.output

    status_after = cli("--json", "status", project=project_dir)
    assert status_after.exit_code == EXIT_OK, status_after.output
    payload = parse_json(status_after.stdout)
    assert payload["tasks"]["total"] == 1
    assert payload["tasks"]["by_status"]["completed"] == 1
    assert len(payload["recent_tasks"]) == 1


def test_doctor_still_passes_after_the_project_has_been_used(
    project_dir: Path, cli: CliInvoke
) -> None:
    """`run` が作った状態（Task 行・監査記録・ログ）が `doctor` を落とさない。

    実行の副作用で検査が不合格になると、利用者は健全なプロジェクトを異常と判断する。
    """
    assert cli("init", project=project_dir).exit_code == EXIT_OK
    before = parse_doctor_summary(cli("doctor", project=project_dir).stdout)

    assert cli("run", "--agent", "echo", project=project_dir).exit_code == EXIT_OK

    after_result = cli("doctor", project=project_dir)
    assert after_result.exit_code == EXIT_OK, after_result.output
    assert parse_doctor_summary(after_result.stdout) == before


def test_repeating_the_whole_sequence_preserves_recorded_tasks(
    project_dir: Path, cli: CliInvoke
) -> None:
    """2周目の `init` が既存の記録を消さない（詳細設計 12.5 の冪等性）。

    テンプレートの冪等性は S-A が判定している。ここで判定するのは **DB の中身**である。
    再初期化で Task が消えるなら、利用者はうっかり `init` を打つだけで履歴を失う。

    版数は実装の `SCHEMA_VERSION` と比較する（詳細設計 19.1。T-013 が T-012 / D-2 に
    伴って更新した。**版数を上げるたびにテストを直さずに済む形が正しい**）。
    """
    from media_agent.core.db.migrations import SCHEMA_VERSION

    assert cli("init", project=project_dir).exit_code == EXIT_OK
    assert cli("run", "--agent", "echo", project=project_dir).exit_code == EXIT_OK
    first_ids = {
        row["task_id"] for row in query_db(project_dir, "SELECT task_id FROM tasks")
    }
    assert len(first_ids) == 1

    assert cli("init", project=project_dir).exit_code == EXIT_OK
    assert cli("doctor", project=project_dir).exit_code == EXIT_OK
    assert cli("status", project=project_dir).exit_code == EXIT_OK
    assert cli("run", "--agent", "echo", project=project_dir).exit_code == EXIT_OK

    second_ids = {
        row["task_id"] for row in query_db(project_dir, "SELECT task_id FROM tasks")
    }
    assert first_ids < second_ids
    assert len(second_ids) == 2

    payload = parse_json(cli("--json", "status", project=project_dir).stdout)
    assert payload["tasks"]["total"] == 2
    assert payload["database"]["schema_version"] == SCHEMA_VERSION


def test_failed_run_does_not_break_the_following_commands(
    project_dir: Path, cli: CliInvoke
) -> None:
    """`fail` Agent の実行のあとも、後続コマンドが正常に動く。

    失敗した実行が接続を開いたままにしたり Task を `running` のまま残したりすると、
    次のコマンドが壊れる。**S-F は失敗そのものを判定するが、その後を判定しない。**
    """
    assert cli("init", project=project_dir).exit_code == EXIT_OK

    failed = cli("run", "--agent", "fail", project=project_dir)
    assert failed.exit_code == EXIT_RUNTIME_ERROR, failed.output

    assert cli("doctor", project=project_dir).exit_code == EXIT_OK
    assert cli("agent", "list", project=project_dir).exit_code == EXIT_OK
    assert cli("task", "list", project=project_dir).exit_code == EXIT_OK
    assert cli("run", "--agent", "echo", project=project_dir).exit_code == EXIT_OK

    payload = parse_json(cli("--json", "status", project=project_dir).stdout)
    assert payload["tasks"]["total"] == 2
    assert payload["tasks"]["by_status"]["failed"] == 1
    assert payload["tasks"]["by_status"]["completed"] == 1
    assert payload["tasks"]["by_status"]["running"] == 0


def test_long_interleaved_sequence_stays_consistent(
    project_dir: Path, cli: CliInvoke
) -> None:
    """読み取り系を挟みながら実行を繰り返しても、集計が実行回数と一致し続ける。"""
    assert cli("init", project=project_dir).exit_code == EXIT_OK

    for index in range(3):
        assert cli("agent", "list", project=project_dir).exit_code == EXIT_OK
        assert cli("run", "--agent", "echo", project=project_dir).exit_code == EXIT_OK
        assert cli("task", "list", project=project_dir).exit_code == EXIT_OK
        assert cli("doctor", project=project_dir).exit_code == EXIT_OK
        payload = parse_json(cli("--json", "status", project=project_dir).stdout)
        assert payload["tasks"]["total"] == index + 1
        assert payload["tasks"]["by_status"]["completed"] == index + 1

    tasks = parse_json(cli("--json", "task", "list", project=project_dir).stdout)[
        "tasks"
    ]
    assert len({task["task_id"] for task in tasks}) == 3
    assert len(query_db(project_dir, "SELECT decision_id FROM decisions")) == 3


def test_text_status_keeps_reporting_agents_through_the_sequence(
    project_dir: Path, cli: CliInvoke
) -> None:
    """人間向け出力も一連の流れを通して壊れない（詳細設計14章）。"""
    assert cli("init", project=project_dir).exit_code == EXIT_OK
    assert cli("run", "--agent", "echo", project=project_dir).exit_code == EXIT_OK

    result = cli("status", project=project_dir)
    assert result.exit_code == EXIT_OK, result.output
    labelled = parse_labelled_output(result.stdout)
    for agent in BUILTIN_AGENTS:
        assert agent in labelled["agents"]
    assert "total 1" in labelled["tasks"]
