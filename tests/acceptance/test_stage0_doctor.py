"""S-B: `media-agent doctor` の検証。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-003 完了条件2 S-B / 要件定義書18節 Stage 0 の検証条件 |
| 期待値の正典 | 詳細設計 19章 S-B 行 → 詳細設計 13.1 / 13.2 / 13.3 |
| 認証情報の扱い | PO 制約 C-2 / 詳細設計 13.2 の検査12・18.1 |
| 判定の軸 | **check id**（15個）。表示文言では判定しない（申し送り N-3 / 用語集「check id」） |
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tests.acceptance.expectations import (
    CHECK_IDS,
    CHECK_STATUSES,
    EXIT_DOCTOR_FAILED,
    EXIT_OK,
    MSG_DOCTOR,
    CliInvoke,
    base_config,
    base_dir,
    db_path,
    parse_doctor_output,
    parse_doctor_summary,
    parse_json,
    write_config,
)

pytestmark = pytest.mark.acceptance


def test_doctor_passes_on_initialized_project(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`init` 済みのプロジェクトで `doctor` は全項目合格・終了コード 0 で終わる。

    出所: 詳細設計 19章 S-B / 13.2（`fail` が1件でもあれば 5、それ以外は 0）。
    """
    result = cli("doctor", project=initialized_project)

    assert result.exit_code == EXIT_OK, result.output
    checks = parse_doctor_output(result.stdout)
    assert set(checks) == set(CHECK_IDS), f"欠落: {set(CHECK_IDS) - set(checks)}"
    assert [cid for cid, status in checks.items() if status == "fail"] == []

    summary = parse_doctor_summary(result.stdout)
    assert summary["fail"] == 0
    assert sum(summary.values()) == len(CHECK_IDS)


def test_doctor_json_reports_every_check(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`--json` でも15項目すべてが id 付きで出る（詳細設計 13.3）。"""
    result = cli("doctor", "--json", project=initialized_project)

    assert result.exit_code == EXIT_OK, result.output
    payload = parse_json(result.stdout)
    assert payload["overall"] == "ok"
    assert payload["summary"]["fail"] == 0
    assert {check["id"] for check in payload["checks"]} == set(CHECK_IDS)
    assert all(check["status"] in CHECK_STATUSES for check in payload["checks"])
    assert Path(payload["project_root"]).resolve() == initialized_project.resolve()


def test_doctor_does_not_treat_missing_credentials_as_failure(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """認証情報が無いことを異常として報告しない（PO 制約 C-2 / 詳細設計 13.2 の検査12）。

    `.env` が無いのは正常。`fail` になるのは「あって、しかも Git に追跡されている」場合だけ。
    """
    assert not list(base_dir(initialized_project).glob(".env*")), (
        "init が .env を作っている"
    )

    result = cli("doctor", "--json", project=initialized_project)

    checks = {
        check["id"]: check["status"] for check in parse_json(result.stdout)["checks"]
    }
    assert checks["security.env_not_tracked"] in {"ok", "skipped"}
    assert result.exit_code == EXIT_OK


def test_doctor_lists_every_check_even_when_one_fails(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """最初の異常で打ち切らない。不合格があれば終了コード 5（詳細設計 13.1 / 13.2）。"""
    shutil.rmtree(base_dir(initialized_project) / "memory")

    result = cli("doctor", project=initialized_project)

    assert result.exit_code == EXIT_DOCTOR_FAILED
    checks = parse_doctor_output(result.stdout)
    assert set(checks) == set(CHECK_IDS), "fail があっても15項目すべてを出すこと"
    assert checks["structure.dirs"] == "fail"

    summary = parse_doctor_summary(result.stdout)
    assert summary["fail"] >= 1
    assert MSG_DOCTOR in result.stderr
    assert str(summary["fail"]) in result.stderr


def test_doctor_does_not_create_the_database(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`doctor` は副作用を持たない。DB が無くても作らない（詳細設計 13.1 / 13.2 の検査7）。"""
    db_path(initialized_project).unlink(missing_ok=True)

    result = cli("doctor", "--json", project=initialized_project)

    checks = {
        check["id"]: check["status"] for check in parse_json(result.stdout)["checks"]
    }
    assert checks["db.file"] == "fail"
    assert result.exit_code == EXIT_DOCTOR_FAILED
    assert not db_path(initialized_project).exists(), "doctor が DB を作っている"


def test_doctor_detects_broken_gitignore(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`.media-agent/.gitignore` から除外設定が消えていれば `fail`。

    出所: 詳細設計 13.2 の検査11 / 18.2（要件定義書14.2節）。
    """
    (base_dir(initialized_project) / ".gitignore").write_text(
        "# 消した\n", encoding="utf-8"
    )

    result = cli("doctor", "--json", project=initialized_project)

    checks = {
        check["id"]: check["status"] for check in parse_json(result.stdout)["checks"]
    }
    assert checks["security.gitignore"] == "fail"
    assert result.exit_code == EXIT_DOCTOR_FAILED


def test_doctor_warns_but_succeeds_on_inconsistent_limits(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`warn` は終了コードを変えない（詳細設計 13.2 の検査6 / 5.2.3）。"""
    config = base_config(initialized_project.name)
    config["content"] = {"posts_per_day": 5}
    config["actions"] = {"post": {"mode": "auto", "max_per_day": 3}}
    write_config(initialized_project, config)

    result = cli("doctor", "--json", project=initialized_project)

    checks = {
        check["id"]: check["status"] for check in parse_json(result.stdout)["checks"]
    }
    assert checks["config.consistency"] == "warn"
    assert result.exit_code == EXIT_OK
