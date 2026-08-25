"""`media-agent doctor` の15検査（詳細設計 13.2）。

**この関数群は副作用を持たない**（13.1）。ファイルを作らない・直さない・DB を作らない・
マイグレーションを実行しない。唯一の例外は `logs.writable` で、一時ファイルを作って
**必ず削除する**。

- **最初の異常で打ち切らない。** 15項目すべてを実行してから結果をまとめる
- **認証情報の不在を異常として報告しない**（PO 制約 C-2 / 13.2 の検査12）。
  `.env` が無いのは正常（`skipped`）であり、`fail` になるのは
  「あって、しかも Git の追跡対象である」場合だけ
- 検査は `id` で識別する。表示文言は判定対象にしない（用語集「check id」）
"""

from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import closing, contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from media_agent.core.config.loader import load_config
from media_agent.core.config.models import (
    CONFIG_SCHEMA_VERSION,
    ActionName,
    Config,
)
from media_agent.core.db.connection import PRAGMAS
from media_agent.core.db.migrations import (
    SCHEMA_VERSION,
    TABLE_NAMES,
    ensure_schema,
    schema_version,
)
from media_agent.core.db.repositories import DecisionRepository
from media_agent.core.observability.audit import AuditRecorder
from media_agent.core.observability.log import get_logger
from media_agent.core.policy import PolicyEngine, PolicyRequest
from media_agent.errors import (
    ConfigError,
    ConfigValidationError,
    ConfigVersionError,
)
from media_agent.project.layout import ProjectLayout

__all__ = [
    "CHECK_ORDER",
    "REQUIRED_GITIGNORE_ENTRIES",
    "CheckResult",
    "CheckStatus",
    "DiagnosticsReport",
    "run_diagnostics",
]


class CheckStatus(StrEnum):
    """検査結果の4値（詳細設計 13.2）。"""

    ok = "ok"
    warn = "warn"
    skipped = "skipped"
    fail = "fail"


#: 検査の並び（詳細設計 13.2 の表の順）。**15項目すべてが必ず1行ずつ出る。**
CHECK_ORDER: tuple[str, ...] = (
    "structure.files",
    "structure.dirs",
    "config.syntax",
    "config.schema",
    "config.version",
    "config.consistency",
    "db.file",
    "db.schema",
    "db.foreign_keys",
    "logs.writable",
    "security.gitignore",
    "security.env_not_tracked",
    "agents.registry",
    "policy.config",
    "runtime.python",
)

#: `.media-agent/.gitignore` が**行として**持つべき除外（詳細設計 13.2 の検査11 / 18.2）。
REQUIRED_GITIGNORE_ENTRIES: tuple[str, ...] = ("data/", "logs/", ".env")

#: この実装が要求する Python の最低バージョン（方式設計 3.1）。
MINIMUM_PYTHON = (3, 11)

_INIT_HINT = "media-agent init を実行してください（既存ファイルは変更されません）"
_SYNTAX_HINT = "YAML の構文を確認してください"
_BUG_HINT = "実装の不具合です。報告してください"


def _quarantine_hint(targets: str) -> str:
    """構造破損（詳細設計 17.4）のときの `hint`（検査2・7・10。R-6）。

    **`media-agent init` だけを助言すると、利用者がそれに従っても復旧しない**
    （T-009 / RV-1 の実害）。`doctor` の助言と、その助言を実行した結果は一致して
    いなければならない。安定文字列は `退避` と `media-agent init` の2つ（17.3）。
    """
    return f"{targets} を退避してから media-agent init を実行してください"


@dataclass(frozen=True)
class CheckResult:
    """1項目の検査結果（詳細設計 13.2 / 13.3）。"""

    id: str
    status: CheckStatus
    message: str
    hint: str | None = None

    def as_json(self) -> dict[str, Any]:
        """`--json` の `checks` 要素（詳細設計 13.3）。"""
        return {
            "id": self.id,
            "status": self.status.value,
            "message": self.message,
            "hint": self.hint,
        }


