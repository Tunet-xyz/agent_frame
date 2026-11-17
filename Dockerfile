FROM hashicorp/terraform:1.15.7@sha256:40e61a86763083ea987ded0ffa15f6d75e0df48ed16275811f949b3ecbcd8aae AS terraform
FROM ghcr.io/astral-sh/uv:0.6.14@sha256:3362a526af7eca2fcd8604e6a07e873fb6e4286d8837cb753503558ce1213664 AS uv

FROM python:3.13-slim-bookworm@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72 AS build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /build
COPY pyproject.toml uv.lock README.md LICENSE backends.json ./
COPY src/ ./src/
COPY modules/definition/ ./modules/definition/
COPY modules/inference/ ./modules/inference/
COPY modules/grok/ ./modules/grok/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-editable

FROM python:3.13-slim-bookworm@sha256:a5a7017efc5969e00ae2b91c8eb0631049a569652aa4ffc4501769049ae45c72 AS runtime
ARG PACKAGE_VERSION=0.6.1
ARG VCS_REF=working-tree
LABEL org.opencontainers.image.title="AgentFrame MCP" \
      org.opencontainers.image.description="Stdio MCP server with bundled Terraform and agent definitions" \
      org.opencontainers.image.source="https://github.com/Tunet-xyz/agent_frame" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${PACKAGE_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"
COPY --from=build /opt/venv /opt/venv
COPY --from=build /build/LICENSE /usr/share/doc/agentframe/LICENSE.txt
COPY --from=terraform /bin/terraform /usr/local/bin/terraform
COPY --from=terraform /usr/share/doc/terraform/LICENSE.txt /usr/share/doc/terraform/LICENSE.txt
ENV PATH="/opt/venv/bin:${PATH}" HOME=/tmp TMPDIR=/tmp \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 CHECKPOINT_DISABLE=1
USER 10001:10001
WORKDIR /tmp
ENTRYPOINT ["/opt/venv/bin/agent-frame-mcp"]
