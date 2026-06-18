#!/usr/bin/env -S uv run

import argparse
import datetime as dt
from dataclasses import dataclass
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

MAKO_MODULE_START = "<%!"
MAKO_MODULE_END = "\n%>\\"
MAKO_MODULE_END_ALT = "\n%>"


def user_config_dir() -> pathlib.Path:
    try:
        import appdirs
    except ImportError:
        appdirs = None
    if appdirs is not None:
        return pathlib.Path(appdirs.user_config_dir("online-judge-tools"))
    if sys.platform == "darwin":
        return pathlib.Path.home() / "Library" / "Application Support" / "online-judge-tools"
    if os.name == "nt" and os.environ.get("APPDATA"):
        return pathlib.Path(os.environ["APPDATA"]) / "online-judge-tools"
    if os.environ.get("XDG_CONFIG_HOME"):
        return pathlib.Path(os.environ["XDG_CONFIG_HOME"]) / "online-judge-tools"
    return pathlib.Path.home() / ".config" / "online-judge-tools"


def toml_string(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def is_under(path: pathlib.Path, base: pathlib.Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def find_parent_git_dir(path: pathlib.Path) -> pathlib.Path | None:
    path = path.resolve()
    for p in [path, *path.parents]:
        if (p / ".git").exists():
            return p
    return None


def backup_file(path: pathlib.Path, *, no_backup: bool) -> None:
    if no_backup or not path.exists():
        return
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = path.with_name(f"{path.name}.bak.{stamp}")
    shutil.copy2(path, backup_path)
    print(f"backup: {path} -> {backup_path}", file=sys.stderr)


def copy_item(src: pathlib.Path, dst: pathlib.Path) -> None:
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
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"wrote: {path}", file=sys.stderr)


def write_executable(path: pathlib.Path, content: str) -> None:
    write_text(path, content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def split_first_mako_module_block(text: str, *, path: pathlib.Path) -> tuple[str, str]:
    if not text.startswith(MAKO_MODULE_START):
        raise SystemExit(f"error: missing first Mako module block: {path}")
    body_start = len(MAKO_MODULE_START)
    if text.startswith("\r\n", body_start):
        body_start += 2
    elif text.startswith("\n", body_start):
        body_start += 1
    for marker in (MAKO_MODULE_END, MAKO_MODULE_END_ALT):
        body_end = text.find(marker)
        if body_end != -1:
            return text[body_start:body_end], text[body_end + len(marker):]
    raise SystemExit(f"error: missing first Mako module block terminator: {path}")


def read_mako_module_code(path: pathlib.Path) -> str:
    if not path.exists():
        raise SystemExit(f"error: missing template adapter module: {path}")
    text = path.read_text(encoding="utf-8")
    if text.startswith(MAKO_MODULE_START):
        text, _tail = split_first_mako_module_block(text, path=path)
    return text.rstrip() + "\n"


def build_bridge_template(mako_in_path: pathlib.Path, module_path: pathlib.Path) -> str:
    template = mako_in_path.read_text(encoding="utf-8")
    _placeholder, tail = split_first_mako_module_block(template, path=mako_in_path)
    return f"{MAKO_MODULE_START}\n{read_mako_module_code(module_path)}%>\\{tail}"


@dataclass(frozen=True)
class CommandLineArgs:
    workspace_root: pathlib.Path
    no_backup: bool = False


def main() -> None:
    parser = argparse.ArgumentParser(description="Install compro workspace runtime files.")
    parser.add_argument("workspace_root", type=pathlib.Path)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--no-backup", dest="no_backup", action="store_true")
    group.add_argument("--backup", dest="no_backup", action="store_false")
    parser.set_defaults(no_backup=False)
    args = CommandLineArgs(**vars(parser.parse_args()))

    template_name = "main.cpp"
    mako_in_name = "main.cpp.mako.in"
    mako_module_name = f"{mako_in_name}.py"

    source_root = pathlib.Path(__file__).resolve().parents[1]
    workspace_root = args.workspace_root.expanduser().resolve()
    if is_under(workspace_root, source_root):
        raise SystemExit("error: workspace_root must be outside this repository")
    git_root = find_parent_git_dir(workspace_root)
    if git_root is not None:
        raise SystemExit(f"error: workspace_root is under a Git repository: {git_root}")

    workspace_root.mkdir(parents=True, exist_ok=True)
    for name in RUNTIME_ITEMS:
        copy_item(source_root / name, workspace_root / name)
    (workspace_root / "problems").mkdir(parents=True, exist_ok=True)

    write_executable(
        workspace_root / "scripts" / "ojp",
        textwrap.dedent(
            """\
            #!/usr/bin/env bash
            set -euo pipefail
            workspace_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
            cd "$workspace_root"
            uv run oj-prepare "$@"
            """
        ),
    )

    config_dir = user_config_dir()
    template_dir = config_dir / "template"
    prepare_config_path = config_dir / "prepare.config.toml"
    bridge_template_path = template_dir / template_name
    backup_file(prepare_config_path, no_backup=args.no_backup)
    backup_file(bridge_template_path, no_backup=args.no_backup)

    problem_directory = (
        workspace_root / "problems"
    ).as_posix() + "/{service_domain}/{contest_id}/{problem_id}"
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

    mako_in_path = workspace_root / "templates" / mako_in_name
    mako_module_path = workspace_root / "templates" / mako_module_name
    if not mako_in_path.exists():
        raise SystemExit(f"error: missing template adapter: {mako_in_path}")

    bridge_template = build_bridge_template(mako_in_path, mako_module_path).replace(
        "__WORKSPACE_ROOT__",
        workspace_root.as_posix(),
    )
    write_text(bridge_template_path, bridge_template)

    print("", file=sys.stderr)
    print("installed runtime workspace:", file=sys.stderr)
    print(f"  workspace_root      = {workspace_root}", file=sys.stderr)
    print(f"  problems            = {workspace_root / 'problems'}", file=sys.stderr)
    print(f"  ojp                 = {workspace_root / 'scripts' / 'ojp'}", file=sys.stderr)
    print("", file=sys.stderr)
    print("installed oj-prepare configuration:", file=sys.stderr)
    print(f"  prepare.config.toml = {prepare_config_path}", file=sys.stderr)
    print(f"  template adapter    = {bridge_template_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