@dataclass(frozen=True)
class DiagnosticsReport:
    """15項目の結果と集計（詳細設計 13.3）。"""

    project_root: Path
    checks: tuple[CheckResult, ...]

    @property
    def summary(self) -> dict[str, int]:
        """状態ごとの件数。**4状態すべてのキーを返す**（0 でも省略しない）。"""
        counts = dict.fromkeys((status.value for status in CheckStatus), 0)
        for check in self.checks:
            counts[check.status.value] += 1
        return counts

    @property
    def failed(self) -> int:
        return self.summary[CheckStatus.fail.value]

    @property
    def overall(self) -> str:
        """`fail` が1件以上なら `"fail"`、それ以外は `"ok"`（詳細設計 13.3）。"""
        return CheckStatus.fail.value if self.failed else CheckStatus.ok.value

    def as_json(self) -> dict[str, Any]:
        """`--json` 出力（詳細設計 13.3）。"""
        return {
            "project_root": str(self.project_root),
            "overall": self.overall,
            "checks": [check.as_json() for check in self.checks],
            "summary": self.summary,
        }


def run_diagnostics(layout: ProjectLayout) -> DiagnosticsReport:
    """15項目を**すべて**実行して結果を返す（詳細設計 13.1 / 13.2）。

    例外を送出しない。設定が壊れていても `ConfigError` にせず `fail` として列挙する
    （13.4 の意図した非対称）。
    """
    config_probe = _probe_config(layout.config_path)
    db_probe = _probe_db(layout)
    checks = (
        _check_structure_files(layout),
        _check_structure_dirs(layout),
        config_probe.syntax,
        config_probe.schema,
        config_probe.version,
        _check_config_consistency(config_probe.config),
        db_probe.file,
        db_probe.schema,
        db_probe.foreign_keys,
        _check_logs_writable(layout),
        _check_gitignore(layout),
        _check_env_not_tracked(layout),
        _check_agents_registry(),
        _check_policy_config(config_probe.config, layout),
        _check_runtime_python(),
    )
    _verify_order(checks)
    return DiagnosticsReport(project_root=layout.root, checks=checks)


def _verify_order(checks: tuple[CheckResult, ...]) -> None:
    """並びと欠落を実装側で検証する（受け入れテストが id の集合を判定するため）。"""
    ids = tuple(check.id for check in checks)
    if ids != CHECK_ORDER:
        raise AssertionError(f"doctor の検査の並びが定義と違います: {ids}")


# --------------------------------------------------------------------------------------
# 1・2 構造
# --------------------------------------------------------------------------------------


def _check_structure_files(layout: ProjectLayout) -> CheckResult:
    """検査1: `config.yaml` / `strategy.md` / `rules.md` が存在し、読み取れる。"""
    targets = (layout.config_path, layout.strategy_path, layout.rules_path)
    missing = [layout.relative(path) for path in targets if not _is_readable_file(path)]
    if missing:
        return _fail(
            "structure.files",
            f"読み取れないファイルがあります: {', '.join(missing)}",
            _INIT_HINT,
        )
    return _ok(
        "structure.files", "config.yaml / strategy.md / rules.md がそろっています"
    )


def _check_structure_dirs(layout: ProjectLayout) -> CheckResult:
    """検査2: `agents/` `memory/` `data/` `logs/` の4つが存在する（ディレクトリである）。

    **通常ファイルとして存在する場合は hint を変える**（詳細設計 13.2 の検査2 /
    17.4 の R-6）。`init` は既存ファイルを消さないため、退避を先に助言しないと
    利用者が行き止まりに入る。
    """
    targets = (layout.agents_dir, layout.memory_dir, layout.data_dir, layout.logs_dir)
    broken = [layout.relative(path) for path in targets if _is_not_a_directory(path)]
    if broken:
        return _fail(
            "structure.dirs",
            f"ディレクトリではありません: {', '.join(broken)}",
            _quarantine_hint(", ".join(broken)),
        )
    missing = [layout.relative(path) for path in targets if not path.is_dir()]
    if missing:
        return _fail(
            "structure.dirs",
            f"ディレクトリがありません: {', '.join(missing)}",
            _INIT_HINT,
        )
    return _ok("structure.dirs", "agents / memory / data / logs がそろっています")


