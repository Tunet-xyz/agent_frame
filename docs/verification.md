# Verification — v0.3.0, 16 November 2026

Verified locally on Windows with Terraform 1.15.7 and Python 3.13. The locked
providers are Mastercard REST API 2.0.1, Modus Agendi Claude Managed Agents
1.1.0, and the official Google provider 8.11.0. Signed checksums were verified and recorded for Windows amd64 and Linux
amd64; execution was on Windows.

| Check | Result |
| --- | --- |
| `terraform fmt -check -recursive` | Passed |
| `terraform validate` | Passed |
| `terraform test` | 30 passed |
| `python tests/integration.py` | 5 passed |
| `python tests/google_integration.py` | 1 passed |
| `python tests/frontier_integration.py` | 2 passed |
| Ruff check of all three Python integration scripts | Passed |
| Initialize and validate all eight examples: both, openai, anthropic, grok, mistral, gemini, muse, frontier | All passed |
| Local Markdown links and manual-only workflow configuration | Passed |

The integration checks run the installed providers and actual Terraform CLI
against local HTTP contract fixtures. They cover create, in-place update, no-op
plans, individual and complete metadata removal, empty instructions, remote
edits, imports, OpenAI external deletion/recreation, Claude archival reporting,
destroy, permission-error recovery, saved-plan/state credential exclusion,
credential redaction from CLI output, and independent single-vendor credentials.

Mistral checks exercise its PATCH endpoint and empty 204 deletion response. The
Google check uses the real provider's native resource against a local API with
long-running-operation responses and server defaults, including ADK config,
runtime identity, imports, external deletion, drift, and non-authoritative labels.
Grok's provider-free definition applies in the module suite without credentials
or an inference request. Catalogue and new-vendor definition contracts are also
covered.

The frontier checks apply all nine reviewed inference profiles, the dedicated
Muse entry point, and custom Chat Completions/Responses endpoints. They check
native tool schemas and instruction roles, Qwen's required workspace endpoint,
runtime-supplied input, and validation of unsupported profiles, credentials,
conversation state and URL userinfo. Catalogue discovery distinguishes these
definitions from remote resources.

The new CLI suite initializes against an empty provider mirror without a direct
registry fallback. It verifies saved-plan application, no resources in plan or
state, exclusion of unused fake environment credentials, endpoint changes without
a definition fingerprint change, runtime fingerprints, cleared instructions,
model updates, no-op plans and destroy. It makes no inference requests. Source
links and local catalogue paths were checked; the manual-only workflow includes
the new suite and was not dispatched.

Fixtures use fake keys, inherit no vendor credentials, and use a local provider
mirror after initialization. No live vendor agents were created or modified.
Account permissions, model availability, and all vendor-side validation of
nested tool definitions remain unverified against live APIs.

UI testing is not applicable: this repository ships a Terraform module and CLI
examples, with no browser or application UI. The affected CLI flows were tested
with real providers. GitHub Actions was not run; its only trigger is
`workflow_dispatch`, which an agent must never invoke.

## Verified implementation findings

The extension adds portable definitions, a Grok Responses template, a reusable
REST profile, a Mistral adapter, and a capability catalogue. Mistral's stable
common handle leaves version null because the REST provider's computed response
could lag an update. The Google adapter requires min_instances >= 1 because the
pinned provider omitted zero in a create payload, producing a perpetual diff
against the documented server default. Both cases are covered by the completed
checks. Python lint, catalogue paths, documentation links, ADK method data, and
the manual-only workflow check pass. No live vendor account or GitHub Actions
workflow was used.

The v0.3.0 extension adds Meta Muse, DeepSeek, Qwen, Kimi, GLM, MiniMax, Cohere,
NVIDIA and OpenRouter definitions without adding provider dependencies to existing
entry points. Model IDs remain caller-selected. Meta-hosted Muse uses Responses;
existing self-hosted Muse Spark Open/Glimmer servers can use a compatible custom
profile. Those paths configure application artifacts, not cloud deployments.
