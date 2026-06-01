# compro-workspace
My C++ workspace for competitive programming

## Installation
まず、`libraries/` の中身が空であれば、
```sh
git submodule update --init --recursive
```
を実行する。

このリポジトリのルートディレクトリで、
```sh
git pull
```
と
```sh
git submodule update --recursive
```
を実行してから、
```sh
./scripts/install-workspace.py (問題を解くワークスペースのルートのパス)
```
を実行する。

なお、問題を解くワークスペースとしてこのリポジトリやその他 Git リポジトリの内部は指定できないようになっていることに注意。

> [!NOTE]
> 必須ではないオプションとして `--no-backup` または `--backup` がある。
> これは prepare.config.toml や template が既に存在する場合にそれらをバックアップするかを指定するオプション。

その後、問題を解くワークスペースのルートで `oj-prepare` またはそのラッパー `./scripts/ojp` を実行できる。

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
