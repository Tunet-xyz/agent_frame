"""Export one immutable AgentFrame release into a new Terraform Registry checkout."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {".gitignore", ".terraform.lock.hcl", "LICENSE", "CHANGELOG.md", "backends.json", "main.tf", "outputs.tf", "variables.tf", "versions.tf"}
CLI_TESTS = {"tests/integration.py", "tests/google_integration.py", "tests/frontier_integration.py"}


def included(name: str) -> bool:
    path = Path(name)
    return (
        name in ROOT_FILES or name in CLI_TESTS
        or (name.startswith(("modules/", "examples/")) and path.suffix in {".tf", ".json", ".md"})
        or (name.startswith("docs/") and path.suffix == ".md")
        or (name.startswith("tests/") and (name.endswith(".tftest.hcl") or name.startswith("tests/fixtures/") and path.suffix == ".tf"))
    )


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", *args], cwd=ROOT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", required=True, help="Existing stable source tag, for example v0.6.1.")
    parser.add_argument("--destination", required=True, type=Path, help="A new directory; existing destinations are never overwritten.")
    args = parser.parse_args()
    if not re.fullmatch(r"v\d+\.\d+\.\d+", args.ref):
        parser.error("--ref must be a stable vX.Y.Z tag.")
    if args.destination.exists():
        parser.error("--destination must be a new directory; existing files are never overwritten.")
    revision = git("rev-parse", "--verify", args.ref + "^{commit}").decode().strip()
    files = {}
    project = None
    with tarfile.open(fileobj=io.BytesIO(git("archive", "--format=tar", revision)), mode="r:") as archive:
        for member in archive.getmembers():
            if member.name == "pyproject.toml":
                project = tomllib.loads(archive.extractfile(member).read().decode())["project"]
            if included(member.name) and not member.isdir():
                if not member.isfile() or Path(member.name).is_absolute() or ".." in Path(member.name).parts:
                    raise SystemExit("The selected source contains an unsupported path or file type.")
                files[member.name] = archive.extractfile(member).read()
    if not project or project["version"] != args.ref[1:] or project.get("license") != "MIT":
        raise SystemExit("The source version and MIT license must match the selected release.")
    if not ROOT_FILES.issubset(files) or not files["LICENSE"].startswith(b"MIT License"):
        raise SystemExit("The release is missing required Terraform source or license files.")
    template = (ROOT / "tools/registry/README.md").read_text(encoding="utf-8")
    files["README.md"] = template.replace("{{VERSION}}", project["version"]).replace("{{REVISION}}", revision).encode()
    files[".gitattributes"] = b"* text=auto eol=lf\n"
    files["AGENTS.md"] = (
        b"# AgentFrame Terraform release export\n\n"
        b"This checkout is generated from Tunet-xyz/agent_frame; SOURCE.json records its source and file hashes.\n"
        b"Make implementation changes upstream, then export a new tested release. Preserve unrelated work.\n"
        b"Verify with terraform fmt -check -recursive, terraform init -backend=false -lockfile=readonly,\n"
        b"terraform validate, terraform test, and the three Python CLI integration suites in tests/.\n"
        b"Use local fixtures and fake keys. There is no graphical UI or MCP package in this export.\n"
        b"Never start, rerun or enable GitHub Actions. Keep authentication non-interactive.\n"
    )
    provenance = {
        "schema_version": 1, "upstream": "https://github.com/Tunet-xyz/agent_frame",
        "revision": revision, "tag": args.ref, "version": project["version"], "license": "MIT",
        "registry_address": "Tunet-xyz/agent-frame/restapi",
        "files": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())},
    }
    files["SOURCE.json"] = (json.dumps(provenance, indent=2) + "\n").encode()
    destination = args.destination.resolve()
    destination.mkdir(exist_ok=False)
    for name, data in files.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
    print(f"Exported {len(files)} files from {args.ref} ({revision}) to {destination}")


if __name__ == "__main__":
    main()
