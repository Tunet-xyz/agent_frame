# Working in this repository

This is a reusable Terraform module, not a custom provider. Preserve the common
inputs and handle while allowing each vendor's documented options.

- Read the parent workspace instructions and preserve other sessions' changes.
- Keep authentication non-interactive. Never log or commit credentials or state.
- Run `terraform fmt -check -recursive`, `terraform init -backend=false`,
  `terraform validate`, `terraform test`, `python tests/integration.py`, and
  `python tests/google_integration.py`.
- The integration tests must use local mock APIs and fake keys. Real vendor
  verification is a separate, explicitly identified check.
- No application UI is shipped; exercise the Terraform CLI flow with real
  providers. If browser work is needed, use a fresh agent-owned isolated browser.
- GitHub Actions must be manual-only (`workflow_dispatch`). Agents must never
  dispatch, rerun, or enable a workflow.
