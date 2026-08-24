"""`core/observability/log.py` の単体テスト（詳細設計 11.2）。

**運用ログの試験である。** 監査記録の試験は `test_observability_audit.py`。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from media_agent.core.config.models import LogLevel
from media_agent.core.observability.log import (
    BACKUP_COUNT,
    MAX_BYTES,
    ROOT_LOGGER_NAME,
    get_logger,
    setup_logging,
)

_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z ")


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    """テストの間に構成したハンドラを残さない。"""
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    saved = list(logger.handlers)
    level = logger.level
    propagate = logger.propagate
    logger.handlers = []
    yield
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    logger.handlers = saved
    logger.level = level
    logger.propagate = propagate


def test_get_logger_is_under_the_application_root() -> None:
    assert get_logger("runtime").name == f"{ROOT_LOGGER_NAME}.runtime"


def test_writes_to_the_given_file(tmp_path: Path) -> None:
    """出力先は呼び出し側が渡す（`core/` はパスを組み立てない。品質基準 Q7）。"""
    log_path = tmp_path / "logs" / "media-agent.log"

    setup_logging(level=LogLevel.INFO, log_path=log_path)
    get_logger("runtime").info("agent=echo task=abc started")

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert _TIMESTAMP.match(lines[0])
    assert "INFO" in lines[0]
    assert "media_agent.runtime" in lines[0]
    assert "agent=echo task=abc started" in lines[0]


def test_level_suppresses_operational_log(tmp_path: Path) -> None:
    """**運用ログはレベルで抑制される**（監査記録との違い。詳細設計 11.1）。"""
    log_path = tmp_path / "media-agent.log"

    setup_logging(level=LogLevel.ERROR, log_path=log_path)
    logger = get_logger("runtime")
    logger.info("これは出ない")
    logger.error("これは出る")

    content = log_path.read_text(encoding="utf-8")
    assert "これは出ない" not in content
    assert "これは出る" in content


def test_no_file_handler_before_the_project_is_resolved(tmp_path: Path) -> None:
    """`log_path` が無ければファイルへ書かない（罠 D-T16）。"""
    setup_logging(level=LogLevel.INFO, log_path=None)

    logger = logging.getLogger(ROOT_LOGGER_NAME)
    assert all(not hasattr(handler, "baseFilename") for handler in logger.handlers)
    assert list(tmp_path.iterdir()) == []


def test_setup_is_idempotent(tmp_path: Path) -> None:
    """同じプロセスで複数回呼んでもハンドラが増えない（テストと CLI の再入）。"""
    log_path = tmp_path / "media-agent.log"

    setup_logging(log_path=log_path)
    setup_logging(log_path=log_path)
    get_logger("runtime").warning("一度だけ")

    assert len(logging.getLogger(ROOT_LOGGER_NAME).handlers) == 2
    assert log_path.read_text(encoding="utf-8").count("一度だけ") == 1


def test_does_not_propagate_to_the_root_logger(tmp_path: Path) -> None:
    """ルートロガーへ二重に流さない（詳細設計 11.2）。"""
    setup_logging(log_path=tmp_path / "media-agent.log")

    assert logging.getLogger(ROOT_LOGGER_NAME).propagate is False


def test_stderr_level_follows_verbose_and_quiet(tmp_path: Path) -> None:
    """既定は WARNING、`-v` で DEBUG、`-q` で ERROR（詳細設計 11.2）。"""

    def stderr_level() -> int:
        handler = logging.getLogger(ROOT_LOGGER_NAME).handlers[0]
        return handler.level

    setup_logging()
    assert stderr_level() == logging.WARNING
    setup_logging(verbose=True)
    assert stderr_level() == logging.DEBUG
    setup_logging(quiet=True)
    assert stderr_level() == logging.ERROR


def test_file_handler_rotates_by_size(tmp_path: Path) -> None:
    """1 MiB × 3世代で回転する（詳細設計 11.2）。"""
    setup_logging(log_path=tmp_path / "media-agent.log")

    handler = logging.getLogger(ROOT_LOGGER_NAME).handlers[1]

    assert handler.maxBytes == MAX_BYTES  # type: ignore[attr-defined]
    assert handler.backupCount == BACKUP_COUNT  # type: ignore[attr-defined]


def test_secret_looking_values_are_masked(tmp_path: Path) -> None:
    """運用ログにも秘密値のマスクを適用する（詳細設計 11.4 / 品質基準 Q10）。"""
    log_path = tmp_path / "media-agent.log"

    setup_logging(level=LogLevel.INFO, log_path=log_path)
    get_logger("runtime").info("input=%s", {"api_key": "s3cret-value"})

    content = log_path.read_text(encoding="utf-8")
    assert "s3cret-value" not in content
    assert "***" in content
