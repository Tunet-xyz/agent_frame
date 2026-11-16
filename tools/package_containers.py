"""Build, exercise and export versioned Linux MCP images for release downloads."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import re
import shutil
import subprocess
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architectures", nargs="+", choices=("amd64", "arm64"), default=["amd64", "arm64"])
    parser.add_argument("--no-archive", action="store_true", help="Build and test without saving release downloads.")
    args = parser.parse_args()
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("The package version must be a stable semantic version.")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip():
        revision = "working-tree"
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    checksums = []
    for arch in args.architectures:
        image = f"tunet-agents-mcp:{version}-linux-{arch}"
        run("docker", "buildx", "build", "--quiet", "--platform", "linux/" + arch, "--load", "--provenance=false", "--tag", image,
            "--build-arg", "PACKAGE_VERSION=" + version, "--build-arg", "VCS_REF=" + revision, ".")
        env = {**os.environ, "MCP_CONTAINER_IMAGE": image, "MCP_EXPECTED_VERSION": version}
        run("uv", "run", "--frozen", "python", "tests/container_integration.py", "-f", env=env)
        if args.no_archive:
            continue
        archive = output / f"tunet-agents-mcp_{version}_linux_{arch}.docker.tar.gz"
        with subprocess.Popen(["docker", "save", image], stdout=subprocess.PIPE, cwd=ROOT) as process:
            with archive.open("wb") as destination, gzip.GzipFile(filename="", fileobj=destination, mode="wb", compresslevel=6, mtime=0) as compressed:
                shutil.copyfileobj(process.stdout, compressed)
            if process.wait(timeout=120) != 0:
                raise SystemExit("docker save failed; do not publish the incomplete archive.")
        with archive.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        checksums.append(f"{digest}  {archive.name}\n")
        print(f"Verified release archive: {archive.name}", flush=True)
    if checksums:
        (output / "SHA256SUMS").write_text("".join(checksums), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
