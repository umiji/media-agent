"""Core Layer（要件定義書5節）。

**`cli/` `project/` `agents/` を import しない**（方式設計 5.2）。
Project 固有の事情（プロジェクト配下のパス等）は引数で受け取る（品質基準 Q7）。
パスの組み立ては `project/layout.py` の担当である。
"""
