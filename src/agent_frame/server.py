"""Local stdio MCP server. stdout belongs exclusively to the MCP transport."""

from __future__ import annotations

import json
from typing import Literal

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import JsonValue

from . import __version__
from .agents import (
    AgentSpec,
    backend_details,
    catalog,
    compile_inference,
    profiles,
    render_configuration,
)

mcp = MCPServer(
    "agent-frame", title="AgentFrame", version=__version__, log_level="WARNING",
    instructions="Discover agent backends, generate Terraform configuration and compile provider-free definitions. Runtime input and credentials belong to the consuming application. This server does not deploy remote agents or run inference.",
)
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def list_backends(management: Literal["all", "definition", "remote_agent", "cloud_runtime", "cloud_agent"] = "all") -> dict[str, JsonValue]:
    """List reviewed backends, implemented modules, lifecycle capabilities and official documentation."""
    result = catalog()
    result["backends"] = {key: value for key, value in result["backends"].items() if management == "all" or value["management"] == management}
    result["custom_inference_supported"] = True
    return result


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def get_backend(backend: str) -> dict[str, JsonValue]:
    """Look up one catalogue backend and its reviewed inference profile, if available."""
    try:
        return backend_details(backend)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def build_inference_agent(spec: AgentSpec) -> dict[str, JsonValue]:
    """Compile a Grok, frontier or custom definition with the bundled Terraform modules. Requires Terraform on PATH. Returns the common handle, definition, fingerprints, capabilities and runtime request template; no vendor calls or deployment."""
    try:
        return compile_inference(spec)
    except (ValueError, RuntimeError) as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool(annotations=READ_ONLY, structured_output=True)
def render_terraform_configuration(spec: AgentSpec) -> dict[str, JsonValue]:
    """Generate reviewable main.tf.json for any implemented backend, including provider configuration and credential setup instructions. Returns text without writing files, running Terraform or deploying anything."""
    try:
        return render_configuration(spec)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.resource("agent-frame://catalog", mime_type="application/json")
def backend_catalog() -> str:
    """The reviewed capability catalogue, shared with Terraform."""
    return json.dumps(catalog(), ensure_ascii=False, indent=2)


@mcp.resource("agent-frame://inference-profiles", mime_type="application/json")
def inference_profiles() -> str:
    """Reviewed endpoints, protocols, credential environment names and source links."""
    return json.dumps(profiles(), ensure_ascii=False, indent=2)


@mcp.resource("terraform-agents://catalog", mime_type="application/json")
def legacy_backend_catalog() -> str:
    """Deprecated resource alias. Use agent-frame://catalog in new clients."""
    return backend_catalog()


@mcp.resource("terraform-agents://inference-profiles", mime_type="application/json")
def legacy_inference_profiles() -> str:
    """Deprecated resource alias. Use agent-frame://inference-profiles in new clients."""
    return inference_profiles()


def main() -> None:
    mcp.run(transport="stdio")
