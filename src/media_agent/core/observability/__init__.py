"""可観測性（要件定義書5.5節・17節）。

**運用ログ（`log.py`）と監査記録（`audit.py`）は別物である**（詳細設計 11.1）。

| | 運用ログ | 監査記録 |
| --- | --- | --- |
| 出力先 | `logs/media-agent.log` と stderr | `logs/audit.jsonl` と `decisions` テーブル |
| 書き込み口 | 標準ライブラリ `logging` | **`AuditRecorder` ただ1つ** |
| レベルによる抑制 | する | **しない。常に全件記録する** |
| 欠落 | 許容する | 許容しない |

監査記録を運用ログの1レベルとして実装しないこと。`logging.level` の設定で消せる記録は、
監査記録ではない（用語集「AuditRecorder」）。
"""

from __future__ import annotations

from media_agent.core.observability.audit import AuditRecord, AuditRecorder
from media_agent.core.observability.log import get_logger, setup_logging

__all__ = ["AuditRecord", "AuditRecorder", "get_logger", "setup_logging"]
