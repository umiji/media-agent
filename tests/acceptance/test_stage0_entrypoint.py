"""追加シナリオ: entry point の疎通（subprocess で1本だけ確認する）。

| 項目 | 出所 |
| --- | --- |
| 追加した理由 | 方式設計 10.2「`--version` と `--help` の疎通だけ subprocess で1本確認する」 |
| 検証するもの | `pip install -e .` で生成される console script と `python -m media_agent` の2経路（6.1） |
| なぜインプロセスでは足りないか | entry point が実際に生成されているかは `CliRunner` では検証できない |

S-A〜S-I には含まれないが、Stage 0 の範囲内であり、T-003 の「判断してよい範囲」
（シナリオの追加）に基づいて足した。
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest

from tests.acceptance.expectations import EXIT_OK

pytestmark = pytest.mark.acceptance


def _clean_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("MEDIA_AGENT_PROJECT_DIR", None)
    return env


def test_console_script_reports_the_package_version() -> None:
    """`media-agent --version` が `media_agent.__version__` を表示する（方式設計12章）。"""
    import media_agent

    executable = shutil.which("media-agent")
    assert executable is not None, (
        "console script `media-agent` が見つからない（未インストール）"
    )

    completed = subprocess.run(
        [executable, "--version"],
        capture_output=True,
        text=True,
        env=_clean_env(),
        timeout=60,
        check=False,
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    assert media_agent.__version__ in completed.stdout


def test_module_entrypoint_shows_help() -> None:
    """`python -m media_agent --help` が同じ CLI へ落ちる（方式設計 6.1）。"""
    completed = subprocess.run(
        [sys.executable, "-m", "media_agent", "--help"],
        capture_output=True,
        text=True,
        env=_clean_env(),
        timeout=60,
        check=False,
    )

    assert completed.returncode == EXIT_OK, completed.stderr
    assert "init" in completed.stdout
    assert "doctor" in completed.stdout
