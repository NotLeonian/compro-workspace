import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import quote

LIBRARIES = {
    "ei1333": "https://github.com/ei1333/library",
    "nyaan": "https://github.com/NotLeonian/Nyaan-Library",
    "suisen": "https://github.com/NotLeonian/cp-library-cpp",
    "niche-library": "https://github.com/NotLeonian/NicheLibrary",
}
MANIFEST_PATH = Path("libraries/.bundle-sources.json")


class BundleError(Exception):
    pass


@dataclass(frozen=True)
class Snapshot:
    commit: str
    files: dict[str, str]


def git(root: Path, *args: str, input_data: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        input=input_data,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise BundleError(
            f"cannot read Git sources in {root}: "
            + result.stderr.decode(errors="replace").strip()
        )
    return result.stdout


def git_snapshot(root: Path, paths: set[str] | None = None) -> Snapshot:
    if not (root / ".git").exists():
        raise BundleError(f"Git metadata is missing: {root}; initialize the submodule")
    if (
        Path(
            os.fsdecode(git(root, "rev-parse", "--show-toplevel")).rstrip("\n")
        ).resolve()
        != root
    ):
        raise BundleError(f"expected a separate Git repository: {root}")
    commit = git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise BundleError(f"invalid commit SHA in {root}")

    blobs: dict[str, str] = {}
    for entry in git(root, "ls-tree", "-rz", "--full-tree", commit).split(b"\0"):
        if not entry:
            continue
        metadata, filename = entry.split(b"\t", 1)
        mode, kind, oid_bytes = metadata.split()
        path = os.fsdecode(filename)
        if (
            mode in (b"100644", b"100755")
            and kind == b"blob"
            and (paths is None or path in paths)
        ):
            blobs[path] = oid_bytes.decode()

    hashes: dict[str, str] = {}
    oids = sorted(set(blobs.values()))
    if oids:
        data = git(
            root,
            "cat-file",
            "--batch",
            input_data="".join(oid + "\n" for oid in oids).encode(),
        )
        offset = 0
        for oid in oids:
            end = data.index(b"\n", offset)
            actual_oid, kind, size_text = data[offset:end].split()
            size = int(size_text)
            start = end + 1
            if actual_oid.decode() != oid or kind != b"blob":
                raise BundleError(f"unexpected Git object in {root}: {oid}")
            hashes[oid] = hashlib.sha256(data[start : start + size]).hexdigest()
            offset = start + size + 1
    return Snapshot(commit, {path: hashes[oid] for path, oid in blobs.items()})


def read_manifest(root: Path) -> dict[str, Snapshot]:
    path = root / MANIFEST_PATH
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise BundleError(
            f"cannot read {path}; reinstall the workspace: {error}"
        ) from error
    if not isinstance(data, dict) or data.get("version") != 1:
        raise BundleError(
            f"unsupported source manifest: {path}; reinstall the workspace"
        )
    libraries = data.get("libraries")
    if not isinstance(libraries, dict) or set(libraries) != set(LIBRARIES):
        raise BundleError(f"invalid libraries in {path}; reinstall the workspace")
    snapshots: dict[str, Snapshot] = {}
    for name in LIBRARIES:
        entry = libraries[name]
        if not isinstance(entry, dict):
            raise BundleError(f"invalid sources for {name} in {path}")
        commit = entry.get("commit")
        files = entry.get("files")
        if (
            not isinstance(commit, str)
            or not re.fullmatch(r"[0-9a-f]{40}", commit)
            or not isinstance(files, dict)
        ):
            raise BundleError(f"invalid sources for {name} in {path}")
        checked_files: dict[str, str] = {}
        for filename, digest in files.items():
            if (
                not isinstance(filename, str)
                or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)
            ):
                raise BundleError(f"invalid file hash for {name} in {path}")
            checked_files[filename] = digest
        snapshots[name] = Snapshot(commit, checked_files)
    return snapshots


