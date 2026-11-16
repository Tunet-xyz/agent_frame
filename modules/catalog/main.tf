terraform {
  required_version = ">= 1.10.0, < 2.0.0"
}

locals {
  catalog = jsondecode(file("${path.module}/../../backends.json"))
}

output "backends" {
  description = "Reviewed capabilities and entry points. A null module means native-provider coverage only, not an adapter shipped here."
  value       = local.catalog.backends
}
output "reviewed_on" {
  value = local.catalog.reviewed_on
}
