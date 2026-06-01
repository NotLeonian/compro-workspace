#!/usr/bin/env -S uv run

import argparse
from dataclasses import dataclass
import datetime as dt
import json
import os
import pathlib
import shutil
import stat
import sys
import textwrap


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


def user_config_dir() -> pathlib.Path:
    """
    oj-prepare が使う online-judge-tools の設定ディレクトリを返す。

    template-generator の実装は appdirs.user_config_dir("online-judge-tools")
    を使っているので、appdirs があればそれに合わせる。
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


def write_executable(path: pathlib.Path, content: str) -> None:
    """
    path のファイルに contest を書き込んだあと、
    実行ファイルとしての権限を与える。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


@dataclass(frozen=True)
class CommandLineArgs:
    workspace_root: pathlib.Path
    no_backup: bool


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

    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="prepare.config.toml や template が既に存在する場合に、それらをバックアップしない。",
    )

    parser.add_argument(
        "backup",
        dest="no_backup",
        action="store_false",
        help="prepare.config.toml や template が既に存在する場合に、それらをバックアップする。",
    )

    args = CommandLineArgs(**vars(parser.parse_args()))

    template_name = "main.cpp"
    mako_in_name = "main.cpp.mako.in"

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

    # 問題を解くワークスペースに problems サブディレクトリを作成
    (workspace_root / "problems").mkdir(parents=True, exist_ok=True)

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
    bridge_template_path = template_dir / template_name

    backup_file(prepare_config_path, no_backup=args.no_backup)
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
        "main.cpp" = {toml_string(template_name)}
        "naive.cpp" = {toml_string(template_name)}
        """
    )

    write_text(prepare_config_path, prepare_config)

    # 5. oj-prepare が使用する adapter を生成
    #
    # adapter 自体は ~/.config に配置するが、C++ テンプレート本体は
    # 問題を解くワークスペースの templates/template.cpp を読む
    mako_in_path = workspace_root / "templates" / mako_in_name
    if not mako_in_path.exists():
        raise SystemExit(f"error: missing template adapter: {mako_in_path}")

    bridge_template = mako_in_path.read_text(encoding="utf-8").replace(
        "__WORKSPACE_ROOT__",
        workspace_root.as_posix(),
    )
    write_text(bridge_template_path, bridge_template)

    print("", file=sys.stderr)
    print("installed runtime workspace:", file=sys.stderr)
    print(f"  workspace_root      = {workspace_root}", file=sys.stderr)
    print(f"  problems            = {workspace_root / 'problems'}", file=sys.stderr)
    print(
        f"  ojp                 = {workspace_root / 'scripts' / 'ojp'}", file=sys.stderr
    )
    print("", file=sys.stderr)
    print("installed oj-prepare configuration:", file=sys.stderr)
    print(f"  prepare.config.toml = {prepare_config_path}", file=sys.stderr)
    print(f"  template adapter    = {bridge_template_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
