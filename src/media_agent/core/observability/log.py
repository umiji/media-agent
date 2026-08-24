"""運用ログ（詳細設計 11.2）。

**監査記録ではない。** ここへ流したものは `logging.level` の設定で消える。
判断の追跡は `audit.py` の `AuditRecorder` が行う（詳細設計 11.1）。

- ルートロガー名は `media_agent`。アプリのロガーはすべてこの配下に置く
- ファイルは 1 MiB × 3世代で回転する。**運用ログは「消えてよい」記録である**
- ファイルハンドラを追加してよいのは**プロジェクトルートが解決できた後**（罠 D-T16）
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from media_agent.core.clock import to_iso
from media_agent.core.config.models import LogLevel
from media_agent.core.observability.masking import mask_text

__all__ = [
    "BACKUP_COUNT",
    "MAX_BYTES",
    "ROOT_LOGGER_NAME",
    "SecretMaskingFilter",
    "get_logger",
    "setup_logging",
]

#: アプリのロガーの根（詳細設計 11.2）。
ROOT_LOGGER_NAME = "media_agent"

#: 回転の閾値と世代数（詳細設計 11.2）。
MAX_BYTES = 1_048_576
BACKUP_COUNT = 3

_FILE_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(message)s"
_STDERR_FORMAT = "%(levelname)s: %(message)s"

#: `config.logging.level` から `logging` のレベルへの対応。
_LEVELS: dict[LogLevel, int] = {
    LogLevel.DEBUG: logging.DEBUG,
    LogLevel.INFO: logging.INFO,
    LogLevel.WARNING: logging.WARNING,
    LogLevel.ERROR: logging.ERROR,
}


class UtcFormatter(logging.Formatter):
    """`asctime` を 6.2 の形式（UTC・マイクロ秒・末尾 `Z`）で書く。

    `logging` の `datefmt` はマイクロ秒を扱えないため、`formatTime` を置き換える。
    """

    def formatTime(  # noqa: N802 - logging の API 名
        self, record: logging.LogRecord, datefmt: str | None = None
    ) -> str:
        return to_iso(datetime.fromtimestamp(record.created, tz=UTC))


class SecretMaskingFilter(logging.Filter):
    """秘密値らしい `key=value` を伏せてから出力する（詳細設計 11.4）。

    フィルタはロガーではなく**ハンドラへ**付ける。ロガーに付けたフィルタは、
    子ロガーから伝播してきたレコードには適用されないため。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        masked = mask_text(message)
        if masked != message:
            record.msg = masked
            record.args = ()
        return True


def setup_logging(
    *,
    level: LogLevel = LogLevel.INFO,
    log_path: Path | None = None,
    verbose: bool = False,
    quiet: bool = False,
) -> None:
    """`media_agent` ロガーを構成する（詳細設計 11.2）。

    **何度呼んでも二重にハンドラが付かない**（同じプロセスで CLI を複数回呼ぶテストのため）。

    Args:
        level: ファイルへ出すレベル（`config.logging.level`）
        log_path: ファイル出力先。`None` なら stderr だけ（プロジェクト解決前。罠 D-T16）
        verbose: stderr を `DEBUG` 以上にする（`-v`）
        quiet: stderr を `ERROR` 以上にする（`-q`）
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    # 他パッケージのロガーには触れない。ルートロガーへも流さない（二重出力の防止）。
    logger.propagate = False

    file_level = _LEVELS[level]
    stderr_level = (
        logging.DEBUG if verbose else logging.ERROR if quiet else logging.WARNING
    )
    logger.setLevel(min(file_level, stderr_level))

    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(stderr_level)
    stderr_handler.setFormatter(logging.Formatter(_STDERR_FORMAT))
    stderr_handler.addFilter(SecretMaskingFilter())
    logger.addHandler(stderr_handler)

    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(UtcFormatter(_FILE_FORMAT))
        file_handler.addFilter(SecretMaskingFilter())
        logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """`media_agent.<name>` のロガーを返す（詳細設計 11.2）。

    ログ本文には `task=... agent=... action=...` の形で識別子を含めること。
    行の grep で1つの実行を追えるようにするため。
    """
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")
