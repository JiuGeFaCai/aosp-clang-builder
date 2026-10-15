#!/usr/bin/env python3
"""Validate and repackage a successful Actions artifact without recompiling LLVM."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

import build as builder


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True)
    parser.add_argument("--work-dir", default=".build")
    parser.add_argument("--output-dir", default="dist")
    parser.add_argument("--source-run-id", required=True)
    args = parser.parse_args()
    archives = list(Path(args.input_dir).resolve().glob("*.tar.xz"))
    if len(archives) != 1:
        raise builder.BuildError("Download exactly one toolchain archive before repackaging.")
    archive = archives[0]
    checksum = archive.with_name(archive.name + ".sha256")
    expected, name = checksum.read_text().strip().split(maxsplit=1)
    if name != archive.name:
        raise builder.BuildError("The checksum record names a different archive.")
    with archive.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise builder.BuildError("Source archive SHA-256 mismatch.")
    work = Path(args.work_dir).resolve()
    unpack = work / "unpack"
    unpack.mkdir(parents=True)
    with tarfile.open(archive) as contents:
        contents.extractall(unpack, filter="data")
    children = list(unpack.iterdir())
    if len(children) != 1 or not children[0].is_dir():
        raise builder.BuildError("Expected one top-level toolchain directory.")
    metadata = json.loads((children[0] / "BUILD_INFO.json").read_text())
    if "verification" not in metadata or metadata["host_architecture"] != builder.native_architecture():
        raise builder.BuildError("Repackage a verified toolchain on a matching native runner.")
    revision, _ = builder.revision_number(metadata["clang_revision"])
    prefix = work / "install" / f"clang-{revision}"
    prefix.parent.mkdir(parents=True)
    children[0].rename(prefix)
    unpack.rmdir()
    metadata["install_prefix"] = str(prefix)
    metadata["repackaged_from"] = {
        "run_id": args.source_run_id, "archive": archive.name, "sha256": actual,
    }
    builder.save_metadata(work, metadata)
    builder.verify(args, work)
    builder.relocation(args, work)
    builder.compatibility(args, work)
    builder.package(args, work)


if __name__ == "__main__":
    try:
        main()
    except (builder.BuildError, subprocess.CalledProcessError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
