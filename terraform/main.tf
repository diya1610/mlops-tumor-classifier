resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

resource "azurerm_resource_group" "main" {
  name     = "${var.project}-rg"
  location = var.location
}

resource "azurerm_container_registry" "main" {
  # Registry names are globally unique and alphanumeric.
  name                = "${var.project}${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
}

resource "azurerm_kubernetes_cluster" "main" {
  name                = "${var.project}-aks"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  dns_prefix          = "${var.project}-${random_string.suffix.result}"
  sku_tier            = "Free"

  default_node_pool {
    name       = "system"
    node_count = var.node_count
    vm_size    = var.node_vm_size
  }

  identity {
    type = "SystemAssigned"
  }
}

resource "azurerm_role_assignment" "aks_pull" {
  scope                            = azurerm_container_registry.main.id
  role_definition_name             = "AcrPull"
  principal_id                     = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
  skip_service_principal_aad_check = true
}

# GitHub Actions signs in with OIDC, so no long-lived Azure credential is stored in GitHub.
resource "azurerm_user_assigned_identity" "github" {
  name                = "${var.project}-github-actions"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
}

resource "azurerm_federated_identity_credential" "github_main" {
  name                = "github-main"
  resource_group_name = azurerm_resource_group.main.name
  parent_id           = azurerm_user_assigned_identity.github.id
  audience            = ["api://AzureADTokenExchange"]
  issuer              = "https://token.actions.githubusercontent.com"
  subject             = "repo:${var.github_repository}:ref:refs/heads/main"
}

resource "azurerm_role_assignment" "github" {
  for_each = {
    reader   = { role = "Reader", scope = azurerm_resource_group.main.id }
    acr_push = { role = "AcrPush", scope = azurerm_container_registry.main.id }
    aks_user = {
      role  = "Azure Kubernetes Service Cluster User Role"
      scope = azurerm_kubernetes_cluster.main.id
    }
  }

  scope                            = each.value.scope
  role_definition_name             = each.value.role
  principal_id                     = azurerm_user_assigned_identity.github.principal_id
  skip_service_principal_aad_check = true
}
