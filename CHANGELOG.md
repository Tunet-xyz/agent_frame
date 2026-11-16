# Changelog

## v0.3.0

- Add a Meta Muse entry point for Wonder, Spark and Ember definitions and
  Responses request templates.
- Add one provider-free inference module with reviewed DeepSeek, Qwen, Kimi,
  GLM, MiniMax, Cohere, NVIDIA and OpenRouter profiles alongside Muse.
- Support future compatible APIs, trusted gateways and existing self-hosted
  models through custom Responses or Chat Completions profiles.
- Require Qwen's workspace/region endpoint, preserve native tool formats and
  instruction roles, and keep runtime credentials and input outside Terraform.
- Expand the capability catalogue and examples. Preserve existing remote-agent
  resource addresses and distinguish definitions from remote provisioning.
- Add offline CLI coverage for saved plans, updates, endpoint fingerprints,
  cleared instructions, no-op plans and destroy; keep Actions manual-only.

## v0.2.0

- Add a provider-neutral, schema-versioned agent definition and capability
  catalogue. New backends use independent entry points and the same core handle.
- Add Grok definitions and an initial Responses request template. Runtime input
  and credentials are supplied by the application; its remote agent ID is null.
- Add a reusable REST lifecycle profile and a Mistral saved-agent adapter.
- Add native Gemini ADK configuration deployment with the official Google
  provider, runtime identity, method declarations, label validation, and bounded
  instance settings. The pinned adapter requires a minimum of one instance.
- Record official AWS Bedrock and Azure Foundry Terraform coverage in the
  catalogue, with those external resources distinguished from shipped adapters.
- Preserve the original root selector's OpenAI/Claude resource addresses.
- Add local real-provider lifecycle checks for Mistral and Google, extending
  the manual-only validation workflow.

## v0.1.0

- Add OpenAI and Claude modules with common inputs and handles, usage examples,
  provider research, and local lifecycle verification.