def atomic_write(path: Path, content: bytes) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False
        ) as output:
            temporary = Path(output.name)
            output.write(content)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def write_manifest(root: Path, destination: Path) -> None:
    snapshots = {
        name: asdict(git_snapshot((root / "libraries" / name).resolve()))
        for name in LIBRARIES
    }
    content = json.dumps(
        {"version": 1, "libraries": snapshots}, indent=2, sort_keys=True
    )
    atomic_write(destination, (content + "\n").encode())


def expand(root: Path, source: Path) -> tuple[bytes, set[Path]]:
    # Manifest export must also work without importing oj-bundle.
    try:
        from onlinejudge_verify.languages.cplusplus_bundle import (
            BundleError as OjBundleError,
        )
        from onlinejudge_verify.languages.cplusplus_bundle import (
            Bundler,
        )
    except ImportError as error:
        raise BundleError(
            "oj-bundle is unavailable; install online-judge-verify-helper"
        ) from error

    paths: set[Path] = set()

    class TrackingBundler(Bundler):
        def update(self, path: Path) -> None:
            paths.add(path.resolve())
            super().update(path)

    bundler = TrackingBundler(
        iquotes=[root, *(root / "libraries" / name for name in LIBRARIES)],
        compiler=str(root / ".vscode/g++-for-oj-bundle"),
    )
    previous_directory = Path.cwd()
    try:
        os.chdir(root)
        bundler.update(source)
    except (OjBundleError, subprocess.CalledProcessError) as error:
        raise BundleError(f"oj-bundle failed: {error}") from error
    finally:
        os.chdir(previous_directory)
    return bundler.get(), paths


def add_sources(root: Path, code: bytes, paths: set[Path]) -> bytes:
    manifest: dict[str, Snapshot] | None = None
    urls: list[str] = []
    for name, repository in LIBRARIES.items():
        library_root = (root / "libraries" / name).resolve()
        used = sorted(
            path.relative_to(library_root).as_posix()
            for path in paths
            if path.is_relative_to(library_root)
        )
        if not used:
            continue
        if (library_root / ".git").exists():
            snapshot = git_snapshot(library_root, set(used))
        else:
            if manifest is None:
                manifest = read_manifest(root)
            snapshot = manifest[name]
        for relative in used:
            expected = snapshot.files.get(relative)
            if expected is None:
                raise BundleError(
                    f"source is absent from commit {snapshot.commit}: {name}/{relative}"
                )
            actual = hashlib.sha256((library_root / relative).read_bytes()).hexdigest()
            if actual != expected:
                raise BundleError(
                    f"source differs from commit {snapshot.commit}: {name}/{relative}; "
                    "restore the published version or publish and install a new commit"
                )
            urls.append(
                f"{repository}/blob/{snapshot.commit}/{quote(relative, safe='/')}"
            )
    if not urls:
        return code
    comments = "// Library sources:\n" + "".join(f"// {url}\n" for url in urls) + "\n"
    return comments.encode() + code


def bundle(root: Path, source: Path, destination: Path) -> None:
    code, paths = expand(root, source)
    if destination in paths or destination == source:
        raise BundleError("output must differ from every input file")
    atomic_write(destination, add_sources(root, code, paths))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bundle C++ with oj-bundle and attach URLs for the four libraries."
    )
    parser.add_argument("source", type=Path, nargs="?")
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument(
        "--write-manifest",
        type=Path,
        help="Export committed sources for the installer.",
    )
    args = parser.parse_args()
    if args.write_manifest is not None:
        if args.source is not None or args.output is not None:
            parser.error("--write-manifest cannot be combined with a source or output")
    elif args.source is None:
        parser.error("a source file is required")

    root = Path(__file__).resolve().parents[1]
    try:
        if args.write_manifest is not None:
            destination = args.write_manifest.expanduser().resolve()
            write_manifest(root, destination)
        else:
            assert args.source is not None
            source = args.source.expanduser().resolve(strict=True)
            destination = (
                args.output.expanduser().resolve()
                if args.output is not None
                else source.with_suffix(".bundle.cpp")
            )
            bundle(root, source, destination)
        print(f"wrote: {destination}", file=sys.stderr)
    except (BundleError, OSError, ValueError) as error:
        print(f"compro-workspace: error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
