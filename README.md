# compro-workspace

My C++ workspace for competitive programming

## Installation

まず、uv 0.11.25 以上をインストールする（インストール済みの uv が古い場合はアップグレードする）。

`libraries/` の中身が空であれば、

```sh
git submodule update --init --recursive
```

を実行しておく。

このリポジトリのルートディレクトリで、

```sh
git pull
```

と

```sh
git submodule update --recursive
```

を実行する。

次に、もし `bits/stdc++.h` をプリコンパイルしていなければ

```sh
cd /usr/include/x86_64-linux-gnu/c++/11/bits (などの bits/stdc++.h が存在するディレクトリ)
sudo g++ -O3 -std=gnu++23 stdc++.h
cd (このリポジトリのルートディレクトリ)
```

を実行する（適切にディレクトリ名は読み替えること）。

次に、[libraries/precompile/precompile.hpp](libraries/precompile/precompile.hpp) をプリコンパイルしていない場合と、このリポジトリが ac-library の更新を反映した場合（および、libraries/precompile/precompile.hpp 自体が変更された場合）は

```sh
cd libraries/precompile
sudo g++ -O3 -std=gnu++23 -I ../ac-library ./precompile.hpp
cd ../..
```

を実行する。

そして、

```sh
./scripts/install-workspace.py (問題を解くワークスペースのルートディレクトリのパス)
```

を実行する。
既に存在するディレクトリもまだ存在していないディレクトリも指定できる。

なお、問題を解くワークスペースとしてこのリポジトリやその他 Git リポジトリの内部は指定できないようになっていることに注意。

> [!NOTE]
> 必須ではないオプションとして `--no-backup` または `--backup` がある。  
> これは `.python-version`、prepare.config.toml、template が既に存在する場合にそれらをバックアップするかを指定するオプションである。

> [!NOTE]
> インストーラは CPython 3.11 の仮想環境を uv のキャッシュ内に同期する。  
> 環境本体は uv のキャッシュに保存され、`.venv` は通常、現在選択されている環境へのリンクになる。
>
> 同じ Python インタープリタ用の環境がキャッシュ内に既にある場合、そこへ手動で追加したパッケージは `--inexact` により保持される。  
> 別実装や別バージョンの Python 環境は別々にキャッシュされるため、切り替え直したときに再利用できる。
>
> ただし、`centralized-project-envs` を使わずに実ディレクトリとして作成された `.venv` から初めてキャッシュ内の環境へ移行する場合、その `.venv` に手動で追加していたパッケージは引き継がれない。
>
> なお、インストール後に `uv sync --no-dev --python pypy3.11` を実行することで、PyPy と相性の悪い Mypy などを避けて環境を作成し、キャッシュすることができる。

その後、問題を解くワークスペースのルートで `oj-prepare` またはそのラッパー `./scripts/ojp` を実行できる。

> [!CAUTION]
> [.clang-format](.clang-format) と [libraries/precompile/.clang-format](libraries/precompile/.clang-format) は clang-format 20 で追加されたオプションを使用している。  
> 使用する clang-format のバージョンは 20 以上にすること。

## このリポジトリの更新への追従

同じパスに対して上の Installation を再度行えばよい。
`problems/` 内のファイルが削除されることはない。

ただし、独自に編集していた設定ファイルがあればそれは上書きされることに注意。

## Tips

### 複数のライブラリの相対パスが衝突している場合

Luzhiled's Library と Nyaan's Library の `geometry/` カテゴリ内の一部のファイルなど、そのライブラリのルートディレクトリから見た相対パスが衝突しているファイルがある。

たとえば Nyaan's Library の geometry/circle.hpp を使用したい場合、

```c++
#include "geometry/circle.hpp"
```

とすると、このリポジトリのコンパイルオプションでは Luzhiled's Library が優先されてそちらの geometry/circle.hpp が include されてしまう。

このリポジトリの配置であれば、このような場合も絶対パスを使わずに

```c++
#include "../nyaan/geometry/circle.hpp"
```

のように相対パスの先頭に `../(ei1333|nyaan|suisen)` を追加すればよい。

## 開発者向け

### Python checks

Python ソースコードのフォーマットと静的検査には以下のコマンドを使用できる。

```sh
uv run ruff format .
uv run ruff check .
uv run pyright
uv run mypy .
```
