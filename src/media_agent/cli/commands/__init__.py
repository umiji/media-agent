"""コマンドの登録（1コマンド1モジュール。方式設計 5.1・6.4）。

要件定義書10節の10コマンドを、すべてここで登録する。
Stage 0 で実装しないコマンドは**スタブ**（終了コード 10）として登録する。
沈黙して成功するコマンドを作らない。
"""

from __future__ import annotations

import click

from media_agent.cli.commands.agent import agent_group
from media_agent.cli.commands.doctor import doctor_command
from media_agent.cli.commands.init import init_command
from media_agent.cli.commands.run import run_command
from media_agent.cli.commands.status import status_command
from media_agent.cli.commands.stubs import stub_commands
from media_agent.cli.commands.task import task_group

__all__ = ["register_commands"]


def register_commands(group: click.Group) -> None:
    """要件定義書10節の10コマンドをグループへ登録する。"""
    for command in (
        init_command,
        doctor_command,
        status_command,
        run_command,
        agent_group,
        task_group,
        *stub_commands(),
    ):
        group.add_command(command)
