"""S-D2〜S-D7: `.media-agent/` の構造が壊れているときの挙動（T-012 / D-1）。

| 項目 | 出所 |
| --- | --- |
| シナリオ | T-013 完了条件1 / 詳細設計 19.1 の S-D2〜S-D7 |
| 期待値の正典 | 詳細設計 17.2（下5行）/ 17.3 / 17.4（定義・R-1〜R-7・メッセージ・復旧経路）/ 13.2 の検査2・7・10 |
| 由来 | T-009 の Major 指摘 RV-1。`doctor` が 5 で診断した状況で、その助言に従うと 70 で終わっていた |
| 判定の軸 | 終了コードと 17.3 の安定文字列だけ（申し送り N-4）。文面全体は判定しない |

**判定の要点は「1 であって 70 でないこと」である**（詳細設計 17.4 の R-1）。
70（内部エラー）が返る限り RV-1 は解消していない。

**壊し方は「ファイルの置き換え」で作る。** 権限を落とす方法（`chmod 000`）は取らない。
root で実行すると権限が効かず、環境によって結果が変わるため（詳細設計 19.1 の注記）。
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.acceptance.expectations import (
    EXIT_DOCTOR_FAILED,
    EXIT_NOT_INITIALIZED,
    EXIT_OK,
    EXIT_RUNTIME_ERROR,
    MSG_INIT_HINT,
    MSG_NOT_A_DIRECTORY,
    MSG_NOT_INITIALIZED,
    MSG_QUARANTINE,
    MSG_SQLITE,
    CliInvoke,
    base_dir,
    config_path,
    db_path,
    parse_json,
)

pytestmark = pytest.mark.acceptance


# --------------------------------------------------------------------------------------
# 壊し方（詳細設計 17.4.1 の種別1 / 種別2）
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Breakage:
    """1つの壊し方。`apply` は壊した対象の絶対パスを返す。"""

    id: str
    apply: Callable[[Path], Path]
    #: 17.3 の安定文字列（種別1 は `ディレクトリではありません`、種別2 は `SQLite`）。
    marker: str
    #: この壊し方で `fail` になるべき `doctor` の check id（詳細設計 13.2 の検査2・7・10）。
    failing_checks: tuple[str, ...]


def _replace_dir_with_file(project: Path, name: str) -> Path:
    """`.media-agent/<name>/` を同名の通常ファイルへ置き換える（種別1）。"""
    target = base_dir(project) / name
    shutil.rmtree(target)
    target.write_text("これはディレクトリではありません\n", encoding="utf-8")
    return target


def _write_garbage_over_the_db(project: Path) -> Path:
    """`data/media-agent.db` を SQLite ではないテキストで上書きする（種別2）。"""
    target = db_path(project)
    target.write_text("これは SQLite データベースではありません\n", encoding="utf-8")
    return target


BREAKAGES: tuple[Breakage, ...] = (
    Breakage(
        id="db-not-sqlite",
        apply=_write_garbage_over_the_db,
        marker=MSG_SQLITE,
        failing_checks=("db.file",),
    ),
    Breakage(
        id="logs-is-file",
        apply=lambda project: _replace_dir_with_file(project, "logs"),
        marker=MSG_NOT_A_DIRECTORY,
        failing_checks=("structure.dirs", "logs.writable"),
    ),
    Breakage(
        id="data-is-file",
        apply=lambda project: _replace_dir_with_file(project, "data"),
        marker=MSG_NOT_A_DIRECTORY,
        failing_checks=("structure.dirs", "db.file"),
    ),
)

#: 構造破損（17.2 の下から2〜4行目）での終了コード。3種の壊し方で同じ行になる。
BROKEN_EXIT_CODES: tuple[tuple[tuple[str, ...], int], ...] = (
    (("init",), EXIT_RUNTIME_ERROR),
    (("doctor",), EXIT_DOCTOR_FAILED),
    (("status",), EXIT_RUNTIME_ERROR),
    (("run", "--agent", "echo"), EXIT_RUNTIME_ERROR),
    (("agent", "list"), EXIT_OK),
    (("task", "list"), EXIT_RUNTIME_ERROR),
)

#: `agents/` `memory/` の破損（17.2 の最終行）。**実行系は 0 で成功する**（17.4 の R-4）。
UNUSED_DIR_EXIT_CODES: tuple[tuple[tuple[str, ...], int], ...] = (
    (("init",), EXIT_RUNTIME_ERROR),
    (("doctor",), EXIT_DOCTOR_FAILED),
    (("status",), EXIT_OK),
    (("run", "--agent", "echo"), EXIT_OK),
    (("agent", "list"), EXIT_OK),
    (("task", "list"), EXIT_OK),
)

#: 終了コード 1 で終わり、利用者へメッセージを出すコマンド（S-D3 の対象）。
FAILING_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("init",),
    ("status",),
    ("run", "--agent", "echo"),
    ("task", "list"),
)


def _ids(value: object) -> str:
    """パラメータの表示名。コマンドはそのまま読める形にする。"""
    if isinstance(value, tuple):
        return " ".join(str(item) for item in value)
    return str(value)


def _quarantine(project: Path, target: Path) -> Path:
    """利用者が行う「退避」を再現する（詳細設計 17.4.4 の手順2）。

    **製品側が退避することは無い**（17.4 の R-2）。退避の主語は利用者であり、
    テストの中では `Path.rename` でよい（19.1 の注記）。
    """
    moved = project.parent / f"quarantined-{target.name}"
    target.rename(moved)
    return moved


# --------------------------------------------------------------------------------------
# S-D2: 構造破損 × コマンド（詳細設計 17.2 の下5行）
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("breakage", BREAKAGES, ids=lambda b: b.id)
@pytest.mark.parametrize("command,expected", BROKEN_EXIT_CODES, ids=lambda c: _ids(c))
def test_broken_structure_returns_the_documented_exit_code(
    initialized_project: Path,
    cli: CliInvoke,
    breakage: Breakage,
    command: tuple[str, ...],
    expected: int,
) -> None:
    """構造が壊れていても 17.2 の行のとおりの終了コードで終わる（S-D2）。

    **70（内部エラー）で終わってはならない**（詳細設計 17.4 の R-1）。
    `sqlite3.Error` / `OSError` を CLI 層へ通さないことの判定である（品質基準 Q8）。
    """
    breakage.apply(initialized_project)

    result = cli(*command, project=initialized_project)

    assert result.exit_code == expected, result.output


@pytest.mark.parametrize("name", ("agents", "memory"))
@pytest.mark.parametrize(
    "command,expected", UNUSED_DIR_EXIT_CODES, ids=lambda c: _ids(c)
)
def test_unused_directories_do_not_stop_the_runtime_commands(
    initialized_project: Path,
    cli: CliInvoke,
    name: str,
    command: tuple[str, ...],
    expected: int,
) -> None:
    """`agents/` `memory/` が壊れても `status` / `run` / `task list` は 0（S-D2）。

    **各コマンドは自分が必要とする構造だけを検査する**（詳細設計 17.4 の R-4 / 17.2 の最終行）。
    Stage 0 の実行経路はこの2つを読まない（8.2）。**「検査していないから通った」ではなく、
    これが期待値である。**
    """
    _replace_dir_with_file(initialized_project, name)

    result = cli(*command, project=initialized_project)

    assert result.exit_code == expected, result.output


@pytest.mark.parametrize(
    "command",
    (
        ("doctor",),
        ("status",),
        ("run", "--agent", "echo"),
        ("agent", "list"),
        ("task", "list"),
    ),
    ids=lambda c: _ids(c),
)
def test_media_agent_itself_being_a_file_is_treated_as_uninitialized(
    initialized_project: Path, cli: CliInvoke, command: tuple[str, ...]
) -> None:
    """`.media-agent/` 自体が通常ファイルなら構造破損ではなく未初期化（3）。

    出所: 詳細設計 17.2 の5行目 / 17.4.1。`is_initialized()` が `.media-agent/` を
    **ディレクトリとして**探すためであり、これは意図した挙動である（4.1）。
    """
    shutil.rmtree(base_dir(initialized_project))
    base_dir(initialized_project).write_text("これはファイル\n", encoding="utf-8")

    result = cli(*command, project=initialized_project)

    assert result.exit_code == EXIT_NOT_INITIALIZED, result.output
    assert MSG_NOT_INITIALIZED in result.stderr


# --------------------------------------------------------------------------------------
# S-D3: 構造破損のメッセージ（詳細設計 17.3 / 17.4.3）
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("breakage", BREAKAGES, ids=lambda b: b.id)
@pytest.mark.parametrize("command", FAILING_COMMANDS, ids=lambda c: _ids(c))
def test_broken_structure_names_the_path_and_shows_the_recovery_hint(
    initialized_project: Path,
    cli: CliInvoke,
    breakage: Breakage,
    command: tuple[str, ...],
) -> None:
    """stderr に対象の絶対パス・種別の安定文字列・復旧手順が出る（S-D3）。

    出所: 詳細設計 17.3 の追加3行 / 17.4 の R-3。**Hint は行き止まりにしない。**
    """
    broken = breakage.apply(initialized_project)

    result = cli(*command, project=initialized_project)

    assert result.exit_code == EXIT_RUNTIME_ERROR, result.output
    assert str(broken) in result.stderr or str(broken.resolve()) in result.stderr
    assert breakage.marker in result.stderr
    assert MSG_QUARANTINE in result.stderr
    assert MSG_INIT_HINT in result.stderr


# --------------------------------------------------------------------------------------
# S-D4: `doctor` の助言（詳細設計 13.2 の検査2・7・10 / 17.4 の R-6）
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("breakage", BREAKAGES, ids=lambda b: b.id)
def test_doctor_hint_points_at_the_recovery_procedure(
    initialized_project: Path, cli: CliInvoke, breakage: Breakage
) -> None:
    """該当の check が `fail` で、その `hint` が復旧手順を示す（S-D4）。

    **message ではなく `hint` を判定する**（詳細設計 13.2 の注記）。
    `doctor` は構造破損でも例外を送出せず、15項目すべてを評価して 5 で終わる（13.1）。
    """
    breakage.apply(initialized_project)

    result = cli("doctor", "--json", project=initialized_project)

    assert result.exit_code == EXIT_DOCTOR_FAILED, result.output
    payload = parse_json(result.stdout)
    assert payload["overall"] == "fail"
    checks = {check["id"]: check for check in payload["checks"]}
    for check_id in breakage.failing_checks:
        check = checks[check_id]
        assert check["status"] == "fail", check
        assert MSG_QUARANTINE in (check["hint"] or ""), check
        assert MSG_INIT_HINT in (check["hint"] or ""), check


# --------------------------------------------------------------------------------------
# S-D5: 復旧経路が行き止まりでない（詳細設計 17.4.4）
#
# **この1本が RV-1 の実害に対する回帰テストである。**
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("breakage", BREAKAGES, ids=lambda b: b.id)
def test_the_documented_recovery_procedure_actually_recovers(
    initialized_project: Path, cli: CliInvoke, breakage: Breakage
) -> None:
    """`doctor`=5 → 退避 → `init`=0 → `doctor`=0 の4手順が成立する（S-D5）。

    出所: 詳細設計 17.4.4。**`doctor` の助言と、その助言を実行した結果は一致していなければ
    ならない**（R-6）。T-009 が RV-1 として報告した実害は「助言に従うと 70 で終わる」であり、
    この4手順が通ることがその解消の定義である。
    """
    broken = breakage.apply(initialized_project)

    # 手順1: doctor は 5 で診断し、退避と init を助言する
    diagnosis = cli("doctor", "--json", project=initialized_project)
    assert diagnosis.exit_code == EXIT_DOCTOR_FAILED, diagnosis.output
    hints = [check["hint"] or "" for check in parse_json(diagnosis.stdout)["checks"]]
    assert any(MSG_QUARANTINE in hint and MSG_INIT_HINT in hint for hint in hints)

    # 手順2: 利用者が退避する（製品は退避しない。R-2）
    _quarantine(initialized_project, broken)

    # 手順3: init は不足分だけを作り、0 で終わる
    repaired = cli("init", project=initialized_project)
    assert repaired.exit_code == EXIT_OK, repaired.output

    # 手順4: doctor が 0（fail 0件）
    verified = cli("doctor", "--json", project=initialized_project)
    assert verified.exit_code == EXIT_OK, verified.output
    assert parse_json(verified.stdout)["summary"]["fail"] == 0


@pytest.mark.parametrize("breakage", BREAKAGES, ids=lambda b: b.id)
def test_skipping_the_quarantine_step_fails_with_the_same_hint(
    initialized_project: Path, cli: CliInvoke, breakage: Breakage
) -> None:
    """手順2 を飛ばして `init` すると 1 で終わり、同じ Hint を出す（詳細設計 17.4.4）。

    **70（内部エラー）にはならない。**
    """
    breakage.apply(initialized_project)

    result = cli("init", project=initialized_project)

    assert result.exit_code == EXIT_RUNTIME_ERROR, result.output
    assert MSG_QUARANTINE in result.stderr
    assert MSG_INIT_HINT in result.stderr


# --------------------------------------------------------------------------------------
# S-D6: `init` の preflight（詳細設計 12.5 / 17.4 の R-5）
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "breakage",
    [b for b in BREAKAGES if b.marker == MSG_NOT_A_DIRECTORY],
    ids=lambda b: b.id,
)
def test_init_writes_nothing_when_the_structure_is_broken(
    initialized_project: Path, cli: CliInvoke, breakage: Breakage
) -> None:
    """種別1 の破損では `init` が生成物を1つも書かずに 1 で終わる（S-D6）。

    出所: 詳細設計 17.4 の R-5。`config.yaml` を消してから `init` すると、
    preflight が無ければ `config.yaml` だけが復活して**中途半端な状態**が残る。
    """
    breakage.apply(initialized_project)
    config_path(initialized_project).unlink()

    result = cli("init", project=initialized_project)

    assert result.exit_code == EXIT_RUNTIME_ERROR, result.output
    assert not config_path(initialized_project).exists(), (
        "preflight で止まらず、生成物を書いている（17.4 の R-5）"
    )


# --------------------------------------------------------------------------------------
# S-D7: 壊れた状態の `run` が記録を残さない（詳細設計 17.4 の R-1 / R-5）
# --------------------------------------------------------------------------------------


def test_run_leaves_no_task_behind_when_logs_are_broken(
    initialized_project: Path, cli: CliInvoke
) -> None:
    """`logs/` が壊れた状態の `run` は 1 で終わり、Task 行を作らない（S-D7）。

    出所: 詳細設計 17.4 の R-1 / R-5・11.3。**記録できない実行を進めない**
    （却下案 E: degrade して続行する）。復旧後に `task list` が空であることで判定する。
    """
    broken = _replace_dir_with_file(initialized_project, "logs")

    result = cli("run", "--agent", "echo", project=initialized_project)
    assert result.exit_code == EXIT_RUNTIME_ERROR, result.output

    _quarantine(initialized_project, broken)
    assert cli("init", project=initialized_project).exit_code == EXIT_OK

    listed = cli("task", "list", "--json", project=initialized_project)
    assert listed.exit_code == EXIT_OK, listed.output
    assert parse_json(listed.stdout)["tasks"] == []
