"""Exercise the installed MCP server over real stdio, with no vendor calls.

Run with the locked Python environment after terraform init in the repository.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from functools import wraps
from pathlib import Path

from mcp import Client, StdioServerParameters

ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads((ROOT / "backends.json").read_text(encoding="utf-8"))
PROFILES = json.loads((ROOT / "modules/inference/profiles.json").read_text(encoding="utf-8"))["profiles"]
SECRET = "fixture-mcp-unused-credential"


def connected(method):
    @wraps(method)
    async def run(self):
        # AnyIO transports must enter and exit their scope in the same task.
        async with Client(self.parameters, mode=self.mode, read_timeout_seconds=90) as self.client:
            await method(self)
    return run


class MCPTestBase(unittest.IsolatedAsyncioTestCase):
    mode = "auto"
    no_terraform = False
    console_entrypoint = False

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="Tunet MCP with spaces ")
        self.folder = Path(self.temp.name)
        self.assertTrue(self.folder.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.addCleanup(self.temp.cleanup)
        env = {
            "TEMP": str(self.folder), "TMP": str(self.folder),
            "TF_CLI_ARGS": "--an-invalid-flag-that-must-not-be-inherited",
            "TF_CLI_CONFIG_FILE": str(self.folder / "nonexistent-user-config"),
            "TF_LOG": "TRACE", "GOOGLE_APPLICATION_CREDENTIALS": "nonexistent-fixture.json",
            **{profile["api_key_env"]: SECRET for profile in PROFILES.values()},
            "ANTHROPIC_API_KEY": SECRET, "OPENAI_API_KEY": SECRET, "XAI_API_KEY": SECRET,
        }
        if self.no_terraform:
            env["PATH"] = str(self.folder / "no-executables")
        command = sys.executable
        arguments = ["-m", "tunet_agents_mcp"]
        if self.console_entrypoint:
            command = str(Path(sys.executable).parent / ("tunet-agents-mcp.exe" if os.name == "nt" else "tunet-agents-mcp"))
            arguments = []
        self.parameters = StdioServerParameters(command=command, args=arguments, cwd=self.folder, env=env)

    async def call(self, name, arguments=None):
        result = await self.client.call_tool(name, arguments)
        self.assertFalse(result.is_error, str(result.content))
        self.assertNotIn(SECRET, result.model_dump_json())
        return result.structured_content

    def terraform(self, configuration, backend, *, apply=False):
        workspace = self.folder / backend
        workspace.mkdir()
        entry = CATALOG["backends"][backend]
        configuration["module"]["assistant"]["source"] = Path(os.path.relpath(ROOT / entry["module"], workspace)).as_posix()
        (workspace / "main.tf.json").write_text(json.dumps(configuration), encoding="utf-8")
        mirror = (ROOT / ".terraform/providers").as_posix()
        cli = workspace / "offline.tfrc"
        cli.write_text('provider_installation {\n filesystem_mirror {\n path = ' + json.dumps(mirror) + '\n include = ["registry.terraform.io/*/*"]\n }\n}\n', encoding="utf-8")
        sources = {provider["source"].lower() for provider in configuration["terraform"].get("required_providers", {}).values()}
        if sources:
            lock = (ROOT / ".terraform.lock.hcl").read_text(encoding="utf-8")
            lock = "\n\n".join(match.group(0) for match in re.finditer(
                r'provider "registry\.terraform\.io/([^\"]+)" \{.*?^\}', lock, flags=re.DOTALL | re.MULTILINE,
            ) if match.group(1).lower() in sources) + "\n"
            (workspace / ".terraform.lock.hcl").write_text(lock, encoding="utf-8")
        env = {key: value for key, value in os.environ.items() if not key.startswith(("TF_", "GOOGLE_", "AWS_", "AZURE_")) and "KEY" not in key.upper() and "TOKEN" not in key.upper()}
        env.update({"TF_CLI_CONFIG_FILE": str(cli), "TF_INPUT": "0", "TF_IN_AUTOMATION": "1", "CHECKPOINT_DISABLE": "1"})

        def run(*args):
            result = subprocess.run(["terraform", *args], cwd=workspace, env=env, capture_output=True, text=True, encoding="utf-8", timeout=120, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout

        run("init", "-backend=false", "-input=false", "-lockfile=readonly", "-no-color")
        run("validate", "-no-color")
        if apply:
            self.assertFalse(entry["remote_lifecycle"], "Tests must never apply a remote backend")
            run("apply", "-auto-approve", "-input=false", "-no-color")
            return {key: value["value"] for key, value in json.loads(run("output", "-json")).items()}
        return None


class ProtocolTests(MCPTestBase):
    @connected
    async def test_discovery_and_resources(self):
        tools = (await self.client.list_tools()).tools
        self.assertEqual({tool.name for tool in tools}, {"list_backends", "get_backend", "build_inference_agent", "render_terraform_configuration"})
        self.assertTrue(all(tool.annotations.read_only_hint and not tool.annotations.open_world_hint for tool in tools))
        self.assertEqual((await self.call("list_backends"))["backends"], CATALOG["backends"])
        filtered = await self.call("list_backends", {"management": "remote_agent"})
        self.assertEqual(set(filtered["backends"]), {"openai", "anthropic", "mistral"})
        resources = (await self.client.list_resources()).resources
        self.assertEqual({str(resource.uri) for resource in resources}, {"terraform-agents://catalog", "terraform-agents://inference-profiles"})
        content = await self.client.read_resource("terraform-agents://catalog")
        self.assertEqual(json.loads(content.contents[0].text), CATALOG)
        profile_resource = await self.client.read_resource("terraform-agents://inference-profiles")
        self.assertEqual(json.loads(profile_resource.contents[0].text)["profiles"], PROFILES)

    @connected
    async def test_compile_all_inference_backends(self):
        for backend in [*PROFILES, "grok"]:
            with self.subTest(backend=backend):
                options = {"base_url": "https://fixture-workspace.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"} if backend == "qwen" else {}
                result = await self.call("build_inference_agent", {"spec": {
                    "backend": backend, "name": "Caf\u00e9 reviewer", "model": "fixture-" + backend,
                    "instructions": "Review code.", "metadata": {"team": "mcp"}, "options": options,
                }})
                self.assertIsNone(result["agent"]["id"])
                self.assertFalse(result["capabilities"]["remote_lifecycle"])
                self.assertEqual(result["definition"]["instructions"], "Review code.")
                self.assertEqual(result["agent"]["name"], "Caf\u00e9 reviewer")
                self.assertEqual(len(result["fingerprint"]), 64)
                self.assertEqual(len(result["runtime_fingerprint"]), 64)
                if backend == "muse":
                    self.assertEqual(result["agent"]["vendor"], "meta")
                    self.assertEqual(result["runtime"]["path"], "/responses")
                if backend == "cohere":
                    self.assertEqual(json.loads(result["runtime"]["request_template_json"])["messages"][0]["role"], "developer")

    @connected
    async def test_custom_profile_and_literal_inputs(self):
        instructions = '${file("this-file-must-never-be-read")} %{ if true } <>& \u2028'
        spec = {"backend": "custom", "name": "Local Muse", "model": "fixture-glimmer", "instructions": instructions, "custom_profile": {
            "vendor": "meta", "protocol": "chat_completions", "base_url": "http://127.0.0.1:8000/v1",
        }}
        result = await self.call("build_inference_agent", {"spec": spec})
        self.assertEqual(result["definition"]["instructions"], instructions)
        self.assertIsNone(result["runtime"]["api_key_env"])
        self.assertEqual(json.loads(result["runtime"]["request_template_json"])["messages"][0]["content"], instructions)
        spec.pop("custom_profile")
        spec["backend"] = "muse"
        rendered = await self.call("render_terraform_configuration", {"spec": spec})
        applied = await asyncio.to_thread(self.terraform, json.loads(rendered["configuration_json"]), "muse", apply=True)
        self.assertEqual(applied["definition"]["instructions"], instructions)

    @connected
    async def test_errors_and_recovery(self):
        cases = [
            ("get_backend", {"backend": "../../private"}, "Unknown backend"),
            ("build_inference_agent", {"spec": {"backend": "openai", "name": "Agent", "model": "fixture"}}, "remote resources"),
            ("build_inference_agent", {"spec": {"backend": "qwen", "name": "Agent", "model": "fixture"}}, "options.base_url"),
            ("build_inference_agent", {"spec": {"backend": "muse", "name": "Agent", "model": "fixture", "options": {"settings_json": '{"input":"run now"}'}}}, "Terraform rejected"),
            ("build_inference_agent", {"spec": {"backend": "muse", "name": "Agent", "model": "fixture", "api_key": "do-not-accept-this"}}, "validation"),
            ("render_terraform_configuration", {"spec": {"backend": "bedrock", "name": "Agent", "model": "fixture"}}, "external provider coverage"),
            ("render_terraform_configuration", {"spec": {"backend": "gemini", "name": "Agent", "model": "fixture"}}, "options.project"),
        ]
        for tool, arguments, expected in cases:
            with self.subTest(tool=tool, expected=expected):
                result = await self.client.call_tool(tool, arguments)
                self.assertTrue(result.is_error, result)
                self.assertIn(expected, " ".join(content.text for content in result.content))
        self.assertEqual((await self.call("get_backend", {"backend": "muse"}))["profile"]["protocol"], "responses")

    @connected
    async def test_rendered_configurations_validate(self):
        for backend, entry in CATALOG["backends"].items():
            if entry["module"] is None:
                continue
            with self.subTest(backend=backend):
                options = {}
                if backend == "gemini":
                    options = {"project": "fixture-project", "region": "us-central1", "service_account": "agent@fixture-project.iam.gserviceaccount.com"}
                elif backend == "qwen":
                    options = {"base_url": "https://fixture-workspace.ap-southeast-1.maas.aliyuncs.com/compatible-mode/v1"}
                rendered = await self.call("render_terraform_configuration", {"spec": {
                    "backend": backend, "name": "MCP reviewer", "model": "fixture-model", "options": options,
                }})
                self.assertEqual(rendered["remote_lifecycle"], entry["remote_lifecycle"])
                configuration = json.loads(rendered["configuration_json"])
                if backend in ("openai", "mistral"):
                    self.assertTrue(configuration["variable"]["api_key"]["ephemeral"])
                await asyncio.to_thread(self.terraform, configuration, backend)

    @connected
    async def test_concurrent_requests_keep_definitions_separate(self):
        results = await asyncio.gather(*[self.call("build_inference_agent", {"spec": {
            "backend": "muse", "name": f"Muse {index}", "model": f"fixture-{index}",
        }}) for index in range(2)])
        self.assertEqual([result["agent"]["model"] for result in results], ["fixture-0", "fixture-1"])
        self.assertNotEqual(results[0]["fingerprint"], results[1]["fingerprint"])


class LegacyProtocolTests(MCPTestBase):
    mode = "legacy"
    console_entrypoint = True

    @connected
    async def test_legacy_client_can_discover_and_compile(self):
        self.assertEqual(len((await self.client.list_tools()).tools), 4)
        result = await self.call("build_inference_agent", {"spec": {"backend": "muse", "name": "Legacy Muse", "model": "fixture-model"}})
        self.assertEqual(result["agent"]["vendor"], "meta")


class MissingTerraformTests(MCPTestBase):
    no_terraform = True

    @connected
    async def test_catalog_and_rendering_work_without_terraform(self):
        self.assertEqual((await self.call("get_backend", {"backend": "muse"}))["backend"], "muse")
        spec = {"backend": "muse", "name": "Muse", "model": "fixture-model"}
        rendered = await self.call("render_terraform_configuration", {"spec": spec})
        self.assertEqual(rendered["filename"], "main.tf.json")
        result = await self.client.call_tool("build_inference_agent", {"spec": spec})
        self.assertTrue(result.is_error)
        self.assertIn("Terraform 1.10", result.content[0].text)


if __name__ == "__main__":
    if not shutil.which("terraform"):
        raise SystemExit("Terraform must be on PATH for the integration suite.")
    unittest.main(verbosity=2)
