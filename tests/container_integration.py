"""Exercise a built image over stdio with a read-only root and no network."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import unittest
from pathlib import Path

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
IMAGE = os.environ.get("MCP_CONTAINER_IMAGE", "agent-frame-mcp:0.6.0-linux-amd64")
VERSION = os.environ.get("MCP_EXPECTED_VERSION", "0.6.0")
FLAGS = ["--rm", "--read-only", "--network", "none", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m,mode=1777"]


class ContainerTests(unittest.TestCase):
    def test_image_runtime_and_assets(self):
        script = (
            "import json,os,subprocess; from pathlib import Path; from importlib.metadata import metadata; "
            "from agent_frame import __version__; from agent_frame.agents import data_root; "
            "print(json.dumps({'uid':os.getuid(),'version':__version__,'distribution':metadata('AgentFrame')['Name'],"
            "'terraform':json.loads(subprocess.check_output(['terraform','version','-json']))['terraform_version'],"
            "'assets':sorted(str(p.relative_to(data_root())) for p in data_root().rglob('*') if p.is_file()),"
            "'license':Path('/usr/share/doc/terraform/LICENSE.txt').is_file()}))"
        )
        result = subprocess.run(["docker", "run", *FLAGS, "--entrypoint", "python", IMAGE, "-c", script], capture_output=True, text=True, timeout=90, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["uid"], 10001)
        self.assertEqual(data["version"], VERSION)
        self.assertEqual(data["distribution"], "AgentFrame")
        self.assertEqual(data["terraform"], "1.15.7")
        self.assertTrue(data["license"])
        self.assertEqual(len(data["assets"]), 8)
        self.assertFalse(any("tfstate" in name or "tfvars" in name or ".terraform/" in name for name in data["assets"]))

    def test_stdio_tools_offline(self):
        async def exercise():
            parameters = StdioServerParameters(command="docker", args=["run", "-i", *FLAGS, IMAGE])
            async with Client(parameters, mode="legacy", read_timeout_seconds=120) as client:
                self.assertEqual(client.server_info.name, "agent-frame")
                self.assertEqual(client.server_info.title, "AgentFrame")
                self.assertEqual(len((await client.list_tools()).tools), 4)
                resource = await client.read_resource("agent-frame://catalog")
                catalog = json.loads(resource.contents[0].text)
                self.assertEqual(set(catalog["backends"]), set(json.loads((ROOT / "backends.json").read_text(encoding="utf-8"))["backends"]))
                profiles = json.loads((ROOT / "modules/inference/profiles.json").read_text(encoding="utf-8"))["profiles"]
                for backend in [*profiles, "grok", "custom"]:
                    with self.subTest(backend=backend):
                        spec = {"backend": backend, "name": "Container agent", "model": "fixture-model", "instructions": "Keep ${this} literal."}
                        if backend == "qwen":
                            spec["options"] = {"base_url": "https://fixture.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"}
                        if backend == "custom":
                            spec["custom_profile"] = {"vendor": "meta", "protocol": "chat_completions", "base_url": "http://127.0.0.1:8000/v1"}
                        result = await client.call_tool("build_inference_agent", {"spec": spec})
                        self.assertFalse(result.is_error, result.content)
                        self.assertIsNone(result.structured_content["agent"]["id"])
                        self.assertFalse(result.structured_content["capabilities"]["remote_lifecycle"])
                        self.assertEqual(result.structured_content["definition"]["instructions"], "Keep ${this} literal.")
                invalid = await client.call_tool("get_backend", {"backend": "missing"})
                self.assertTrue(invalid.is_error)
                rendered = await client.call_tool("render_terraform_configuration", {"spec": {"backend": "openai", "name": "Remote agent", "model": "fixture-model"}})
                self.assertFalse(rendered.is_error, rendered.content)
                config = json.loads(rendered.structured_content["configuration_json"])
                self.assertTrue(config["variable"]["api_key"]["ephemeral"])
                self.assertTrue(config["module"]["assistant"]["source"].endswith("?ref=v" + VERSION))
        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main(verbosity=2)
