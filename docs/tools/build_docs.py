#!/usr/bin/env python3
"""マスタ文書から人間用ビュー（README.md / docs/handbook.md）を生成する。

マスタは `docs/features/` と `docs/guides/` にある。**そこだけが真実である。**
README と handbook は生成物であり、手で書かない。手で書くと必ずマスタと乖離する。

使い方:
    python3 docs/tools/build_docs.py            # 生成する
    python3 docs/tools/build_docs.py --check    # 生成物が最新か検査する（差分があれば終了コード 1）

判断を伴わない機械的な結合・見出し調整・目次生成だけを行う。内容は書き換えない。
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

#: マスタの一覧。**handbook はこの順で全部を載せる。**
MASTERS: list[str] = [
    "docs/features/overview.md",
    "docs/features/stage0-scope.md",
    "docs/guides/install.md",
    "docs/guides/quickstart.md",
    "docs/features/cli.md",
    "docs/features/project-directory.md",
    "docs/guides/verification-stage0.md",
    "docs/guides/development.md",
]

#: README に載せるマスタ。**通し読みで長くなりすぎるものは載せず、リンクだけ張る。**
README_SECTIONS: list[str] = [
    "docs/features/overview.md",
    "docs/features/stage0-scope.md",
    "docs/guides/install.md",
    "docs/guides/quickstart.md",
    "docs/guides/development.md",
]

GENERATED_NOTICE = (
    "<!-- このファイルは自動生成物です。直接編集しないでください。\n"
    "     マスタ: {masters}\n"
    "     生成:   python3 docs/tools/build_docs.py -->"
)

_LINK_RE = re.compile(r"\]\(([^)\s]+)\)")
_FENCE_RE = re.compile(r"^\s*(```|~~~)")


def _slug(text: str) -> str:
    """GitHub 風の見出しアンカーを作る。"""
    text = unicodedata.normalize("NFKC", text).strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return re.sub(r"\s+", "-", text)


def _rewrite_links(body: str, src: str, dst: str) -> str:
    """マスタ内の相対リンクを、出力先から見た相対パスへ直す。"""
    src_dir = posixpath.dirname(src)
    dst_dir = posixpath.dirname(dst)

    def repl(match: re.Match[str]) -> str:
        target = match.group(1)
        if target.startswith(("http://", "https://", "#", "mailto:", "/")):
            return match.group(0)
        anchor = ""
        if "#" in target:
            target, anchor = target.split("#", 1)
            anchor = "#" + anchor
        resolved = posixpath.normpath(posixpath.join(src_dir, target))
        return "](" + posixpath.relpath(resolved, dst_dir or ".") + anchor + ")"

    return _LINK_RE.sub(repl, body)


def _shift_headings(body: str) -> tuple[str, list[str]]:
    """H1 を除いた本文を1段下げ、元の H2 の見出し文字列を返す。"""
    lines = body.splitlines()
    out: list[str] = []
    subsections: list[str] = []
    in_fence = False
    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if not in_fence and line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            title = line.lstrip("#").strip()
            if level == 1:
                continue  # H1 は節見出しとして呼び出し側が作る
            if level == 2:
                subsections.append(title)
            out.append("#" * (level + 1) + " " + title)
            continue
        out.append(line)
    return "\n".join(out).strip("\n"), subsections


def _title_of(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    raise SystemExit("H1 が無いマスタがあります")


def _render(sections: list[str], dst: str, doc_title: str, lead: str) -> str:
    parts: list[str] = [f"# {doc_title}", ""]
    parts.append(GENERATED_NOTICE.format(masters=" / ".join(sections)))
    parts.append("")
    if lead:
        parts.append(lead)
        parts.append("")

    rendered: list[tuple[str, str, list[str]]] = []
    for src in sections:
        raw = (REPO_ROOT / src).read_text(encoding="utf-8")
        title = _title_of(raw)
        body, subs = _shift_headings(_rewrite_links(raw, src, dst))
        rendered.append((title, body, subs))

    parts.append("## 目次")
    parts.append("")
    for title, _body, subs in rendered:
        parts.append(f"- [{title}](#{_slug(title)})")
        for sub in subs:
            parts.append(f"  - [{sub}](#{_slug(sub)})")
    parts.append("")

    for (title, body, _subs), src in zip(rendered, sections, strict=True):
        parts.append("---")
        parts.append("")
        parts.append(f"## {title}")
        parts.append("")
        parts.append(body)
        parts.append("")
        parts.append(f"<sub>出典: [`{src}`]({posixpath.relpath(src, posixpath.dirname(dst) or '.')})</sub>")
        parts.append("")

    parts.append("---")
    parts.append("")
    parts.append("## ドキュメント一覧")
    parts.append("")
    parts.append("| 文書 | 内容 |")
    parts.append("| --- | --- |")
    for src in MASTERS:
        raw = (REPO_ROOT / src).read_text(encoding="utf-8")
        rel = posixpath.relpath(src, posixpath.dirname(dst) or ".")
        parts.append(f"| [`{src}`]({rel}) | {_title_of(raw)} |")
    parts.append("")
    return "\n".join(parts).rstrip("\n") + "\n"


README_LEAD = """**任意のプロジェクトへ導入して使える、AI によるメディア運用 Agent 基盤。**

> **現在の実装状況は Stage 0（Media Agent Core）です。**
> CLI・プロジェクト初期化・設定・DB・Task・Agent Runtime・Policy・ログ／監査記録までが動きます。
> **X への投稿、情報収集、AI によるコンテンツ生成はまだ実装されていません。**
> 外部サービスへ接続しないため、**API キーなどの認証情報は一切必要ありません。**

- 動作を確認したい方 → [Stage 0 動作確認手順書](docs/guides/verification-stage0.md)
- コマンドの詳細 → [CLI リファレンス](docs/features/cli.md)
- 通し読み → [ハンドブック](docs/handbook.md)"""

HANDBOOK_LEAD = """Media Agent の利用者向け文書を 1 つに結合したものです。
個別の文書は `docs/features/` と `docs/guides/` にあります。"""


def build() -> dict[str, str]:
    return {
        "README.md": _render(README_SECTIONS, "README.md", "Media Agent", README_LEAD),
        "docs/handbook.md": _render(
            MASTERS, "docs/handbook.md", "Media Agent ハンドブック", HANDBOOK_LEAD
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="生成せず、最新かどうかだけ検査する"
    )
    args = parser.parse_args()

    stale: list[str] = []
    for rel, content in build().items():
        path = REPO_ROOT / rel
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if args.check:
            if current != content:
                stale.append(rel)
            continue
        if current != content:
            path.write_text(content, encoding="utf-8")
            print(f"updated  {rel}")
        else:
            print(f"ok       {rel}")

    if stale:
        for rel in stale:
            print(f"stale    {rel}", file=sys.stderr)
        print(
            "python3 docs/tools/build_docs.py を実行してください", file=sys.stderr
        )
        return 1
    if args.check:
        print("生成物はマスタと一致しています")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
