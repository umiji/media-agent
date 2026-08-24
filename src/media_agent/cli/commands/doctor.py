"""`media-agent doctor`（詳細設計13章）。

`doctor` は **Config の読み込みで例外を送出しない**（罠 D-T15）。設定の不備は検査結果
`fail` として列挙し、終了コード 5 で終わる。**最初の異常で打ち切らない。**

**副作用を持たない**（13.1）。DB を作らず、運用ログのファイルも作らない。
"""

from __future__ import annotations

import click

from media_agent.cli.context import CliContext, pass_cli_context
from media_agent.cli.diagnostics import (
    CHECK_ORDER,
    CheckStatus,
    DiagnosticsReport,
    run_diagnostics,
)
from media_agent.cli.rendering import emit_json
from media_agent.cli.session import setup_cli_logging
from media_agent.errors import DoctorCheckFailedError

#: `[status]` 欄と check id 欄の幅（表示上の見た目。判定対象にしない）。
#: **check id の後ろには必ず空白が入る幅にする。** 詰まると id と message が
#: 1語に見え、id での判定（用語集「check id」）が壊れる。
_STATUS_WIDTH = 10
_CHECK_ID_WIDTH = max(len(check_id) for check_id in CHECK_ORDER) + 2


@click.command("doctor")
@click.option("--json", "json_output", is_flag=True, help="機械可読な JSON で出力する")
@pass_cli_context
def doctor_command(cli_ctx: CliContext, json_output: bool) -> None:
    """設定・構造・依存関係を検証する。"""
    layout = cli_ctx.layout()
    # ファイルハンドラを付けない。ログファイルを作ること自体が副作用になる（13.1）。
    setup_cli_logging(cli_ctx, log_path=None)

    report = run_diagnostics(layout)
    if cli_ctx.wants_json(json_output):
        emit_json(report.as_json())
    else:
        _render_text(report)

    if report.failed:
        # 終了コード 5。**`ConfigError`（4）ではない**（13.4 の意図した非対称）。
        raise DoctorCheckFailedError(
            f"doctor の検査に {report.failed} 件の不合格があります",
            hint="上の [fail] 行の「対処」を確認してください",
        )


def _render_text(report: DiagnosticsReport) -> None:
    """人間向け出力（詳細設計 13.3）。**15項目すべてを1行ずつ出す。**"""
    click.echo(f"Media Agent doctor — {report.project_root}")
    for check in report.checks:
        marker = f"[{check.status.value}]"
        click.echo(
            f"{marker:<{_STATUS_WIDTH}}{check.id:<{_CHECK_ID_WIDTH}}{check.message}"
        )
        if check.status is CheckStatus.fail and check.hint:
            click.echo(f"{'':<{_STATUS_WIDTH}}→ 対処: {check.hint}")
    summary = report.summary
    click.echo(
        f"結果: {summary['ok']} ok / {summary['warn']} warn / "
        f"{summary['skipped']} skipped / {summary['fail']} fail"
    )