def _is_not_a_directory(path: Path) -> bool:
    """存在するが、ディレクトリではない（詳細設計 17.4.1 の種別1）。"""
    return path.exists() and not path.is_dir()


def _is_readable_file(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        with path.open("rb"):
            return True
    except OSError:
        return False


# --------------------------------------------------------------------------------------
# 3・4・5 設定（構文 / スキーマ / 版数）
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _ConfigProbe:
    """設定に関する3項目の結果と、成功した場合の `Config`。"""

    syntax: CheckResult
    schema: CheckResult
    version: CheckResult
    config: Config | None


def _probe_config(path: Path) -> _ConfigProbe:
    """検査3・4・5 をまとめて評価する（詳細設計 13.4）。

    **`ConfigError` を送出しない。** 読めない設定は検査結果として報告する。
    構文が壊れていればスキーマと版数は評価できないため `skipped` にする。
    """
    raw = _read_raw_config(path)
    if isinstance(raw, CheckResult):
        return _ConfigProbe(
            syntax=raw,
            schema=_skipped("config.schema", "設定を読めないため検査できません"),
            version=_skipped("config.version", "設定を読めないため検査できません"),
            config=None,
        )
    syntax = _ok("config.syntax", "config.yaml を YAML として読めます")
    try:
        config = load_config(path)
    except ConfigVersionError as exc:
        return _ConfigProbe(
            syntax=syntax,
            schema=_skipped("config.schema", "版数が未対応のため検査できません"),
            version=_fail(
                "config.version",
                exc.message,
                f"サポートする config 版数は {CONFIG_SCHEMA_VERSION} です",
            ),
            config=None,
        )
    except ConfigValidationError as exc:
        return _ConfigProbe(
            syntax=syntax,
            schema=_fail(
                "config.schema",
                "設定の検証に失敗しました: " + " / ".join(exc.details),
                exc.hint,
            ),
            version=_check_config_version(raw),
            config=None,
        )
    except ConfigError as exc:  # pragma: no cover - 構文検査を通った後は起きない
        return _ConfigProbe(
            syntax=syntax,
            schema=_fail("config.schema", exc.message, exc.hint),
            version=_skipped("config.version", "設定を読めないため検査できません"),
            config=None,
        )
    return _ConfigProbe(
        syntax=syntax,
        schema=_ok("config.schema", "設定はスキーマを満たしています"),
        version=_check_config_version(raw),
        config=config,
    )


def _read_raw_config(path: Path) -> Mapping[str, Any] | CheckResult:
    """検査3: `yaml.safe_load` で読め、mapping であること。

    パーサは `safe_load` のみ（罠 T-6）。失敗した場合は `config.syntax` の結果を返す。
    """
    if not path.is_file():
        return _fail("config.syntax", f"config.yaml がありません: {path}", _INIT_HINT)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return _fail("config.syntax", f"config.yaml を読めません: {exc}", _INIT_HINT)
    except yaml.YAMLError as exc:
        return _fail(
            "config.syntax",
            f"config.yaml の構文が正しくありません: {_yaml_problem(exc)}",
            _SYNTAX_HINT,
        )
    if not isinstance(data, Mapping):
        return _fail(
            "config.syntax",
            "config.yaml の構文が正しくありません（設定は mapping で書きます）: "
            f"読み取れた型 {type(data).__name__}",
            _SYNTAX_HINT,
        )
    return data


def _yaml_problem(exc: yaml.YAMLError) -> str:
    """PyYAML の例外から1行の説明を作る（`loader._yaml_error_details` と同じ考え方）。"""
    mark = getattr(exc, "problem_mark", None)
    problem = getattr(exc, "problem", None) or "YAML として解析できません"
    if mark is not None:
        return f"{mark.line + 1} 行 {mark.column + 1} 列: {problem}"
    return str(problem)


def _check_config_version(raw: Mapping[str, Any]) -> CheckResult:
    """検査5: `version == 1`。キーが無い場合は `warn`（`1` とみなす）。"""
    hint = f"サポートする config 版数は {CONFIG_SCHEMA_VERSION} です"
    if "version" not in raw:
        return _warn(
            "config.version",
            f"version が書かれていません（{CONFIG_SCHEMA_VERSION} とみなします）",
            hint,
        )
    version = raw["version"]
    if isinstance(version, bool) or not isinstance(version, int):
        return _fail(
            "config.version", f"version が整数ではありません: {version!r}", hint
        )
    if version != CONFIG_SCHEMA_VERSION:
        return _fail("config.version", f"未対応の config 版数です: {version}", hint)
    return _ok("config.version", f"config 版数 {version}")


# --------------------------------------------------------------------------------------
# 6 設定の整合
# --------------------------------------------------------------------------------------


def _check_config_consistency(config: Config | None) -> CheckResult:
    """検査6: `content.posts_per_day <= actions.post.max_per_day`。

    上回る場合は `warn`（`fail` にしない）。目標値と上限は別の設定であり、
    食い違っていても動作はする（詳細設計 5.2.3）。
    """
    if config is None:
        return _skipped("config.consistency", "設定を読めないため検査できません")
    post = config.actions.get(ActionName.POST)
    limit = None if post is None else post.max_per_day
    posts_per_day = config.content.posts_per_day
    if limit is None:
        return _ok(
            "config.consistency",
            f"content.posts_per_day ({posts_per_day}) に対する上限は設定されていません",
        )
    if posts_per_day > limit:
        return _warn(
            "config.consistency",
            f"content.posts_per_day ({posts_per_day}) が "
            f"actions.post.max_per_day ({limit}) を超えています",
        )
    return _ok(
        "config.consistency",
        f"content.posts_per_day ({posts_per_day}) <= "
        f"actions.post.max_per_day ({limit})",
    )


# --------------------------------------------------------------------------------------
# 7・8・9 DB
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _DbProbe:
    """DB に関する3項目の結果。"""

    file: CheckResult
    schema: CheckResult
    foreign_keys: CheckResult


def _probe_db(layout: ProjectLayout) -> _DbProbe:
    """検査7・8・9 をまとめて評価する。**DB を作らない**（詳細設計 13.1）。

    **`data/` が通常ファイルの場合と、DB を SQLite として開けない場合は hint を変える**
    （詳細設計 13.2 の検査7 / 17.4 の R-6）。どちらも `media-agent init` だけでは
    復旧せず、先に退避が要る。
    """
    db_path = layout.db_path
    if not db_path.is_file():
        broken = _broken_db_location(db_path)
        if broken is not None:
            relative = layout.relative(broken)
            return _DbProbe(
                file=_fail(
                    "db.file",
                    f"DB を置けません: {relative} の形が違います",
                    _quarantine_hint(relative),
                ),
                schema=_skipped("db.schema", "DB を開けないため検査できません"),
                foreign_keys=_skipped(
                    "db.foreign_keys", "DB を開けないため検査できません"
                ),
            )
        return _DbProbe(
            file=_fail("db.file", f"DB がありません: {db_path}", _INIT_HINT),
            schema=_skipped("db.schema", "DB が無いため検査できません"),
            foreign_keys=_skipped("db.foreign_keys", "DB が無いため検査できません"),
        )
    try:
        with _read_only(db_path) as conn:
            version = schema_version(conn)
            tables = {
                str(row[0])
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            conn.execute("PRAGMA foreign_keys = ON")
            foreign_keys_enabled = int(
                conn.execute("PRAGMA foreign_keys").fetchone()[0]
            )
    except sqlite3.Error as exc:
        # SQLite として開けない DB は `init` では直らない（既存ファイルを消さないため）。
        # 退避を先に助言する（詳細設計 13.2 の検査7 / 17.4 の R-6）。
        return _DbProbe(
            file=_fail(
                "db.file",
                f"DB を SQLite として開けません: {exc}",
                _quarantine_hint(layout.relative(db_path)),
            ),
            schema=_skipped("db.schema", "DB を開けないため検査できません"),
            foreign_keys=_skipped("db.foreign_keys", "DB を開けないため検査できません"),
        )
    return _DbProbe(
        file=_ok("db.file", f"{db_path.name} を SQLite として開けます"),
        schema=_check_db_schema(version, tables),
        foreign_keys=_check_foreign_keys(foreign_keys_enabled),
    )


def _broken_db_location(db_path: Path) -> Path | None:
    """DB を置けない形（構造破損の種別1）なら、その対象を返す（詳細設計 17.4.1）。

    `data/` が通常ファイル、または DB のパスがディレクトリの場合。どちらも
    `init` が既存を消さないため、退避が先に要る。
    """
    if _is_not_a_directory(db_path.parent):
        return db_path.parent
    if db_path.is_dir():
        return db_path
    return None


@contextmanager
def _read_only(db_path: Path) -> Iterator[sqlite3.Connection]:
    """検査用の読み取り専用接続（詳細設計 13.1: 副作用を持たない）。

    WAL の残骸が無い通常の状態では `immutable=1` で開く。この場合 SQLite は
    `-wal` / `-shm` を**作らない**。未チェックポイントの `-wal` がある場合だけ
    `mode=ro` へ落とす（`immutable` は `-wal` を無視するため、古い内容を読んでしまう）。
    """
    wal = db_path.with_name(db_path.name + "-wal")
    query = "mode=ro" if wal.exists() else "immutable=1"
    uri = f"file:{db_path.as_uri().removeprefix('file:')}?{query}"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        yield conn


def _check_db_schema(version: int, tables: set[str]) -> CheckResult:
    """検査8: 版数が一致し、6テーブルがすべて存在する。"""
    missing = [name for name in TABLE_NAMES if name not in tables]
    if version != SCHEMA_VERSION:
        hint = (
            "media-agent init で移行されます"
            if version < SCHEMA_VERSION
            else "Media Agent を更新してください"
        )
        return _fail(
            "db.schema",
            f"スキーマ版数が一致しません: DB {version} / 実装 {SCHEMA_VERSION}",
            hint,
        )
    if missing:
        return _fail(
            "db.schema",
            f"テーブルがありません: {', '.join(missing)}",
            "media-agent init で移行されます",
        )
    return _ok(
        "db.schema",
        f"スキーマ版数 {version} / {len(TABLE_NAMES)} テーブルがそろっています",
    )


def _check_foreign_keys(enabled: int) -> CheckResult:
    """検査9: 外部キーが実際に有効になる（罠 T-2 の再発検出）。

    接続時に適用する `PRAGMAS` から `foreign_keys` が落ちた場合も検出する。
    「設定してあるつもりで効いていない」の両方の原因をここで見る。
    """
    declared = ("foreign_keys", "ON") in PRAGMAS
    if not declared:
        return _fail(
            "db.foreign_keys",
            "接続時の PRAGMA に foreign_keys が含まれていません",
            _BUG_HINT,
        )
    if enabled != 1:
        return _fail(
            "db.foreign_keys",
            f"PRAGMA foreign_keys が有効になりません: {enabled}",
            _BUG_HINT,
        )
    return _ok("db.foreign_keys", "外部キー制約が有効です")


# --------------------------------------------------------------------------------------
# 10 ログの書き込み
# --------------------------------------------------------------------------------------


def _check_logs_writable(layout: ProjectLayout) -> CheckResult:
    """検査10: `logs/` に一時ファイルを作成して削除できる。

    **作った一時ファイルは必ず削除する**（詳細設計 13.1）。
    `logs/` が通常ファイルの場合は構造破損として退避を助言する（17.4 の R-6）。
    """
    hint = "ディレクトリの権限を確認してください"
    if _is_not_a_directory(layout.logs_dir):
        # **通常ファイルとして存在する場合は hint を変える**（詳細設計 13.2 の検査10 /
        # 17.4 の R-6）。`init` は既存ファイルを消さないため、退避が先に要る。
        relative = layout.relative(layout.logs_dir)
        return _fail(
            "logs.writable",
            f"ディレクトリではありません: {relative}",
            _quarantine_hint(relative),
        )
    if not layout.logs_dir.is_dir():
        return _fail(
            "logs.writable",
            f"ディレクトリがありません: {layout.relative(layout.logs_dir)}",
            _INIT_HINT,
        )
    try:
        with tempfile.NamedTemporaryFile(
            dir=layout.logs_dir, prefix=".doctor-", suffix=".tmp"
        ) as handle:
            handle.write(b"media-agent doctor\n")
    except OSError as exc:
        return _fail("logs.writable", f"logs/ へ書き込めません: {exc}", hint)
    return _ok("logs.writable", f"{layout.relative(layout.logs_dir)} へ書き込めます")


# --------------------------------------------------------------------------------------
# 11・12 Security（要件定義書14.2）
# --------------------------------------------------------------------------------------


def _check_gitignore(layout: ProjectLayout) -> CheckResult:
    """検査11: `.media-agent/.gitignore` が `data/` `logs/` `.env` を行として含む。"""
    hint = "要件14.2。media-agent init --force で復元できます"
    if not layout.gitignore_path.is_file():
        return _fail(
            "security.gitignore",
            f"{layout.relative(layout.gitignore_path)} がありません",
            hint,
        )
    try:
        text = layout.gitignore_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _fail("security.gitignore", f".gitignore を読めません: {exc}", hint)
    lines = {line.strip() for line in text.splitlines()}
    missing = [entry for entry in REQUIRED_GITIGNORE_ENTRIES if entry not in lines]
    if missing:
        return _fail(
            "security.gitignore",
            f"除外の指定がありません: {', '.join(missing)}",
            hint,
        )
    return _ok(
        "security.gitignore",
        f"{', '.join(REQUIRED_GITIGNORE_ENTRIES)} が除外されています",
    )


def _check_env_not_tracked(layout: ProjectLayout) -> CheckResult:
    """検査12: `.env*` が無い、または Git の追跡対象でない。

    **認証情報が無いことを異常として報告しない**（PO 制約 C-2）。`.env` が無いのは
    正常であり `skipped`。`fail` になるのは「あって、しかも追跡されている」場合だけ。
    """
    candidates = sorted(path for path in layout.base.glob(".env*") if path.is_file())
    if not candidates:
        return _skipped(
            "security.env_not_tracked",
            ".env はありません（Stage 0 では認証情報を使いません）",
        )
    git = shutil.which("git")
    if git is None or not _inside_work_tree(git, layout.root):
        return _skipped(
            "security.env_not_tracked",
            "Git リポジトリではないため確認できません",
        )
    tracked = [
        layout.relative(path) for path in candidates if _git_tracked(git, layout, path)
    ]
    if tracked:
        return _fail(
            "security.env_not_tracked",
            f".env が Git の追跡対象です: {', '.join(tracked)}",
            "git rm --cached で追跡から外してください",
        )
    return _ok(
        "security.env_not_tracked",
        f"{len(candidates)} 件の .env は追跡されていません",
    )


def _git(git: str, args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Git を1回呼ぶ。**ネットワークへ出るサブコマンドは使わない**（PO 制約 C-1）。"""
    return subprocess.run(  # noqa: S603 - 引数は固定。利用者入力を渡さない
        [git, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _inside_work_tree(git: str, root: Path) -> bool:
    try:
        result = _git(git, ["rev-parse", "--is-inside-work-tree"], root)
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def _git_tracked(git: str, layout: ProjectLayout, path: Path) -> bool:
    try:
        result = _git(
            git, ["ls-files", "--error-unmatch", "--", str(path)], layout.root
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


# --------------------------------------------------------------------------------------
# 13・14・15 Runtime
# --------------------------------------------------------------------------------------


def _check_agents_registry() -> CheckResult:
    """検査13: `build_default_registry()` が Agent を返し、`echo` が引ける。"""
    from media_agent.agents.builtin import build_default_registry

    try:
        registry = build_default_registry()
        registry.get("echo")
    except Exception as exc:  # noqa: BLE001 - 検査は例外を外へ出さない（13.1）
        return _fail(
            "agents.registry", f"Registry を組み立てられません: {exc}", _BUG_HINT
        )
    if len(registry) < 1:  # pragma: no cover - get("echo") が先に失敗する
        return _fail("agents.registry", "Agent が1つも登録されていません", _BUG_HINT)
    return _ok(
        "agents.registry",
        f"{len(registry)} 件の Agent が登録されています: {', '.join(registry.names())}",
    )


def _check_policy_config(config: Config | None, layout: ProjectLayout) -> CheckResult:
    """検査14: 4 Action すべてで `check(..., record=False)` が判定を返す。

    - **`record=False` で呼ぶ**（罠 D-T14）。`True` だと診断そのものが上限を消費する
    - 計数用の接続には**メモリ上の DB** を使う。`doctor` はプロジェクトの DB を
      作らない・触らないため（13.1）。この検査が見るのは設定の妥当性であり、
      実際の実行回数ではない
    """
    if config is None:
        return _skipped("policy.config", "設定を読めないため検査できません")
    hint = "actions の設定を確認してください"
    try:
        with closing(sqlite3.connect(":memory:")) as conn:
            conn.row_factory = sqlite3.Row
            ensure_schema(conn)
            decisions = DecisionRepository(conn)
            engine = PolicyEngine(
                config=config,
                decisions=decisions,
                audit=AuditRecorder(
                    decisions=decisions,
                    audit_path=layout.audit_path,
                    logger=get_logger("doctor"),
                ),
            )
            outcomes = {
                action.value: engine.check(
                    PolicyRequest(action=action.value), record=False
                ).outcome.value
                for action in ActionName
            }
    except Exception as exc:  # noqa: BLE001 - 検査は例外を外へ出さない（13.1）
        return _fail("policy.config", f"Policy を判定できません: {exc}", hint)
    rendered = " ".join(f"{name}={outcome}" for name, outcome in outcomes.items())
    return _ok(
        "policy.config", f"{len(outcomes)} 件の Action を判定できます: {rendered}"
    )


def _check_runtime_python() -> CheckResult:
    """検査15: 実行中の Python が 3.11 以上。"""
    current = sys.version_info[:2]
    required = ".".join(str(part) for part in MINIMUM_PYTHON)
    running = ".".join(str(part) for part in current)
    if current < MINIMUM_PYTHON:  # pragma: no cover - 3.11 未満では動かない
        return _fail(
            "runtime.python",
            f"Python {running} で実行されています（{required} 以上が必要です）",
            f"Python {required} 以上で実行してください",
        )
    return _ok("runtime.python", f"Python {running}")


# --------------------------------------------------------------------------------------
# 生成のヘルパ
# --------------------------------------------------------------------------------------


def _ok(check_id: str, message: str) -> CheckResult:
    return CheckResult(id=check_id, status=CheckStatus.ok, message=message)


def _warn(check_id: str, message: str, hint: str | None = None) -> CheckResult:
    return CheckResult(id=check_id, status=CheckStatus.warn, message=message, hint=hint)


def _skipped(check_id: str, message: str) -> CheckResult:
    return CheckResult(id=check_id, status=CheckStatus.skipped, message=message)


def _fail(check_id: str, message: str, hint: str | None = None) -> CheckResult:
    return CheckResult(id=check_id, status=CheckStatus.fail, message=message, hint=hint)
