# Terraform Registry publishing route

Reviewed on 16 November 2026. This repository is a **Terraform module** reusing
existing providers, plus an MCP server. It has no Terraform provider plugin.
The appropriate listing for the current implementation is a module listing.

HashiCorp's [provider publishing guide](https://developer.hashicorp.com/terraform/registry/providers/publishing)
requires an actual provider, a public `terraform-provider-NAME` repository,
provider documentation, release binaries, checksums and signing material.
Registering a publisher account does not turn Terraform module code into a
provider. A custom provider would be a separate implementation and maintenance
commitment; it is not needed to reuse the providers selected here.

## Public module listing

HashiCorp's [module publishing requirements](https://developer.hashicorp.com/terraform/registry/modules/publish)
require a public GitHub repository named `terraform-PROVIDER-NAME`, a description,
standard module structure and semantic version tags. Publishing connects the
publisher's GitHub account to the Registry and authorizes repository webhooks.

Current status:

| Requirement | Status |
| --- | --- |
| Reusable module with root and independent submodules | Present |
| README, examples, declared inputs/outputs and provider dependencies | Present |
| Version tags | Present |
| Public repository | Not met: `Tunet-xyz/terraform-agents` is private |
| Eligible three-part repository name | Not met: `terraform-agents` has two parts |
| Registry GitHub OAuth connection | Not available in this agent session |

A possible public source would be `Tunet-xyz/terraform-restapi-agents`, with
`restapi` identifying the root's main provider and a module address of
`Tunet-xyz/agents/restapi`. The module can still include the other provider
adapters. This name is a proposal, not a reserved or published Registry address.

Before publishing, the owner must choose whether the module source should be
public and choose its license. A dedicated public export can preserve the
existing private repository and its Git URLs, but its documentation and MCP
generated module sources must be updated to point to the public source. The
final public source must be reviewed and tested before Registry publication.
No repository has been renamed, copied publicly or made public by this release.

After those choices, use Upload on the [Terraform Registry](https://registry.terraform.io/)
to connect the owner's GitHub identity, authorize Tunet-xyz access where needed,
and publish the eligible module. Signup and OAuth require the account owner's
authenticated interaction; no browser session or credentials are copied here.

## Private alternative

The [HCP Terraform private module registry](https://developer.hashicorp.com/terraform/cloud-docs/registry/publish-modules)
supports private source repositories. It needs an HCP Terraform organization,
the appropriate registry permissions and a VCS connection. No HCP organization
or authenticated Terraform token is configured in this session, and no relevant
connected Terraform plugin was available when checked.

Existing private Git sources remain usable without a Registry account. Public
module publication or HCP onboarding is pending the owner's choice and account
connection; neither has been represented as complete.
