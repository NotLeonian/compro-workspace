from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar
from urllib.parse import quote

REPOSITORY = Path(__file__).resolve().parents[1]
LIBRARIES = {
    "ei1333": "https://github.com/ei1333/library",
    "nyaan": "https://github.com/NotLeonian/Nyaan-Library",
    "suisen": "https://github.com/NotLeonian/cp-library-cpp",
    "niche-library": "https://github.com/NotLeonian/NicheLibrary",
}
HEADERS = {
    "ei1333": {
        "geometry/circle.hpp": (
            '#pragma once\n#include "detail/value.hpp"\n'
            "inline constexpr int luzhiled_circle = detail_value;\n"
        ),
        "geometry/detail/value.hpp": "#pragma once\ninline constexpr int detail_value = 1;\n",
        "unused.hpp": "#pragma once\n",
    },
    "nyaan": {
        "geometry/circle.hpp": "#pragma once\ninline constexpr int nyaan_circle = 2;\n",
    },
    "suisen": {
        "library/util/value with space.hpp": (
            "#ifndef SUISEN_VALUE_HPP\n#define SUISEN_VALUE_HPP\n"
            "inline constexpr int suisen_value = 3;\n#endif\n"
        ),
    },
    "niche-library": {
        "value.hpp": (
            '#pragma once\n#include "../suisen/library/util/value with space.hpp"\n'
            "inline constexpr int niche_value = 4;\n"
        ),
    },
}
SOURCE = """#include <bits/stdc++.h>
#include <atcoder/all>
#include "geometry/circle.hpp"
#include "../nyaan/geometry/circle.hpp"
#include "value.hpp"
#include "geometry/circle.hpp"
int main() {
    std::cout << luzhiled_circle + nyaan_circle + suisen_value + niche_value;
}
"""

GENERATE_TEMPLATE = """\
import sys

from onlinejudge_template.generator._main import run
from onlinejudge_template.types import (
    AnalyzerResources, AnalyzerResult, ItemNode, VarDecl, VarName, VarType,
)

analyzed = AnalyzerResult(
    resources=AnalyzerResources(None, None, None, None, None),
    input_format=None,
    input_variables=None,
    output_format=None,
    output_variables=None,
    constants={},
    output_type=None,
    topcoder_class_definition=None,
)
if sys.argv[2] == "input":
    name = VarName("n")
    analyzed = analyzed._replace(
        input_format=ItemNode(name=name),
        input_variables={name: VarDecl(name, VarType.ValueInt, [], [], set())},
    )
sys.stdout.buffer.write(run(analyzed, template_file=sys.argv[1]))
"""


def git(root: Path, *args: str, input_data: bytes | None = None) -> bytes:
    return subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Bundle Test",
            "-c",
            "user.email=bundle-test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        input=input_data,
        capture_output=True,
        check=True,
    ).stdout


def commit_files(root: Path, files: dict[str, str]) -> str:
    # Use Git plumbing so these fixtures never create or change a staging index.
    blobs: dict[str, str] = {}
    for filename, content in files.items():
        path = root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        blobs[filename] = (
            git(root, "hash-object", "-w", "--stdin", input_data=content.encode())
            .decode()
            .strip()
        )

    def make_tree(prefix: str) -> str:
        entries: dict[str, tuple[str, str]] = {}
        for filename, oid in blobs.items():
            if not filename.startswith(prefix):
                continue
            rest = filename[len(prefix) :]
            name, separator, _tail = rest.partition("/")
            if separator:
                if name not in entries:
                    entries[name] = ("040000 tree", make_tree(prefix + name + "/"))
            else:
                entries[name] = ("100644 blob", oid)
        data = b"".join(
            f"{kind} {oid}\t{name}\0".encode()
            for name, (kind, oid) in sorted(entries.items())
        )
        return git(root, "mktree", "-z", input_data=data).decode().strip()

    commit = git(root, "commit-tree", make_tree(""), "-m", "fixture").decode().strip()
    git(root, "update-ref", "HEAD", commit)
    return commit


