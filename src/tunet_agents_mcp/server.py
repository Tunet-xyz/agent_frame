"""Compatibility imports; the server lives in agent_frame.server."""

from agent_frame.server import (
    backend_catalog,
    build_inference_agent,
    get_backend,
    inference_profiles,
    list_backends,
    main,
    mcp,
    render_terraform_configuration,
)

__all__ = ["backend_catalog", "build_inference_agent", "get_backend", "inference_profiles", "list_backends", "main", "mcp", "render_terraform_configuration"]
