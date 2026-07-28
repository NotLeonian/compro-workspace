#!/usr/bin/env -S uv run

import argparse
import datetime as dt
import json
import os
import pathlib
import shutil
import stat
import sys
import textwrap
from dataclasses import dataclass

RUNTIME_ITEMS = [
    ".vscode",
    ".clang-format",
    ".clangd",
    ".python-version",
    "compile_flags.txt",
    "pyproject.toml",
    "uv.lock",
    "libraries",
    "templates",
]

MAKO_MODULE_START = "<%!"
MAKO_MODULE_END = "\n%>\\"
MAKO_MODULE_END_WITHOUT_CONTINUATION = "\n%>"


def user_config_dir() -> pathlib.Path:
    """
    oj-prepare が使う online-judge-tools の設定ディレクトリを返す。

    template-generator の実装は
    appdirs.user_config_dir("online-judge-tools") を
    使っているので、appdirs があればそれに合わせる。
    """

    try:
        import appdirs
    except ImportError:
        appdirs = None

    if appdirs is not None:
        return pathlib.Path(appdirs.user_config_dir("online-judge-tools"))

    if sys.platform == "darwin":
        return (
            pathlib.Path.home()
            / "Library"
            / "Application Support"
            / "online-judge-tools"
        )

    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return pathlib.Path(appdata) / "online-judge-tools"

    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home:
        return pathlib.Path(xdg_config_home) / "online-judge-tools"

    return pathlib.Path.home() / ".config" / "online-judge-tools"


def toml_string(s: str) -> str:
    """
    TOML の basic string を返す。
    """

    # TOML の basic string は JSON 文字列とかなり互換性がある
    return json.dumps(s, ensure_ascii=False)


def is_under(path: pathlib.Path, base: pathlib.Path) -> bool:
    """
    path が base の内部にあるかを判定する。
    """

    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def find_parent_git_dir(path: pathlib.Path) -> pathlib.Path | None:
    """
    path やその親に .git があれば、そのディレクトリを返す。
    """

    path = path.resolve()
    for p in [path, *path.parents]:
        if (p / ".git").exists():
            return p
    return None


def backup_file(path: pathlib.Path, *, no_backup: bool) -> None:
    """
    no_backup が false である場合、path のファイルをバックアップする。
    """

    if no_backup or not path.exists():
        return

    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.name}.bak.{stamp}")
    shutil.copy2(path, backup_path)
    print(f"backup: {path} -> {backup_path}", file=sys.stderr)


def copy_item(src: pathlib.Path, dst: pathlib.Path) -> None:
    """
    src から dst にファイルをコピーする。
    """

    if not src.exists():
        raise SystemExit(f"error: missing source item: {src}")

    if src.is_dir():
        shutil.copytree(
            src,
            dst,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(
                ".git",
                ".github",
                ".venv",
                "__pycache__",
                "*.pyc",
                "problems",
                "test",
                "*.out",
                "*.bundle.cpp",
            ),
        )
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    print(f"copied: {src} -> {dst}", file=sys.stderr)


def write_text(path: pathlib.Path, content: str) -> None:
    """
    path のファイルに contest を書き込む。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"wrote: {path}", file=sys.stderr)


def make_executable(path: pathlib.Path) -> None:
    """
    path のファイルに実行権限を与える。
    """

    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def write_executable(path: pathlib.Path, content: str) -> None:
    """
    path のファイルに contest を書き込んだ後に
    実行ファイルとしての権限を与える。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    make_executable(path)