class BundleTests(unittest.TestCase):
    base_directory: ClassVar[tempfile.TemporaryDirectory[str]]
    base: ClassVar[Path]
    commits: ClassVar[dict[str, str]]

    @classmethod
    def setUpClass(cls) -> None:
        cls.base_directory = tempfile.TemporaryDirectory(prefix="bundle-fixtures-")
        cls.base = Path(cls.base_directory.name)
        (cls.base / ".vscode").mkdir()
        for filename in ("bundle.py", "g++-for-oj-bundle"):
            shutil.copy2(
                REPOSITORY / ".vscode" / filename, cls.base / ".vscode" / filename
            )
        cls.commits = {}
        for name, headers in HEADERS.items():
            root = cls.base / "libraries" / name
            root.mkdir(parents=True)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            cls.commits[name] = commit_files(root, headers)
        acl = cls.base / "libraries/ac-library/atcoder/all"
        acl.parent.mkdir(parents=True)
        acl.write_text("#pragma once\nnamespace atcoder {}\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.base_directory.cleanup()

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="bundle-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "workspace with spaces"
        shutil.copytree(self.base, self.root)
        self.source = self.root / "problems/problem with spaces/main.cpp"
        self.source.parent.mkdir(parents=True)
        self.source.write_text(SOURCE, encoding="utf-8")
        self.output = self.source.with_suffix(".bundle.cpp")
        self.manifest = self.root / "libraries/.bundle-sources.json"

    def run_script(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [sys.executable, str(self.root / ".vscode/bundle.py"), *args],
            cwd=self.root.parent,
            capture_output=True,
            check=False,
        )

    def assert_success(self, result: subprocess.CompletedProcess[bytes]) -> None:
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))

    def export_and_remove_git(self) -> None:
        self.assert_success(self.run_script("--write-manifest", str(self.manifest)))
        for name in LIBRARIES:
            shutil.rmtree(self.root / "libraries" / name / ".git")

    def assert_bundle_error(self, message: str) -> None:
        self.output.write_text("previous output\n", encoding="utf-8")
        result = self.run_script(str(self.source))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(message, result.stderr.decode(errors="replace"))
        self.assertEqual(self.output.read_text(), "previous output\n")
        self.assertEqual(list(self.output.parent.glob("*.tmp")), [])

    def assert_bundle_references(self, *urls: str) -> str:
        self.output.write_text("previous output\n", encoding="utf-8")
        self.assert_success(self.run_script(str(self.source)))
        code = self.output.read_text()
        for url in urls:
            self.assertEqual(code.splitlines().count(f"// {url}"), 1)
        self.assertEqual(list(self.output.parent.glob("*.tmp")), [])
        return code

    def test_git_sources_include_dependencies_and_compile(self) -> None:
        self.assert_success(self.run_script(str(self.source)))
        code = self.output.read_text()
        expected = []
        for name, repository in LIBRARIES.items():
            for filename in sorted(HEADERS[name]):
                if filename == "unused.hpp":
                    continue
                expected.append(
                    f"// {repository}/blob/{self.commits[name]}/{quote(filename, safe='/')}"
                )
        self.assertEqual(
            [line for line in code.splitlines() if line.startswith("// https://")],
            expected,
        )
        self.assertIn("#line ", code)
        self.assertIn("#include <bits/stdc++.h>", code)
        self.assertIn("#include <atcoder/all>", code)
        environment = os.environ.copy()
        environment["CXX"] = str(self.root / ".vscode/g++-for-oj-bundle")
        command = [sys.executable, "-m", "onlinejudge_bundle.main"]
        for name in LIBRARIES:
            command.extend(["-I", str(self.root / "libraries" / name)])
        original = subprocess.check_output(
            [*command, str(self.source)],
            cwd=self.root,
            env=environment,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(self.output.read_bytes().split(b"\n\n", 1)[1], original)
        executable = self.output.parent / "program"
        subprocess.run(
            [
                "g++",
                "-std=gnu++23",
                "-I",
                str(self.root / "libraries/ac-library"),
                str(self.output),
                "-o",
                str(executable),
            ],
            check=True,
            capture_output=True,
        )
        self.assertEqual(subprocess.check_output([str(executable)]), b"10")
        for name in LIBRARIES:
            self.assertFalse((self.root / "libraries" / name / ".git/index").exists())

    def test_manifest_works_without_git(self) -> None:
        self.assert_success(self.run_script(str(self.source)))
        expected = self.output.read_bytes()
        self.export_and_remove_git()
        self.assert_success(self.run_script(str(self.source)))
        self.assertEqual(self.output.read_bytes(), expected)

    def test_manifest_export_does_not_require_site_packages(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-S",
                str(self.root / ".vscode/bundle.py"),
                "--write-manifest",
                str(self.manifest),
            ],
            capture_output=True,
            check=False,
        )
        self.assert_success(result)
        data = json.loads(self.manifest.read_text())
        self.assertEqual(set(data["libraries"]), set(LIBRARIES))

    def use_include_only_header(self) -> str:
        headers = HEADERS["niche-library"] | {
            "umbrella.hpp": '#include "nested.hpp"\n',
            "nested.hpp": '#include "value.hpp"\n',
            "alternative.hpp": HEADERS["niche-library"]["value.hpp"].replace(
                "niche_value = 4", "niche_value = 5"
            ),
        }
        commit = commit_files(self.root / "libraries/niche-library", headers)
        self.source.write_text(
            SOURCE.replace('#include "value.hpp"', '#include "umbrella.hpp"'),
            encoding="utf-8",
        )
        return commit

    def test_include_only_headers_get_urls(self) -> None:
        commit = self.use_include_only_header()
        for installed in (False, True):
            with self.subTest(installed=installed):
                if installed:
                    self.export_and_remove_git()
                self.assert_success(self.run_script(str(self.source)))
                lines = self.output.read_text().splitlines()
                for filename in ("umbrella.hpp", "nested.hpp", "value.hpp"):
                    url = (
                        "// https://github.com/NotLeonian/NicheLibrary/blob/"
                        f"{commit}/{filename}"
                    )
                    self.assertEqual(lines.count(url), 1)

    def test_modified_include_only_header_keeps_original_and_dependency_urls(
        self,
    ) -> None:
        commit = self.use_include_only_header()
        umbrella = self.root / "libraries/niche-library/umbrella.hpp"
        umbrella.write_text('#include "alternative.hpp"\n', encoding="utf-8")
        for installed in (False, True):
            with self.subTest(installed=installed):
                if installed:
                    self.export_and_remove_git()
                code = self.assert_bundle_references(
                    *(
                        f"{LIBRARIES['niche-library']}/blob/{commit}/{name}"
                        for name in ("umbrella.hpp", "alternative.hpp")
                    )
                )
                self.assertIn("niche_value = 5", code)

    def test_untracked_include_only_header_keeps_dependency_urls(self) -> None:
        umbrella = self.root / "libraries/niche-library/umbrella.hpp"
        umbrella.write_text('#include "value.hpp"\n', encoding="utf-8")
        self.source.write_text(
            SOURCE.replace('#include "value.hpp"', '#include "umbrella.hpp"'),
            encoding="utf-8",
        )
        commit = self.commits["niche-library"]
        for installed in (False, True):
            with self.subTest(installed=installed):
                if installed:
                    self.export_and_remove_git()
                code = self.assert_bundle_references(
                    f"{LIBRARIES['niche-library']}/blob/{commit}/value.hpp",
                )
                self.assertNotIn(f"/blob/{commit}/umbrella.hpp", code)
                self.assertNotIn(f"{LIBRARIES['niche-library']}/tree/", code)

    def test_stale_include_only_headers_get_no_urls_but_keep_dependency_urls(
        self,
    ) -> None:
        self.use_include_only_header()
        commit = commit_files(
            self.root / "libraries/niche-library", HEADERS["niche-library"]
        )
        for installed in (False, True):
            with self.subTest(installed=installed):
                if installed:
                    self.export_and_remove_git()
                code = self.assert_bundle_references(
                    f"{LIBRARIES['niche-library']}/blob/{commit}/value.hpp",
                )
                self.assertNotIn(f"{LIBRARIES['niche-library']}/tree/", code)
                for filename in ("umbrella.hpp", "nested.hpp"):
                    self.assertNotIn(f"/blob/{commit}/{filename}", code)

    def test_output_cannot_overwrite_include_only_input(self) -> None:
        self.use_include_only_header()
        umbrella = self.root / "libraries/niche-library/umbrella.hpp"
        original = umbrella.read_bytes()
        result = self.run_script(str(self.source), "-o", str(umbrella))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("output must differ", result.stderr.decode())
        self.assertEqual(umbrella.read_bytes(), original)

    def test_modified_git_header_keeps_original_url(self) -> None:
        path = self.root / "libraries/ei1333/geometry/detail/value.hpp"
        path.write_text("inline constexpr int detail_value = 9;\n", encoding="utf-8")
        code = self.assert_bundle_references(
            f"{LIBRARIES['ei1333']}/blob/{self.commits['ei1333']}/geometry/detail/value.hpp"
        )
        self.assertIn("detail_value = 9", code)

    def test_modified_installed_header_keeps_original_url(self) -> None:
        self.export_and_remove_git()
        path = self.root / "libraries/niche-library/value.hpp"
        path.write_text("inline constexpr int niche_value = 9;\n", encoding="utf-8")
        code = self.assert_bundle_references(
            f"{LIBRARIES['niche-library']}/blob/{self.commits['niche-library']}/value.hpp"
        )
        self.assertIn("niche_value = 9", code)

    def test_manifest_paths_come_from_commit_without_hashing_local_changes(
        self,
    ) -> None:
        path = self.root / "libraries/niche-library/value.hpp"
        path.write_text("inline constexpr int niche_value = 9;\n", encoding="utf-8")
        (path.parent / "untracked.hpp").write_text(
            "// local header\n", encoding="utf-8"
        )
        self.export_and_remove_git()
        data = json.loads(self.manifest.read_text())
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["libraries"]["niche-library"]["files"], ["value.hpp"])
        self.assert_bundle_references(
            f"{LIBRARIES['niche-library']}/blob/{self.commits['niche-library']}/value.hpp"
        )

    def test_legacy_manifest_hashes_do_not_reject_local_changes(self) -> None:
        self.export_and_remove_git()
        data = json.loads(self.manifest.read_text())
        data["version"] = 1
        for name, entry in data["libraries"].items():
            entry["files"] = {
                filename: hashlib.sha256(HEADERS[name][filename].encode()).hexdigest()
                for filename in entry["files"]
            }
        self.manifest.write_text(json.dumps(data), encoding="utf-8")
        path = self.root / "libraries/niche-library/value.hpp"
        path.write_text("inline constexpr int niche_value = 9;\n", encoding="utf-8")
        code = self.assert_bundle_references(
            f"{LIBRARIES['niche-library']}/blob/{self.commits['niche-library']}/value.hpp"
        )
        self.assertIn("niche_value = 9", code)

    def test_unused_changes_do_not_block_bundle(self) -> None:
        path = self.root / "libraries/ei1333/unused.hpp"
        path.write_text("// locally edited but unused\n", encoding="utf-8")
        self.assert_success(self.run_script(str(self.source)))

    def test_missing_header_preserves_output(self) -> None:
        (self.root / "libraries/niche-library/value.hpp").unlink()
        self.assert_bundle_error("oj-bundle failed")

    def test_untracked_header_gets_no_url_but_keeps_existing_urls(self) -> None:
        path = self.root / "libraries/niche-library/untracked.hpp"
        path.write_text(
            "#pragma once\ninline constexpr int untracked_value = 0;\n",
            encoding="utf-8",
        )
        self.source.write_text(SOURCE + '#include "untracked.hpp"\n', encoding="utf-8")
        commit = self.commits["niche-library"]
        for installed in (False, True):
            with self.subTest(installed=installed):
                if installed:
                    self.export_and_remove_git()
                code = self.assert_bundle_references(
                    f"{LIBRARIES['niche-library']}/blob/{commit}/value.hpp",
                )
                self.assertIn("untracked_value = 0", code)
                self.assertNotIn(f"/blob/{commit}/untracked.hpp", code)
                self.assertNotIn(f"{LIBRARIES['niche-library']}/tree/", code)

    def test_untracked_header_without_committed_dependencies_gets_no_urls(self) -> None:
        path = self.root / "libraries/niche-library/untracked.hpp"
        path.write_text("inline constexpr int local_value = 7;\n", encoding="utf-8")
        self.source.write_text(
            '#include "untracked.hpp"\nint main() { return local_value; }\n',
            encoding="utf-8",
        )
        for installed in (False, True):
            with self.subTest(installed=installed):
                if installed:
                    self.export_and_remove_git()
                code = self.assert_bundle_references()
                self.assertIn("local_value = 7", code)
                self.assertNotIn("// Library sources:", code)
                self.assertNotIn("https://github.com/", code)

    def test_stale_header_after_reinstall_gets_no_url(self) -> None:
        commit_files(
            self.root / "libraries/niche-library", {"replacement.hpp": "#pragma once\n"}
        )
        self.export_and_remove_git()
        code = self.assert_bundle_references(
            f"{LIBRARIES['ei1333']}/blob/{self.commits['ei1333']}/geometry/circle.hpp"
        )
        self.assertIn("niche_value = 4", code)
        self.assertNotIn(LIBRARIES["niche-library"], code)

    def test_missing_or_invalid_manifest_preserves_output(self) -> None:
        self.export_and_remove_git()
        for content in (None, "{", '{"version": 2}', '{"version": 1, "libraries": {}}'):
            with self.subTest(content=content):
                if content is None:
                    self.manifest.unlink()
                else:
                    self.manifest.write_text(content, encoding="utf-8")
                self.assert_bundle_error("reinstall the workspace")

    def test_local_headers_do_not_require_manifest(self) -> None:
        self.export_and_remove_git()
        self.manifest.unlink()
        (self.source.parent / "local.hpp").write_text(
            "#pragma once\n", encoding="utf-8"
        )
        self.source.write_text(
            '#include "local.hpp"\nint main() {}\n', encoding="utf-8"
        )
        self.assert_success(self.run_script(str(self.source)))
        self.assertNotIn("// Library sources:", self.output.read_text())

    def test_explicit_output_and_input_protection(self) -> None:
        destination = self.root / "submission.cpp"
        self.assert_success(self.run_script(str(self.source), "-o", str(destination)))
        self.assertTrue(destination.is_file())
        result = self.run_script(str(self.source), "-o", str(self.source))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("output must differ", result.stderr.decode())
        self.assertEqual(self.source.read_text(), SOURCE)
        header = self.root / "libraries/nyaan/geometry/circle.hpp"
        result = self.run_script(str(self.source), "-o", str(header))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(header.read_text(), HEADERS["nyaan"]["geometry/circle.hpp"])

    def prepare_installer(self) -> tuple[Path, dict[str, str], str]:
        scripts = self.root / "scripts"
        scripts.mkdir()
        shutil.copy2(REPOSITORY / "scripts/install-workspace.py", scripts)
        for filename in (
            ".clang-format",
            ".clangd",
            ".python-version",
            "compile_flags.txt",
            "pyproject.toml",
            "uv.lock",
        ):
            shutil.copy2(REPOSITORY / filename, self.root / filename)
        shutil.copytree(REPOSITORY / "templates", self.root / "templates")
        shutil.copytree(REPOSITORY / "typings", self.root / "typings")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        commit = commit_files(
            self.root,
            {"templates/main.cpp": (self.root / "templates/main.cpp").read_text()},
        )
        for filename in ("build-debug", "compro-shell"):
            shutil.copy2(
                REPOSITORY / ".vscode" / filename, self.root / ".vscode" / filename
            )

        destination = self.root.parent / "installed workspace"
        problems = destination / "problems"
        problems.mkdir(parents=True)
        for filename in (".debug.out.source", ".debug.out.source.sha256", "debug.out"):
            (problems / filename).write_text("old build\n", encoding="utf-8")
        commands = self.root.parent / "commands"
        commands.mkdir()
        uv = commands / "uv"
        # This test exercises installation without downloading Python dependencies.
        uv.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        uv.chmod(0o755)
        environment = os.environ.copy()
        environment["PATH"] = str(commands) + os.pathsep + environment["PATH"]
        environment["XDG_CONFIG_HOME"] = str(self.root.parent / "config")
        return destination, environment, commit

    def run_installer(
        self, destination: Path, environment: dict[str, str]
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [
                sys.executable,
                str(self.root / "scripts/install-workspace.py"),
                str(destination),
                "--no-backup",
            ],
            env=environment,
            capture_output=True,
            check=False,
        )

    def test_installer_exports_sources_to_workspace_without_git(self) -> None:
        destination, environment, _commit = self.prepare_installer()
        self.assert_success(self.run_installer(destination, environment))
        self.assertTrue((destination / "libraries/.bundle-sources.json").is_file())
        for stub in (REPOSITORY / "typings").rglob("*.pyi"):
            installed_stub = (
                destination / "typings" / stub.relative_to(REPOSITORY / "typings")
            )
            self.assertEqual(installed_stub.read_bytes(), stub.read_bytes())
        for name in LIBRARIES:
            self.assertFalse((destination / "libraries" / name / ".git").exists())
        problems = destination / "problems"
        self.assertFalse((problems / ".debug.out.source").exists())
        self.assertFalse((problems / ".debug.out.source.sha256").exists())
        self.assertTrue((problems / "debug.out").is_file())
        source = problems / "main.cpp"
        source.write_text(SOURCE, encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(destination / ".vscode/bundle.py"), str(source)],
            capture_output=True,
            check=False,
        )
        self.assert_success(result)
        self.assertIn(
            "// Library sources:", source.with_suffix(".bundle.cpp").read_text()
        )

    def test_generated_templates_pin_commit_and_keep_original_url(self) -> None:
        import tomllib

        destination, environment, commit = self.prepare_installer()
        self.assert_success(self.run_installer(destination, environment))
        self.assertFalse((destination / ".git").exists())
        expected = (
            "// Template source: https://github.com/NotLeonian/compro-workspace/blob/"
            f"{commit}/templates/main.cpp"
        )
        config_dir = Path(environment["XDG_CONFIG_HOME"]) / "online-judge-tools"
        config = tomllib.loads((config_dir / "prepare.config.toml").read_text())

        # A later commit in the source checkout must not affect this installation.
        template = self.root / "templates/main.cpp"
        updated = template.read_text() + "\n// newer template\n"
        new_commit = commit_files(self.root, {"templates/main.cpp": updated})
        self.assertNotEqual(commit, new_commit)

        def generate(filename: str, mode: str) -> subprocess.CompletedProcess[bytes]:
            adapter = config_dir / "template" / config["templates"][filename]
            return subprocess.run(
                [sys.executable, "-c", GENERATE_TEMPLATE, str(adapter), mode],
                env=environment,
                capture_output=True,
                check=False,
            )

        for filename, mode in (("main.cpp", "input"), ("naive.cpp", "fallback")):
            with self.subTest(filename=filename):
                result = generate(filename, mode)
                self.assert_success(result)
                code = result.stdout.decode()
                self.assertTrue(code.startswith(expected + "\n"), code[:200])
                self.assertEqual(code.count(expected), 1)
                if mode == "input":
                    self.assertIn("::in(n);", code)
                else:
                    self.assertIn("failed to analyze input format", code)
                    code += '\n#include "value.hpp"\n'
                source = destination / "problems" / filename
                source.write_text(code, encoding="utf-8")
                bundled = subprocess.run(
                    [
                        sys.executable,
                        str(destination / ".vscode/bundle.py"),
                        str(source),
                    ],
                    capture_output=True,
                    check=False,
                )
                self.assert_success(bundled)
                self.assertEqual(
                    source.with_suffix(".bundle.cpp").read_text().count(expected), 1
                )

        installed = destination / "templates/main.cpp"
        installed.write_text(updated, encoding="utf-8")
        result = generate("main.cpp", "input")
        self.assert_success(result)
        self.assertTrue(result.stdout.decode().startswith(expected + "\n"))
        self.assertIn("// newer template", result.stdout.decode())

        self.assert_success(self.run_installer(destination, environment))
        result = generate("main.cpp", "input")
        self.assert_success(result)
        self.assertIn(f"/blob/{new_commit}/templates/main.cpp", result.stdout.decode())
        self.assertIn("// newer template", result.stdout.decode())

    def test_uncommitted_template_keeps_original_url_when_generating(self) -> None:
        destination, environment, commit = self.prepare_installer()
        template = self.root / "templates/main.cpp"
        template.write_text(
            template.read_text() + "\n// local change\n", encoding="utf-8"
        )
        self.assert_success(self.run_installer(destination, environment))
        adapter = (
            Path(environment["XDG_CONFIG_HOME"])
            / "online-judge-tools/template/main.cpp"
        )
        result = subprocess.run(
            [sys.executable, "-c", GENERATE_TEMPLATE, str(adapter), "fallback"],
            env=environment,
            capture_output=True,
            check=False,
        )
        self.assert_success(result)
        code = result.stdout.decode()
        self.assertIn(f"/blob/{commit}/templates/main.cpp", code)
        self.assertIn("// local change", code)

    def test_installer_requires_template_in_git_commit(self) -> None:
        destination, environment, _commit = self.prepare_installer()
        commit_files(self.root, {"README.md": "fixture without a committed template\n"})
        for missing_git in (False, True):
            with self.subTest(missing_git=missing_git):
                if missing_git:
                    shutil.rmtree(self.root / ".git")
                result = self.run_installer(destination, environment)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    "Git metadata is missing"
                    if missing_git
                    else "cannot read committed templates/main.cpp",
                    result.stderr.decode(),
                )
                self.assertFalse((destination / "templates").exists())

    @unittest.skipUnless(shutil.which("clang-format"), "clang-format is not installed")
    def test_debug_build_in_installed_workspace(self) -> None:
        self.export_and_remove_git()
        shutil.copy2(
            REPOSITORY / ".vscode/build-debug", self.root / ".vscode/build-debug"
        )
        commands = self.root.parent / "commands"
        commands.mkdir()
        uv = commands / "uv"
        # Delegate uv run to this interpreter without synchronizing an environment.
        uv.write_text(
            '#!/bin/sh\n[ "$1" = run ] && [ "$2" = python ] || exit 2\n'
            'shift 2\nexec ' + shlex.quote(sys.executable) + ' "$@"\n',
            encoding="utf-8",
        )
        uv.chmod(0o755)
        environment = os.environ.copy()
        environment["PATH"] = str(commands) + os.pathsep + environment["PATH"]
        command = [
            "bash",
            str(self.root / ".vscode/build-debug"),
            str(self.root),
            str(self.source),
        ]
        result = subprocess.run(
            command, env=environment, capture_output=True, check=False
        )
        self.assert_success(result)
        self.assertEqual(
            subprocess.check_output([str(self.source.parent / "debug.out")]), b"10"
        )
        code = self.output.read_text()
        self.assertIn("// Library sources:", code)
        self.assertNotIn("#line ", code)
        result = subprocess.run(
            command, env=environment, capture_output=True, check=False
        )
        self.assert_success(result)
        self.assertIn("debug.out is up to date", result.stderr.decode())

    @unittest.skipUnless(shutil.which("clang-format"), "clang-format is not installed")
    def test_urls_survive_removing_line_directives_and_formatting(self) -> None:
        self.assert_success(self.run_script(str(self.source)))
        original = self.output.read_text()
        without_directives = "".join(
            line
            for line in original.splitlines(keepends=True)
            if not line.startswith("#line")
        )
        self.output.write_text(without_directives, encoding="utf-8")
        subprocess.run(["clang-format", "-i", str(self.output)], check=True)
        formatted = self.output.read_text()
        for line in original.splitlines():
            if line.startswith("// https://"):
                self.assertIn(line, formatted)


if __name__ == "__main__":
    unittest.main()
