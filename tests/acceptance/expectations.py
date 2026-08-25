"""受け入れテストが判定してよい契約と、共通のヘルパ。

出所: T-003（`docs/tasks/T-003.md`）。期待値の正典は
`docs/design/stage0-detail.md` 19章「受け入れテスト S-A〜S-I への対応」である。

**このモジュールは `media_agent` をモジュール先頭で import しない。**
製品への import はヘルパの内側で行い、未実装時の失敗が「どのシナリオで」起きたかを
テスト単位で読めるようにする（方式設計 17.2 の順序制約 O-2）。
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------------------
# 契約として判定してよい定数
# --------------------------------------------------------------------------------------

#: `.media-agent/` 配下の生成物のうちファイル（詳細設計 12.1）。
#: `data/media-agent.db` は含めない（申し送り N-1 / 詳細設計 12.4。DB の存在は S-B で判定する）。
SCAFFOLD_FILES: tuple[str, ...] = (
    ".media-agent/config.yaml",
    ".media-agent/strategy.md",
    ".media-agent/rules.md",
    ".media-agent/agents/.gitkeep",
    ".media-agent/memory/.gitkeep",
    ".media-agent/.gitignore",
)

#: `init` が作るディレクトリ（詳細設計 12.1 の 6・7）。
SCAFFOLD_DIRS: tuple[str, ...] = (
    ".media-agent/data",
    ".media-agent/logs",
)

#: テンプレート由来のファイル（詳細設計 12.5。`--force` の対象はこの4つだけ）。
TEMPLATE_FILES: tuple[str, ...] = (
    ".media-agent/config.yaml",
    ".media-agent/strategy.md",
    ".media-agent/rules.md",
    ".media-agent/.gitignore",
)

#: `doctor` の check id（詳細設計 13.2 の15個）。
#: **判定は id で行い、表示文言では行わない**（申し送り N-3 / 用語集「check id」）。
CHECK_IDS: tuple[str, ...] = (
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

#: `doctor` の検査結果の値域（詳細設計 13.2）。
CHECK_STATUSES: frozenset[str] = frozenset({"ok", "warn", "skipped", "fail"})

#: `status` のラベル（詳細設計14章。**ラベル名が安定文字列である**）。
STATUS_LABELS: tuple[str, ...] = (
    "project",
    "config",
    "automation",
    "database",
    "agents",
    "tasks",
    "recent tasks",
)

#: Task の状態（詳細設計 9.1）。
TASK_STATUSES: tuple[str, ...] = (
    "pending",
    "running",
    "completed",
    "failed",
    "cancelled",
)

#: 組み込み Agent（詳細設計 8.4）。
BUILTIN_AGENTS: tuple[str, ...] = ("echo", "fail")

#: 監査記録の必須9キー（要件定義書5.5節 / 詳細設計 11.3）。
AUDIT_KEYS: tuple[str, ...] = (
    "timestamp",
    "agent",
    "task",
    "input",
    "decision",
    "reason",
    "action",
    "result",
    "error",
)

#: スタブコマンド（方式設計 6.4 / 用語集「スタブコマンド」）。
STUB_COMMANDS: tuple[str, ...] = ("setup", "post", "research", "analyze")

#: 安定文字列（詳細設計 17.3）。**`in` で判定してよいのはこの表だけ**（申し送り N-4）。
MSG_NOT_INITIALIZED = "Media Agent が初期化されていません"
MSG_INIT_HINT = "media-agent init"
MSG_STUB_STAGE = "Stage"
MSG_STUB_UNIMPLEMENTED = "未実装"
MSG_CONFIG_FILE = "config.yaml"
MSG_CONFIG_SYNTAX = "構文"
MSG_DOCTOR = "doctor"
MSG_NOT_A_DIRECTORY = "ディレクトリではありません"
MSG_NO_TASKS = "(タスクはありません)"

#: 構造破損の安定文字列（詳細設計 17.3 の追加3行 / 17.4.3。T-012 / D-1）。
#: `MSG_NOT_A_DIRECTORY` は種別1、`MSG_SQLITE` は種別2、`MSG_QUARANTINE` は Hint 側。
MSG_SQLITE = "SQLite"
MSG_QUARANTINE = "退避"

#: オプション名（詳細設計 17.3 の `--limit` 行 / 16.2。T-012 / D-3）。
MSG_LIMIT_OPTION = "--limit"
MSG_STATUS_OPTION = "--status"

#: 終了コード表（方式設計 6.5）。
EXIT_OK = 0
EXIT_RUNTIME_ERROR = 1
EXIT_USAGE = 2
EXIT_NOT_INITIALIZED = 3
EXIT_CONFIG_ERROR = 4
EXIT_DOCTOR_FAILED = 5
EXIT_NOT_IMPLEMENTED = 10

#: `cli` fixture の型。
CliInvoke = Callable[..., Any]


# --------------------------------------------------------------------------------------
# パス・ファイルのヘルパ
# --------------------------------------------------------------------------------------


def base_dir(project: Path) -> Path:
    """`.media-agent/`（詳細設計 4.1 の `ProjectLayout.base`）。"""
    return project / ".media-agent"


def config_path(project: Path) -> Path:
    return base_dir(project) / "config.yaml"


def db_path(project: Path) -> Path:
    return base_dir(project) / "data" / "media-agent.db"


def audit_path(project: Path) -> Path:
    return base_dir(project) / "logs" / "audit.jsonl"


def log_path(project: Path) -> Path:
    return base_dir(project) / "logs" / "media-agent.log"


def write_config_text(project: Path, text: str) -> None:
    """`config.yaml` を任意のテキストで置き換える（S-I 用）。"""
    config_path(project).write_text(text, encoding="utf-8")


def write_config(project: Path, mapping: dict[str, Any]) -> None:
    """`config.yaml` を辞書から書き直す（S-G / S-I 用）。"""
    import yaml

    write_config_text(
        project, yaml.safe_dump(mapping, allow_unicode=True, sort_keys=False)
    )


def base_config(name: str = "sample-project") -> dict[str, Any]:
    """検証を通る最小の設定（詳細設計 5.2.1: 必須項目は `project.name` だけ）。

    テストはこれに必要なキーだけを足して使う。
    """
    return {"version": 1, "project": {"name": name}}


def read_config(project: Path) -> Any:
    """公開 API `load_config()` で設定を読む（詳細設計 5.3）。"""
    from media_agent.core.config.loader import load_config

    return load_config(config_path(project))


def tree_snapshot(project: Path) -> set[str]:
    """`.media-agent/` 配下の相対パス集合。副作用の有無の判定に使う。"""
    return {p.relative_to(project).as_posix() for p in base_dir(project).rglob("*")}


# --------------------------------------------------------------------------------------
# 出力のパース（判定は check id / ラベル / 終了コードで行う）
# --------------------------------------------------------------------------------------

_SCAFFOLD_LINE = re.compile(r"^(created|skipped|updated)\s{2}(\S+)$")
_DOCTOR_LINE = re.compile(r"^\[(ok|warn|skipped|fail)\]\s+(\S+)")
_DOCTOR_SUMMARY = re.compile(
    r"^結果:\s*(\d+)\s*ok\s*/\s*(\d+)\s*warn\s*/\s*(\d+)\s*skipped\s*/\s*(\d+)\s*fail\s*$"
)
_LABELLED_LINE = re.compile(r"^(\S[^:]*?)\s*:\s?(.*)$")


def parse_scaffold_output(stdout: str) -> dict[str, str]:
    """`init` の出力を {相対パス: 動詞} にする（詳細設計 12.6）。

    行の集合の完全一致は判定しない（T-005 で DB の行が増えるため）。
    """
    result: dict[str, str] = {}
    for line in stdout.splitlines():
        matched = _SCAFFOLD_LINE.match(line.rstrip())
        if matched:
            result[matched.group(2)] = matched.group(1)
    return result


def parse_doctor_output(stdout: str) -> dict[str, str]:
    """`doctor` のテキスト出力を {check id: status} にする（詳細設計 13.3）。"""
    result: dict[str, str] = {}
    for line in stdout.splitlines():
        matched = _DOCTOR_LINE.match(line.rstrip())
        if matched:
            result[matched.group(2)] = matched.group(1)
    return result


def parse_doctor_summary(stdout: str) -> dict[str, int]:
    """`結果:` 行を辞書にする（詳細設計 13.3）。見つからなければ AssertionError。"""
    for line in stdout.splitlines():
        matched = _DOCTOR_SUMMARY.match(line.strip())
        if matched:
            return {
                "ok": int(matched.group(1)),
                "warn": int(matched.group(2)),
                "skipped": int(matched.group(3)),
                "fail": int(matched.group(4)),
            }
    raise AssertionError(f"`結果:` 行が出力にありません:\n{stdout}")


def parse_labelled_output(stdout: str) -> dict[str, str]:
    """`ラベル : 値` 形式の行を辞書にする（詳細設計14章 `status` / 15.2 `run`）。"""
    result: dict[str, str] = {}
    for line in stdout.splitlines():
        if line.startswith(" "):
            continue
        matched = _LABELLED_LINE.match(line.rstrip())
        if matched:
            result[matched.group(1).strip()] = matched.group(2).strip()
    return result


def parse_json(stdout: str) -> Any:
    """`--json` 出力を読む。"""
    return json.loads(stdout)


def read_audit_records(project: Path) -> list[dict[str, Any]]:
    """`logs/audit.jsonl` を1行1レコードとして読む（詳細設計 11.3）。"""
    lines = audit_path(project).read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def query_db(
    project: Path, sql: str, params: tuple[Any, ...] = ()
) -> list[sqlite3.Row]:
    """DB を別接続で読む（記録が永続化されていることの確認に使う）。"""
    conn = sqlite3.connect(str(db_path(project)))
    conn.row_factory = sqlite3.Row
    try:
        return list(conn.execute(sql, params))
    finally:
        conn.close()


# --------------------------------------------------------------------------------------
# 公開 API の組み立て（申し送り N-2: S-E〜S-H は公開 API で書いてよい）
# --------------------------------------------------------------------------------------


@dataclass
class RuntimeStack:
    """受け入れテストが公開 API を直接呼ぶための組み立て済み一式（詳細設計 8.3）。"""

    project: Path
    config: Any
    conn: Any
    tasks: Any
    decisions: Any
    audit: Any
    registry: Any
    runner: Any


def build_runtime_stack(project: Path) -> RuntimeStack:
    """`AgentRunner` を公開 API だけで組み立てる（詳細設計 8.3 / 20.2 の D-O6）。"""
    from media_agent.agents.builtin import build_default_registry
    from media_agent.core.config.loader import load_config
    from media_agent.core.db.connection import open_project_db
    from media_agent.core.db.repositories import DecisionRepository, TaskRepository
    from media_agent.core.observability.audit import AuditRecorder
    from media_agent.core.observability.log import get_logger
    from media_agent.core.runtime import AgentRunner
    from media_agent.core.task import TaskService
    from media_agent.project.layout import layout_for

    layout = layout_for(project)
    config = load_config(layout.config_path)
    conn = open_project_db(layout, config)
    logger = get_logger("acceptance")
    tasks = TaskService(TaskRepository(conn))
    decisions = DecisionRepository(conn)
    audit = AuditRecorder(
        decisions=decisions, audit_path=layout.audit_path, logger=logger
    )
    registry = build_default_registry()
    runner = AgentRunner(
        registry=registry,
        tasks=tasks,
        audit=audit,
        logger=logger,
        config=config,
        project_root=layout.root,
    )
    return RuntimeStack(
        project=project,
        config=config,
        conn=conn,
        tasks=tasks,
        decisions=decisions,
        audit=audit,
        registry=registry,
        runner=runner,
    )


def build_policy_engine(project: Path) -> Any:
    """`PolicyEngine` を公開 API だけで組み立てる（詳細設計 10.6）。

    Policy Engine は Config を**受け取るだけ**であり、自分で `config.yaml` を読まない
    （順序制約 O-3）。読み込みは呼び出し側（ここ）が行う。
    """
    from media_agent.core.config.loader import load_config
    from media_agent.core.db.connection import open_project_db
    from media_agent.core.db.repositories import DecisionRepository
    from media_agent.core.observability.audit import AuditRecorder
    from media_agent.core.observability.log import get_logger
    from media_agent.core.policy import PolicyEngine
    from media_agent.project.layout import layout_for

    layout = layout_for(project)
    config = load_config(layout.config_path)
    conn = open_project_db(layout, config)
    decisions = DecisionRepository(conn)
    audit = AuditRecorder(
        decisions=decisions,
        audit_path=layout.audit_path,
        logger=get_logger("acceptance"),
    )
    return PolicyEngine(config=config, decisions=decisions, audit=audit)
