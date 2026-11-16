# Terraform agents

Manage reusable OpenAI and Claude agents with common Terraform inputs and one
output shape. This private Tunet module reuses existing providers:

| Platform | Implementation | Verified dependency |
| --- | --- | --- |
| OpenAI | Agents API through `Mastercard/restapi` | 2.0.1 |
| Claude | `modus-agendi/anthropic-claude-managed-agents` | 1.1.0 |

OpenAI has an [official Terraform provider](https://developers.openai.com/api/docs/guides/terraform),
but its current resource catalogue covers administration and webhooks rather than
agent definitions. No Anthropic-maintained provider was found in the checked
vendor namespaces. Several community
providers support Claude agents. The dated comparison and selection evidence are
in [docs/provider-research.md](docs/provider-research.md).

## Usage

Terraform 1.10 or later is required. See [examples/both](examples/both/main.tf)
for a complete configuration managing both platforms. Configure providers in the
calling configuration and pass them explicitly:

```hcl
module "assistant" {
  source = "git::https://github.com/Tunet-xyz/terraform-agents.git?ref=v0.1.0"
  providers = {
    restapi = restapi
    claude  = claude
  }

  vendor       = "openai" # or "anthropic"
  name         = "Support assistant"
  model        = var.model
  instructions = "Prepare clear, concise answers for the support team."
  metadata     = { team = "support" }
}
```

The shared selector declares both providers, so Terraform configures both and
needs both credentials even when one vendor is selected. For a configuration
using only one platform, use the vendor entry point. They share the same
`name`, `model`, `instructions`, `metadata`, and `agent` output contract:

| Entry point | Source suffix | Example | Provider required |
| --- | --- | --- | --- |
| Shared selector | repository root | [both](examples/both/main.tf) | `restapi`, `claude` |
| OpenAI only | `//modules/openai?ref=v0.1.0` | [openai](examples/openai/main.tf) | `restapi` |
| Claude only | `//modules/anthropic?ref=v0.1.0` | [anthropic](examples/anthropic/main.tf) | `claude` |

The vendor entry points use `options` for vendor settings; the shared selector
uses `openai` or `anthropic`. Changing `vendor` destroys the old agent and creates
one on the selected platform; it does not transfer sessions or history.

## Credentials

OpenAI needs a project API key with access to the beta Agents API. Configure the
REST provider with `uri = "https://api.openai.com/v1"`,
`write_returns_object = true`, and headers `Authorization = "Bearer ..."` and
`OpenAI-Beta = "agents=v1"`. The examples obtain the key from an ephemeral,
sensitive Terraform input (`TF_VAR_openai_api_key`), which excludes it from saved
plans and state. An OpenAI Admin API key cannot replace the project key.

The Claude provider reads `ANTHROPIC_API_KEY`. Use a workspace-scoped key with
Managed Agents access. This provider's configuration does not expose an explicit
workspace selector; identity-linked keys needing that header are outside this
module's verified scope. The provider supplies the Managed Agents beta header.

Inject credentials into the environment from your normal secret store. Use
non-interactive Git authentication to download this private module. No keys,
state, or variable files belong in the repository. Instructions, tool settings,
and metadata are retained in Terraform state, so protect the state backend.

## Interface

| Input | Type | Default / meaning |
| --- | --- | --- |
| `vendor` | string | Required at the root: `openai` or `anthropic` |
| `name` | string | Required, 1-256 characters |
| `model` | string | Required vendor model ID; availability depends on your account |
| `instructions` | string | `""`; maps to OpenAI `instructions` or Claude `system` |
| `metadata` | map(string) | `{}`; up to 16 pairs, key length 64, value length 512 |
| `openai` / OpenAI `options` | object | `tools_json`, `reasoning_effort`, `service_tier` |
| `anthropic` / Claude `options` | object | `description`, `tools`, `mcp_servers`, `skills`, `multiagent` |

`tools_json` is a JSON array so different OpenAI tool shapes retain their native
types. Claude nested options use the
[community provider's schema](https://registry.terraform.io/providers/modus-agendi/anthropic-claude-managed-agents/1.1.0/docs/resources/agent).
Tool names, permission policies, and MCP/skill formats are platform-specific.
OpenAI appends custom instructions to its base instructions; Claude uses its
system-prompt field. The shared input does not make those behaviors identical.

Every entry point returns `agent`:

```hcl
{
  id       = "agent_..."
  vendor   = "openai" # or "anthropic"
  name     = "Support assistant"
  model    = "..."
  version  = null     # Claude returns its current numeric version
  archived = false
}
```

This module manages saved definitions. It does not start sessions, run prompts,
deploy sandboxes, create scheduled runs, or manage ChatGPT GPTs or Claude Code
subagent files. Runtime workloads consume the agent ID separately.

## Lifecycle and imports

OpenAI uses `POST /v1/agents`, `GET` and `POST /v1/agents/{id}`, then `DELETE`
on destroy. Empty instructions and metadata clear the managed values. Tools are
an explicit list (empty by default); removing reasoning effort resets it to the
model default. Other OpenAI API settings are outside this module's managed scope.

Claude updates the same agent ID and uses its version for optimistic concurrency.
The selected provider sends null entries to remove metadata keys. Empty common
instructions and metadata are translated to null because its schema uses null
for an unset value. Destroy archives the agent through the API. An agent archived
outside Terraform is reported as `agent.archived = true`; it is not silently
recreated. To replace one, review a `terraform apply -replace=ADDRESS` plan.

Import an existing agent into the configured root module named `assistant`:

```shell
terraform import 'module.assistant.module.openai[0].restapi_object.this' '/agents/AGENT_ID'
terraform import 'module.assistant.module.anthropic[0].claude-managed-agents_agent.this' 'AGENT_ID'
```

For the vendor entry points, the addresses are
`module.assistant.restapi_object.this` and
`module.assistant.claude-managed-agents_agent.this`. Review the first plan after
import: applying reconciles the imported agent to the configured values and can
clear existing tools or metadata you have not declared.

## Verification

```shell
terraform init -backend=false -input=false
terraform fmt -check -recursive
terraform validate
terraform test
python tests/integration.py
```

The Python tests use the real, locked providers with local HTTP contract fixtures
and fake keys. After initialization, they install providers from a local mirror
and make no requests to vendor APIs. They exercise the CLI lifecycle, including
errors, imports, empty values, drift, and credential isolation. There is no
application UI, so browser UI testing is not applicable.

Live OpenAI/Claude account verification has not been performed. The fixtures
cannot establish account entitlements, model availability, service-side
validation of every nested tool shape, or beta API compatibility in your account.
The checked-in workflow is manual-only and agents must not start it.
