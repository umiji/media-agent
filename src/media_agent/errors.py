"""例外階層（詳細設計 17.1 / 方式設計 6.5）。

- すべて `MediaAgentError` を基底とし、**クラス属性 `exit_code` を持つ**
- 終了コードへの変換は **CLI 層だけ**が行う（品質基準 Q8）。呼び出し側に
  `isinstance` の分岐表を作らないために、終了コードを例外自身へ持たせている

エラー出力の形（詳細設計 17.3）:

    Error: <一行の要約>          <- `message`
      - <詳細>                   <- `details`（0行以上）
    Hint: <対処>                 <- `hint`（省略可）
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import ClassVar


class MediaAgentError(Exception):
    """Media Agent が想定している実行時エラーの基底（終了コード 1）。"""

    #: このエラーで CLI が終了するときの終了コード（詳細設計 17.1）。
    exit_code: ClassVar[int] = 1

    def __init__(
        self,
        message: str,
        *,
        details: Sequence[str] = (),
        hint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details: tuple[str, ...] = tuple(details)
        self.hint = hint


class ProjectNotInitializedError(MediaAgentError):
    """対象ディレクトリが `media-agent init` されていない（終了コード 3）。"""

    exit_code: ClassVar[int] = 3


class ScaffoldError(MediaAgentError):
    """`init` が生成物を用意できなかった（終了コード 1）。"""

    exit_code: ClassVar[int] = 1


class ConfigError(MediaAgentError):
    """設定に関するエラーの基底（終了コード 4）。"""

    exit_code: ClassVar[int] = 4


class ConfigNotFoundError(ConfigError):
    """`config.yaml` が存在しない（詳細設計 5.4 の C-1）。"""


class ConfigParseError(ConfigError):
    """`config.yaml` を YAML として解析できない（詳細設計 5.4 の C-2 / C-3）。"""


class ConfigValidationError(ConfigError):
    """スキーマ検証に失敗した（詳細設計 5.4 の C-4 / C-5 / C-6）。"""


class ConfigVersionError(ConfigError):
    """サポートしていない設定スキーマ版数（詳細設計 5.4 の C-7）。"""


class DatabaseError(MediaAgentError):
    """DB の操作に失敗した（終了コード 1）。"""


class DatabaseVersionError(DatabaseError):
    """DB のスキーマ版数がこのバージョンで扱えない。"""


class AgentError(MediaAgentError):
    """Agent に関するエラーの基底（終了コード 1）。"""


class AgentNotFoundError(AgentError):
    """要求された Agent が Registry に無い。"""


class DuplicateAgentError(AgentError):
    """同じ名前の Agent を二重に登録しようとした。"""


class InvalidAgentError(AgentError):
    """Agent の定義が要件を満たしていない。"""


class AgentExecutionFailedError(AgentError):
    """Agent の実行が失敗した（Task が `failed` で終わった）。"""


class InvalidTaskTransitionError(MediaAgentError):
    """Task の状態遷移表に無い遷移が要求された（詳細設計 9.2）。"""


class PolicyDeniedError(MediaAgentError):
    """Policy により拒否された（終了コード 6）。

    Stage 0 では送出されない（詳細設計 10.6 / 15.4。Action が存在しないため）。
    """

    exit_code: ClassVar[int] = 6


class DoctorCheckFailedError(MediaAgentError):
    """`doctor` の検査に不合格の項目がある（終了コード 5）。"""

    exit_code: ClassVar[int] = 5


class NotImplementedInStageError(MediaAgentError):
    """Stage 0 では未実装のコマンド（スタブコマンド。終了コード 10）。

    **終了コード 0 で終わらせないこと**（方式設計 6.4 / 罠 T-8）。
    """

    exit_code: ClassVar[int] = 10
