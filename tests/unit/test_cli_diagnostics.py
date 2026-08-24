"""`cli/diagnostics.py` の単体テスト（詳細設計 13.1〜13.4）。

受け入れテスト（S-B / S-I）は `doctor` を CLI 越しに見る。ここでは**検査1件ずつ**を
関数として直接呼び、受け入れテストが踏まない分岐（DB の版数違い・`.env` の追跡・
`logs/` へ書けない・上限が未設定）を対象にする。
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
from pathlib import Path

import pytest

from media_agent.cli import diagnostics
from media_agent.cli.diagnostics import (
    CHECK_ORDER,
    REQUIRED_GITIGNORE_ENTRIES,
    CheckStatus,
    run_diagnostics,
)
from media_agent.core.config.loader import load_config
from media_agent.core.db.migrations import SCHEMA_VERSION
from media_agent.project.layout import ProjectLayout
from media_agent.project.scaffold import init_project


@pytest.fixture()
def layout(tmp_path: Path) -> ProjectLayout:
    """`init` 済みプロジェクトの `ProjectLayout`。"""
    project = tmp_path / "sample-project"
    project.mkdir()
    return init_project(project).layout


def _statuses(layout: ProjectLayout) -> dict[str, CheckStatus]:
    return {check.id: check.status for check in run_diagnostics(layout).checks}


def test_all_fifteen_checks_run_in_the_designed_order(layout: ProjectLayout) -> None:
    """15項目が定義の順で並ぶ（詳細設計 13.2 / 13.3）。"""
    report = run_diagnostics(layout)

    assert tuple(check.id for check in report.checks) == CHECK_ORDER
    assert report.overall == "ok"
    assert sum(report.summary.values()) == len(CHECK_ORDER)


def test_summary_reports_every_status_even_when_zero(layout: ProjectLayout) -> None:
    """集計は4状態すべてのキーを持つ（0 でも省略しない）。"""
    summary = run_diagnostics(layout).summary

    assert set(summary) == {status.value for status in CheckStatus}
    assert summary["fail"] == 0


def test_diagnostics_do_not_touch_the_project(layout: ProjectLayout) -> None:
    """`doctor` は副作用を持たない（詳細設計 13.1）。生成物が1つも増減しない。

    `logs/` の更新時刻だけは変わる。`logs.writable` が一時ファイルを作って消すため
    であり、これは設計が明示している唯一の例外である。
    """
    before = {path.relative_to(layout.base) for path in layout.base.rglob("*")}
    contents = layout.config_path.read_bytes()

    run_diagnostics(layout)

    after = {path.relative_to(layout.base) for path in layout.base.rglob("*")}
    assert after == before
    assert layout.config_path.read_bytes() == contents


def test_missing_database_skips_the_dependent_checks(layout: ProjectLayout) -> None:
    """DB が無ければ `db.file` は `fail`、版数と外部キーは `skipped`（DB を作らない）。"""
    layout.db_path.unlink()

    statuses = _statuses(layout)

    assert statuses["db.file"] is CheckStatus.fail
    assert statuses["db.schema"] is CheckStatus.skipped
    assert statuses["db.foreign_keys"] is CheckStatus.skipped
    assert not layout.db_path.exists()


def test_outdated_schema_version_is_reported_with_a_migration_hint(
    layout: ProjectLayout,
) -> None:
    """版数が古ければ `db.schema` は `fail` で、`init` で移行できると伝える。"""
    conn = sqlite3.connect(str(layout.db_path))
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION - 1}")
    conn.commit()
    conn.close()

    check = next(c for c in run_diagnostics(layout).checks if c.id == "db.schema")

    assert check.status is CheckStatus.fail
    assert check.hint is not None and "media-agent init" in check.hint


def test_newer_schema_version_asks_to_update_media_agent(layout: ProjectLayout) -> None:
    """版数が新しければ、移行ではなく更新を促す（詳細設計 13.2 の検査8）。"""
    conn = sqlite3.connect(str(layout.db_path))
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION + 1}")
    conn.commit()
    conn.close()

    check = next(c for c in run_diagnostics(layout).checks if c.id == "db.schema")

    assert check.status is CheckStatus.fail
    assert check.hint is not None and "更新" in check.hint


def test_foreign_keys_check_detects_a_pragma_regression(
    monkeypatch: pytest.MonkeyPatch, layout: ProjectLayout
) -> None:
    """接続時の `PRAGMAS` から `foreign_keys` が落ちたら `fail`（罠 T-2 の再発検出）。"""
    monkeypatch.setattr(diagnostics, "PRAGMAS", (("journal_mode", "WAL"),))

    assert _statuses(layout)["db.foreign_keys"] is CheckStatus.fail


@pytest.mark.parametrize("entry", REQUIRED_GITIGNORE_ENTRIES)
def test_each_required_gitignore_entry_is_checked(
    layout: ProjectLayout, entry: str
) -> None:
    """`data/` `logs/` `.env` は**それぞれ**必要（詳細設計 13.2 の検査11）。"""
    kept = [item for item in REQUIRED_GITIGNORE_ENTRIES if item != entry]
    layout.gitignore_path.write_text("\n".join(kept) + "\n", encoding="utf-8")

    check = next(
        c for c in run_diagnostics(layout).checks if c.id == "security.gitignore"
    )

    assert check.status is CheckStatus.fail
    assert entry in check.message


def test_env_file_outside_a_git_repository_is_not_a_failure(
    layout: ProjectLayout,
) -> None:
    """Git リポジトリでなければ追跡の有無を確認できない → `skipped`。

    **`.env` があること自体は異常ではない**（PO 制約 C-2 / 詳細設計 13.2 の検査12）。
    """
    (layout.base / ".env").write_text("TOKEN=dummy\n", encoding="utf-8")

    assert _statuses(layout)["security.env_not_tracked"] is CheckStatus.skipped


def test_tracked_env_file_is_a_failure(
    monkeypatch: pytest.MonkeyPatch, layout: ProjectLayout
) -> None:
    """`.env` があり、しかも Git の追跡対象なら `fail`（唯一の `fail` 条件）。"""
    (layout.base / ".env").write_text("TOKEN=dummy\n", encoding="utf-8")
    monkeypatch.setattr(diagnostics, "_inside_work_tree", lambda *_: True)
    monkeypatch.setattr(diagnostics, "_git_tracked", lambda *_: True)
    monkeypatch.setattr(diagnostics.shutil, "which", lambda _: "/usr/bin/git")

    check = next(
        c for c in run_diagnostics(layout).checks if c.id == "security.env_not_tracked"
    )

    assert check.status is CheckStatus.fail
    assert check.hint is not None and "git rm --cached" in check.hint


def test_unwritable_logs_directory_is_a_failure(layout: ProjectLayout) -> None:
    """`logs/` が無ければ `logs.writable` は `fail`。"""
    for child in layout.logs_dir.iterdir():  # pragma: no cover - 通常は空
        child.unlink()
    layout.logs_dir.rmdir()

    assert _statuses(layout)["logs.writable"] is CheckStatus.fail


def test_writability_check_leaves_no_file_behind(layout: ProjectLayout) -> None:
    """書き込み検査の一時ファイルは必ず削除する（詳細設計 13.1）。"""
    run_diagnostics(layout)

    assert list(layout.logs_dir.iterdir()) == []


def test_missing_version_key_is_a_warning_not_a_failure(layout: ProjectLayout) -> None:
    """`version` が無い場合は `warn`（`1` とみなす。詳細設計 13.2 の検査5）。"""
    layout.config_path.write_text("project:\n  name: sample\n", encoding="utf-8")

    statuses = _statuses(layout)

    assert statuses["config.version"] is CheckStatus.warn
    assert statuses["config.schema"] is CheckStatus.ok
    assert run_diagnostics(layout).overall == "ok"


def test_unsupported_version_skips_the_schema_check(layout: ProjectLayout) -> None:
    """版数が未対応なら、スキーマ検査は評価できないので `skipped`（詳細設計 13.4）。"""
    layout.config_path.write_text(
        "version: 99\nproject:\n  name: sample\n", encoding="utf-8"
    )

    statuses = _statuses(layout)

    assert statuses["config.version"] is CheckStatus.fail
    assert statuses["config.schema"] is CheckStatus.skipped
    assert statuses["config.consistency"] is CheckStatus.skipped
    assert statuses["policy.config"] is CheckStatus.skipped


def test_non_mapping_config_is_a_syntax_failure(layout: ProjectLayout) -> None:
    """トップレベルが mapping でなければ `config.syntax` が `fail`（詳細設計 5.4 の C-3）。"""
    layout.config_path.write_text("- 1\n- 2\n", encoding="utf-8")

    statuses = _statuses(layout)

    assert statuses["config.syntax"] is CheckStatus.fail
    assert statuses["config.schema"] is CheckStatus.skipped


def test_schema_failure_lists_the_violated_key_paths(layout: ProjectLayout) -> None:
    """`config.schema` の `message` に違反したキーパスを列挙する（詳細設計 13.2 の検査4）。"""
    layout.config_path.write_text(
        "version: 1\nproject:\n  description: 説明だけ\n", encoding="utf-8"
    )

    check = next(c for c in run_diagnostics(layout).checks if c.id == "config.schema")

    assert check.status is CheckStatus.fail
    assert "project.name" in check.message


def test_consistency_is_ok_when_no_daily_limit_is_configured(
    layout: ProjectLayout,
) -> None:
    """`actions.post.max_per_day` が `null` なら常に `ok`（詳細設計 13.2 の検査6）。"""
    layout.config_path.write_text(
        "version: 1\nproject:\n  name: sample\n"
        "content:\n  posts_per_day: 50\nactions:\n  post:\n    mode: auto\n",
        encoding="utf-8",
    )
    assert load_config(layout.config_path).content.posts_per_day == 50

    assert _statuses(layout)["config.consistency"] is CheckStatus.ok


def test_policy_check_does_not_consume_the_limit(layout: ProjectLayout) -> None:
    """検査14 は `record=False` で判定する（罠 D-T14）。監査記録が増えない。"""
    run_diagnostics(layout)
    run_diagnostics(layout)

    conn = sqlite3.connect(str(layout.db_path))
    try:
        assert conn.execute("SELECT COUNT(*) FROM decisions").fetchone()[0] == 0
    finally:
        conn.close()
    assert not layout.audit_path.exists()


def test_non_integer_version_is_a_failure(layout: ProjectLayout) -> None:
    """`version` が整数でなければ `fail`（`1` とみなさない）。"""
    layout.config_path.write_text(
        'version: "いち"\nproject:\n  name: sample\n', encoding="utf-8"
    )

    assert _statuses(layout)["config.version"] is CheckStatus.fail


def test_registry_failure_is_reported_as_a_bug(
    monkeypatch: pytest.MonkeyPatch, layout: ProjectLayout
) -> None:
    """Registry を組み立てられなければ `fail`。**例外を外へ出さない**（詳細設計 13.1）。"""

    def _broken() -> object:
        raise RuntimeError("registry is broken")

    monkeypatch.setattr(
        "media_agent.agents.builtin.build_default_registry", _broken, raising=True
    )

    check = next(c for c in run_diagnostics(layout).checks if c.id == "agents.registry")

    assert check.status is CheckStatus.fail
    assert "registry is broken" in check.message


def test_policy_failure_is_reported_without_raising(
    monkeypatch: pytest.MonkeyPatch, layout: ProjectLayout
) -> None:
    """Policy の判定が失敗しても `fail` として報告し、例外にしない（詳細設計 13.1）。"""

    def _broken(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("policy is broken")

    monkeypatch.setattr(diagnostics, "PolicyEngine", _broken)

    check = next(c for c in run_diagnostics(layout).checks if c.id == "policy.config")

    assert check.status is CheckStatus.fail
    assert "policy is broken" in check.message


@pytest.mark.skipif(shutil.which("git") is None, reason="git が無い環境")
class TestEnvNotTrackedInsideGit:
    """検査12 を**実物の Git リポジトリ**で確認する（詳細設計 13.2 の検査12）。"""

    @staticmethod
    def _git_project(tmp_path: Path) -> ProjectLayout:
        project = tmp_path / "tracked-project"
        project.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        return init_project(project).layout

    def test_untracked_env_is_ok(self, tmp_path: Path) -> None:
        """`.env` があっても追跡されていなければ `ok`（PO 制約 C-2）。"""
        layout = self._git_project(tmp_path)
        (layout.base / ".env").write_text("TOKEN=dummy\n", encoding="utf-8")

        assert _statuses(layout)["security.env_not_tracked"] is CheckStatus.ok

    def test_tracked_env_is_a_failure(self, tmp_path: Path) -> None:
        """追跡対象になっていれば `fail`。**これが唯一の `fail` 条件である。**"""
        layout = self._git_project(tmp_path)
        env = layout.base / ".env"
        env.write_text("TOKEN=dummy\n", encoding="utf-8")
        subprocess.run(["git", "add", "-f", str(env)], cwd=layout.root, check=True)

        assert _statuses(layout)["security.env_not_tracked"] is CheckStatus.fail

    def test_no_env_file_is_skipped_even_inside_git(self, tmp_path: Path) -> None:
        """`.env` が無ければ Git の中でも `skipped`（不在は異常ではない）。"""
        layout = self._git_project(tmp_path)

        assert _statuses(layout)["security.env_not_tracked"] is CheckStatus.skipped