def split_first_mako_module_block(
    text: str,
    *,
    path: pathlib.Path,
) -> tuple[str, str]:
    """
    最初の Mako module block（`<%! ... %>`）の中身と
    それ以降の本文に分ける。

    この関数では最初の `<%! ... %>` だけを扱う。
    後続の `<% ... %>` block は本文として残す。
    """

    if not text.startswith(MAKO_MODULE_START):
        raise SystemExit(f"error: missing first Mako module block: {path}")

    body_start = len(MAKO_MODULE_START)
    if text.startswith("\r\n", body_start):
        body_start += 2
    elif text.startswith("\n", body_start):
        body_start += 1

    for marker in (MAKO_MODULE_END, MAKO_MODULE_END_WITHOUT_CONTINUATION):
        body_end = text.find(marker)
        if body_end != -1:
            return text[body_start:body_end], text[body_end + len(marker) :]

    raise SystemExit(f"error: missing first Mako module block terminator: {path}")


def read_mako_module_code(path: pathlib.Path) -> str:
    """
    main.cpp.mako.in.py から
    最初の `<%! ... %>` に挿入する Python ソースコードを読む。

    main.cpp.mako.in.py は Mako の囲みを含まない
    通常の Python ソースコードであることを仮定する。
    """

    if not path.exists():
        raise SystemExit(f"error: missing template adapter module: {path}")

    return path.read_text(encoding="utf-8").rstrip() + "\n"


def build_bridge_template(mako_in_path: pathlib.Path, module_path: pathlib.Path) -> str:
    """
    main.cpp.mako.in の最初の module block に Python ソースコードを挿入する。
    """

    template = mako_in_path.read_text(encoding="utf-8")
    _placeholder, tail = split_first_mako_module_block(template, path=mako_in_path)
    module_code = read_mako_module_code(module_path)
    return f"{MAKO_MODULE_START}\n{module_code}%>\\{tail}"


DEBUG_BUILD_STAMP_NAMES = [
    ".debug.out.source",
    ".debug.out.source.sha256",
]


def invalidate_debug_build_stamps(problems_root: pathlib.Path) -> None:
    """
    再インストール後の最初のデバッグで
    debug.out を再生成させるため、
    build-debug が生成した stamp を削除する。

    debug.out 自体は削除しない。
    """

    if not problems_root.exists():
        return

    removed = 0

    for stamp_name in DEBUG_BUILD_STAMP_NAMES:
        for path in problems_root.rglob(stamp_name):
            if not path.is_file() and not path.is_symlink():
                continue

            try:
                path.unlink()
            except OSError as e:
                raise SystemExit(
                    f"error: failed to remove debug build stamp: {path}: {e}"
                ) from e

            removed += 1
            print(f"removed debug build stamp: {path}", file=sys.stderr)

    if removed:
        print(
            f"invalidated debug build stamps: {removed} file(s)",
            file=sys.stderr,
        )


