# インストール

## 前提

| 項目 | 条件 |
| --- | --- |
| Python | **3.11 以上**（3.11 / 3.12 / 3.13 で検証している） |
| Git | リポジトリを取得するために使う |
| ネットワーク | 依存パッケージの取得にのみ使う。**Media Agent 自体は外部サービスへ接続しない** |
| 認証情報 | **不要。** X や LLM の API キーは要らない |

```
$ python3 --version
Python 3.11.15
```

## 取得とインストール

**Media Agent はまだ PyPI へ公開していない**（配布は Stage 8）。ソースから入れる。

```sh
git clone https://github.com/umiji/media-agent.git
cd media-agent

python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

`-e`（editable）はソースを直接参照する開発向けの入れ方である。使うだけなら `-e` と `[dev]` は省いてよい。

```sh
.venv/bin/python -m pip install .
```

## 疎通確認

```sh
.venv/bin/media-agent --version
```

```
media-agent, version 0.1.0
```

以降このドキュメントでは、次のように仮想環境へパスを通した状態で `media-agent` と書く。

```sh
export PATH="$PWD/.venv/bin:$PATH"
```

パスを通さない場合は `.venv/bin/media-agent ...` と書くか、`python -m media_agent ...` を使う。

## 導入先プロジェクトで使う

Media Agent は**導入先のプロジェクトのディレクトリで実行する。** 本体のリポジトリの中で実行するのではない。

```sh
cd ~/my-project
media-agent init
```

別のディレクトリから対象を指定することもできる。

```sh
media-agent -C ~/my-project status
```

## アンインストール

```sh
.venv/bin/python -m pip uninstall media-agent
```

導入先プロジェクトの `.media-agent/` は残る。不要なら手で削除する
（**中の DB とログも消える。** 消す前に中身を確認すること）。
