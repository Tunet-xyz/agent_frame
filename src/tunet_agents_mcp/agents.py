"""Catalogue access, configuration generation and isolated Terraform compilation."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from . import __version__


def data_root() -> Path:
    packaged = Path(__file__).resolve().parent / "data"
    if (packaged / "backends.json").is_file():
        return packaged
    return Path(__file__).resolve().parents[2]


def catalog() -> dict:
    return json.loads((data_root() / "backends.json").read_text(encoding="utf-8"))


def profiles() -> dict:
    return json.loads((data_root() / "modules/inference/profiles.json").read_text(encoding="utf-8"))


class CustomProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    vendor: str
    protocol: Literal["responses", "chat_completions"]
    base_url: str
    api_key_env: str | None = None
    instruction_role: Literal["system", "developer"] = "system"


class AgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    backend: str = Field(description="Catalogue key, or custom for a compatible inference endpoint.")
    name: str = Field(min_length=1, max_length=256)
    model: str = Field(min_length=1, description="An account-enabled model ID; no latest alias is assumed.")
    instructions: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)
    options: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Terraform module options. Inference profiles accept tools_json/settings_json strings and base_url/api_key_env. Other backends use native options. Never pass credentials.",
    )
    custom_profile: CustomProfile | None = None

    @field_validator("name", "model")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name and model cannot be blank")
        return value


def backend_details(backend: str) -> dict:
    entries = catalog()["backends"]
    if backend not in entries:
        raise ValueError("Unknown backend. Use list_backends to discover supported names.")
    result = {"backend": backend, **entries[backend]}
    if backend in profiles()["profiles"]:
        result["profile"] = profiles()["profiles"][backend]
    return result


def validate_spec(spec: AgentSpec) -> None:
    if spec.backend != "custom":
        backend_details(spec.backend)
    if (spec.backend == "custom") != (spec.custom_profile is not None):
        raise ValueError("Supply custom_profile exactly when backend is custom.")
    forbidden = {"api_key", "access_token", "authorization", "headers", "credentials"}
    if forbidden.intersection(key.lower() for key in spec.options):
        raise ValueError("Pass credential environment names, not credentials, in module options.")
    if spec.backend in {*profiles()["profiles"], "custom", "grok"}:
        allowed = {"tools_json", "settings_json"}
        if spec.backend != "grok":
            allowed |= {"base_url", "api_key_env"}
        if spec.options.keys() - allowed:
            raise ValueError("Inference options are tools_json, settings_json, base_url and api_key_env; Grok accepts only the JSON options.")


def copy_modules(destination: Path) -> None:
    """Copy a fixed source whitelist, excluding state, caches and other files."""
    for module in ("definition", "inference", "grok"):
        for filename in ("main.tf", "variables.tf"):
            relative = Path("modules") / module / filename
            (destination / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(data_root() / relative, destination / relative)
    relative = Path("modules/inference/profiles.json")
    shutil.copyfile(data_root() / relative, destination / relative)


def compile_inference(spec: AgentSpec) -> dict:
    """Use only the bundled provider-free modules in an isolated temp directory."""
    validate_spec(spec)
    if spec.backend not in {*profiles()["profiles"], "custom", "grok"}:
        raise ValueError("This backend manages remote resources. Use render_terraform_configuration, then review and run Terraform separately.")
    terraform = shutil.which("terraform")
    if terraform is None:
        raise RuntimeError("Terraform 1.10 or later must be on the server's PATH for compilation. Catalogue and rendering tools work without it.")
    with tempfile.TemporaryDirectory(prefix="tunet-agents-mcp-") as folder:
        workspace = Path(folder)
        if not workspace.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError("The compiler workspace is outside the system temporary directory.")
        copy_modules(workspace)
        (workspace / "empty-mirror").mkdir()
        (workspace / "offline.tfrc").write_text(
            'provider_installation {\n  filesystem_mirror {\n    path = "./empty-mirror"\n'
            '    include = ["registry.terraform.io/*/*"]\n  }\n}\n', encoding="utf-8"
        )
        # No vendor credentials, Terraform CLI arguments, logging or cloud settings
        # are inherited. There is no direct provider-registry fallback.
        inherited = {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "HOME", "USERPROFILE", "LANG", "LC_ALL"}
        env = {key: value for key, value in os.environ.items() if key.upper() in inherited}
        env.update({
            "TF_CLI_CONFIG_FILE": str(workspace / "offline.tfrc"),
            "TF_IN_AUTOMATION": "1", "TF_INPUT": "0", "CHECKPOINT_DISABLE": "1",
        })
        arguments = spec.model_dump(exclude={"backend"}, mode="json")
        selected = "grok" if spec.backend == "grok" else "inference"
        module = {"source": "./modules/" + selected, **{
            key: "${var.request." + key + "}" for key in ("name", "model", "instructions", "metadata", "options")
        }}
        if selected == "inference":
            arguments["profile"] = spec.backend
            module.update({"profile": "${var.request.profile}", "custom_profile": "${var.request.custom_profile}"})
        config = {
            "terraform": {"required_version": ">= 1.10.0, < 2.0.0"},
            "variable": {"request": {"type": "any"}}, "module": {"assistant": module},
            "output": {key: {"value": "${module.assistant." + key + "}"} for key in (
                "agent", "definition", "fingerprint", "capabilities", "runtime"
            )},
        }
        config["output"]["runtime_fingerprint"] = {"value": "${sha256(jsonencode(module.assistant.runtime))}"}
        (workspace / "main.tf.json").write_text(json.dumps(config), encoding="utf-8")
        # Values in a JSON variable file remain literal; ${...} is never code.
        (workspace / "request.auto.tfvars.json").write_text(json.dumps({"request": arguments}), encoding="utf-8")

        def run(*args: str) -> str:
            try:
                result = subprocess.run(
                    [terraform, *args], cwd=workspace, env=env, capture_output=True,
                    text=True, encoding="utf-8", timeout=20, check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("Terraform compilation exceeded its 20-second command timeout.") from exc
            if result.returncode != 0:
                # Return variable-validation diagnostics without the process
                # environment, saved plan or Terraform state.
                diagnostics = result.stderr.replace(str(workspace), "<temporary workspace>")
                raise ValueError("Terraform rejected the definition:\n" + diagnostics[:6000])
            return result.stdout

        run("init", "-backend=false", "-input=false", "-no-color")
        run("apply", "-auto-approve", "-input=false", "-no-color")
        output = json.loads(run("output", "-json"))
        return {key: value["value"] for key, value in output.items()}


def literal(value: JsonValue) -> JsonValue:
    """Escape Terraform JSON template sequences in caller-supplied strings."""
    if isinstance(value, str):
        return value.replace("${", "$${").replace("%{", "%%{")
    if isinstance(value, list):
        return [literal(item) for item in value]
    if isinstance(value, dict):
        return {key: literal(item) for key, item in value.items()}
    return value


def render_configuration(spec: AgentSpec) -> dict:
    validate_spec(spec)
    entry = backend_details(spec.backend) if spec.backend != "custom" else {"module": "modules/inference", "remote_lifecycle": False}
    if entry["module"] is None:
        raise ValueError("This catalogue entry has external provider coverage only. Use get_backend for its native resource and documentation.")
    module = {
        "source": f"git::https://github.com/Tunet-xyz/terraform-agents.git//{entry['module']}?ref=v{__version__}",
        **literal(spec.model_dump(include={"name", "model", "instructions", "metadata", "options"}, mode="json")),
    }
    if entry["module"] == "modules/inference":
        module["profile"] = spec.backend
    if spec.custom_profile is not None:
        module["custom_profile"] = literal(spec.custom_profile.model_dump(mode="json"))
    config = {
        "terraform": {"required_version": ">= 1.10.0, < 2.0.0"},
        "module": {"assistant": module},
        "output": {"agent": {"value": "${module.assistant.agent}"}},
    }
    credential_setup = []
    if spec.backend in ("openai", "mistral"):
        config["terraform"]["required_providers"] = {"restapi": {"source": "Mastercard/restapi", "version": "~> 2.0.1"}}
        config["variable"] = {"api_key": {"type": "string", "sensitive": True, "ephemeral": True}}
        headers = {"Authorization": "Bearer ${var.api_key}"}
        if spec.backend == "openai":
            headers["OpenAI-Beta"] = "agents=v1"
        config["provider"] = {"restapi": {
            "uri": "https://api.openai.com/v1" if spec.backend == "openai" else "https://api.mistral.ai/v1",
            "write_returns_object": True, "timeout": 60, "headers": headers,
        }}
        module["providers"] = {"restapi": "restapi"}
        credential_setup = ["Provide TF_VAR_api_key from your secret store when running Terraform."]
    elif spec.backend == "anthropic":
        config["terraform"]["required_providers"] = {"claude": {"source": "modus-agendi/anthropic-claude-managed-agents", "version": "~> 1.1.0"}}
        config["provider"] = {"claude": {}}
        module["providers"] = {"claude": "claude"}
        credential_setup = ["Provide ANTHROPIC_API_KEY from your secret store when running Terraform."]
    elif spec.backend == "gemini":
        if not {"project", "region", "service_account"}.issubset(spec.options):
            raise ValueError("Gemini needs options.project, options.region and options.service_account for an existing runtime identity.")
        config["terraform"]["required_providers"] = {"google": {"source": "hashicorp/google", "version": "~> 8.11.0"}}
        config["provider"] = {"google": {}}
        module["providers"] = {"google": "google"}
        credential_setup = ["Use existing Google ADC or workload identity when running Terraform."]
    if not entry["remote_lifecycle"]:
        config["output"].update({key: {"value": "${module.assistant." + key + "}"} for key in ("definition", "runtime", "capabilities")})
    return {
        "filename": "main.tf.json", "configuration_json": json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        "remote_lifecycle": entry["remote_lifecycle"], "credential_setup": credential_setup,
        "next_step": "Review this configuration, save it in your intended workspace, then run Terraform there. This tool writes no files and runs no deployment.",
    }
