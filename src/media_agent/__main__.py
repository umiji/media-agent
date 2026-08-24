"""`python -m media_agent` の入口（方式設計 6.1）。

console script（`media-agent`）と**同じ関数へ落とす**。2経路で挙動が分かれないようにする。
"""

from __future__ import annotations

from media_agent.cli.app import main

if __name__ == "__main__":
    main()
