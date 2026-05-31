# compro-workspace
My C++ workspace for competitive programming

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
