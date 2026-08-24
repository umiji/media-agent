"""`media_agent.errors` の単体テスト（詳細設計 17.1）。"""

from __future__ import annotations

import pytest

from media_agent import errors

#: 詳細設計 17.1 の階層表（例外クラス, 終了コード）。
EXIT_CODES: tuple[tuple[type[errors.MediaAgentError], int], ...] = (
    (errors.MediaAgentError, 1),
    (errors.ProjectNotInitializedError, 3),
    (errors.ScaffoldError, 1),
    (errors.ConfigError, 4),
    (errors.ConfigNotFoundError, 4),
    (errors.ConfigParseError, 4),
    (errors.ConfigValidationError, 4),
    (errors.ConfigVersionError, 4),
    (errors.DatabaseError, 1),
    (errors.DatabaseVersionError, 1),
    (errors.AgentError, 1),
    (errors.AgentNotFoundError, 1),
    (errors.DuplicateAgentError, 1),
    (errors.InvalidAgentError, 1),
    (errors.AgentExecutionFailedError, 1),
    (errors.InvalidTaskTransitionError, 1),
    (errors.PolicyDeniedError, 6),
    (errors.DoctorCheckFailedError, 5),
    (errors.NotImplementedInStageError, 10),
)


@pytest.mark.parametrize(("error_class", "exit_code"), EXIT_CODES, ids=lambda v: str(v))
def test_exit_code_matches_the_design_table(
    error_class: type[errors.MediaAgentError], exit_code: int
) -> None:
    """各例外は自分の終了コードをクラス属性として持つ（品質基準 Q8）。"""
    assert error_class.exit_code == exit_code


@pytest.mark.parametrize(("error_class", "_"), EXIT_CODES, ids=lambda v: str(v))
def test_every_error_derives_from_the_base(
    error_class: type[errors.MediaAgentError], _: int
) -> None:
    """すべて `MediaAgentError` を基底とする。"""
    assert issubclass(error_class, errors.MediaAgentError)


def test_config_errors_share_the_config_base() -> None:
    """Config 系は `ConfigError` の派生である（詳細設計 5.4）。"""
    for error_class in (
        errors.ConfigNotFoundError,
        errors.ConfigParseError,
        errors.ConfigValidationError,
        errors.ConfigVersionError,
    ):
        assert issubclass(error_class, errors.ConfigError)


def test_message_details_and_hint_are_kept() -> None:
    """出力の3要素（要約 / 詳細 / Hint）を保持する（詳細設計 17.3）。"""
    error = errors.MediaAgentError("要約", details=["詳細1", "詳細2"], hint="対処")

    assert error.message == "要約"
    assert error.details == ("詳細1", "詳細2")
    assert error.hint == "対処"
    assert str(error) == "要約"


def test_details_default_to_empty() -> None:
    """詳細と Hint は省略できる。"""
    error = errors.MediaAgentError("要約")

    assert error.details == ()
    assert error.hint is None
