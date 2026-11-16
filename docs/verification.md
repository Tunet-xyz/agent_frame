# Verification — 16 November 2026

Verified locally on Windows with Terraform 1.15.7 and Python 3.13. The locked
providers are Mastercard REST API 2.0.1 and Modus Agendi Claude Managed Agents
1.1.0. Signed checksums were verified and recorded for Windows amd64 and Linux
amd64; execution was on Windows.

| Check | Result |
| --- | --- |
| `terraform fmt -check -recursive` | Passed |
| `terraform validate` | Passed |
| `terraform test` | 8 passed |
| `python tests/integration.py` | 4 passed |
| `python -m ruff check tests/integration.py` | Passed |
| Initialize and validate `examples/both`, `examples/openai`, `examples/anthropic` | All passed |
| Local Markdown links and manual-only workflow configuration | Passed |

The integration checks run the installed providers and actual Terraform CLI
against local HTTP contract fixtures. They cover create, in-place update, no-op
plans, individual and complete metadata removal, empty instructions, remote
edits, imports, OpenAI external deletion/recreation, Claude archival reporting,
destroy, permission-error recovery, saved-plan/state credential exclusion,
credential redaction from CLI output, and independent single-vendor credentials.

Fixtures use fake keys, inherit no vendor credentials, and use a local provider
mirror after initialization. No live vendor agents were created or modified.
Account permissions, model availability, and all vendor-side validation of
nested tool definitions remain unverified against live APIs.

UI testing is not applicable: this repository ships a Terraform module and CLI
examples, with no browser or application UI. The affected CLI flows were tested
with real providers. GitHub Actions was not run; its only trigger is
`workflow_dispatch`, which an agent must never invoke.