@dataclass(frozen=True)
class CommandLineArgs:
    workspace_root: pathlib.Path
    no_backup: bool = False


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "競技プログラミング向けワークスペースと oj-prepare の設定をインストールするスクリプト"
        )
    )

    parser.add_argument(
        "workspace_root",
        type=pathlib.Path,
        help="実際に問題を解くために使うワークスペースのパス",
    )

    group = parser.add_mutually_exclusive_group()

    group.add_argument(
        "--no-backup",
        dest="no_backup",
        action="store_true",
        help="prepare.config.toml や template が既に存在する場合に、それらをバックアップしない。",
    )

    group.add_argument(
        "--backup",
        dest="no_backup",
        action="store_false",
        help="prepare.config.toml や template が既に存在する場合に、それらをバックアップする。",
    )

    parser.set_defaults(no_backup=False)

    args = CommandLineArgs(**vars(parser.parse_args()))

    template_specs = {
        "main.cpp": ("main.cpp.mako.in", "main.cpp.mako.in.py"),
        "gen.py": ("gen.py.mako.in", "gen.py.mako.in.py"),
    }

    source_root = pathlib.Path(__file__).resolve().parents[1]
    workspace_root = args.workspace_root.expanduser().resolve()

    if is_under(workspace_root, source_root):
        raise SystemExit(
            "\n".join(
                [
                    "error:",
                    f"  指定されたパス     = {workspace_root}",
                    f"  リポジトリのルート = {source_root}",
                    "",
                    "問題を解くワークスペースは compro-workspace リポジトリの外部に配置してください。",
                ]
            )
        )

    git_root = find_parent_git_dir(workspace_root)
    if git_root is not None:
        raise SystemExit(
            "\n".join(
                [
                    "error:",
                    f"  指定されたパス           = {workspace_root}",
                    f"  その親リポジトリのルート = {git_root}",
                    "",
                    "問題を解くワークスペースは Git リポジトリの外部に配置すべきです。",
                ]
            )
        )

    # 問題を解くワークスペースのルートディレクトリの作成
    workspace_root.mkdir(parents=True, exist_ok=True)

    # ファイル一式のコピー
    for name in RUNTIME_ITEMS:
        copy_item(source_root / name, workspace_root / name)

    # コピーされたスクリプトへの実行権限の付与
    for relpath in [
        ".vscode/g++-for-oj-bundle",
        ".vscode/compro-shell",
        ".vscode/build-debug",
    ]:
        make_executable(workspace_root / relpath)

    # 問題を解くワークスペースに problems サブディレクトリを作成し、
    # 古い stamp を削除する
    problems_root = workspace_root / "problems"
    problems_root.mkdir(parents=True, exist_ok=True)
    invalidate_debug_build_stamps(problems_root)

    # ojp（oj-prepare のラッパー）の作成
    write_executable(
        workspace_root / "scripts" / "ojp",
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail

            workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
            cd "$workspace_root"

            exec uv run oj-prepare "$@"
            """
        ),
    )

    # online-judge-tools の設定ファイルを作成
    config_dir = user_config_dir()
    template_dir = config_dir / "template"

    prepare_config_path = config_dir / "prepare.config.toml"
    bridge_template_paths = {
        template_name: template_dir / template_name for template_name in template_specs
    }

    backup_file(prepare_config_path, no_backup=args.no_backup)
    for bridge_template_path in bridge_template_paths.values():
        backup_file(bridge_template_path, no_backup=args.no_backup)

    problem_directory = (
        workspace_root / "problems"
    ).as_posix() + "/{service_domain}/{contest_id}/{problem_id}"

    # main.cpp と naive.cpp を同じ内容で生成
    prepare_config = textwrap.dedent(
        f"""\
        contest_directory = "."
        problem_directory = {toml_string(problem_directory)}

        [templates]
        "main.cpp" = {toml_string("main.cpp")}
        "naive.cpp" = {toml_string("main.cpp")}
        "gen.py" = "gen.py"
        """
    )

    write_text(prepare_config_path, prepare_config)

    # 5. oj-prepare が使用する adapter を生成

    # adapter 自体は ~/.config に配置するが、テンプレート本体は
    # 問題を解くワークスペースの templates/ 配下のファイルを読む
    for template_name, (mako_in_name, mako_module_name) in template_specs.items():
        mako_in_path = workspace_root / "templates" / mako_in_name
        mako_module_path = workspace_root / "templates" / mako_module_name
        if not mako_in_path.exists():
            raise SystemExit(f"error: missing template adapter: {mako_in_path}")

        bridge_template = build_bridge_template(mako_in_path, mako_module_path).replace(
            "__WORKSPACE_ROOT__",
            workspace_root.as_posix(),
        )
        write_text(bridge_template_paths[template_name], bridge_template)

    print(file=sys.stderr)
    print("installed runtime workspace:", file=sys.stderr)
    print(f"  workspace_root      = {workspace_root}", file=sys.stderr)
    print(f"  problems            = {workspace_root / 'problems'}", file=sys.stderr)
    print(
        f"  ojp                 = {workspace_root / 'scripts' / 'ojp'}", file=sys.stderr
    )
    print(file=sys.stderr)
    print("installed oj-prepare configuration:", file=sys.stderr)
    print(f"  prepare.config.toml = {prepare_config_path}", file=sys.stderr)
    for template_name, bridge_template_path in bridge_template_paths.items():
        print(f"  template adapter    = {bridge_template_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
