output "github_variables" {
  description = "Set these as GitHub repository variables to turn on deployment."
  value = {
    AZURE_CLIENT_ID       = azurerm_user_assigned_identity.github.client_id
    AZURE_TENANT_ID       = azurerm_user_assigned_identity.github.tenant_id
    AZURE_SUBSCRIPTION_ID = var.subscription_id
    ACR_NAME              = azurerm_container_registry.main.name
    AKS_NAME              = azurerm_kubernetes_cluster.main.name
    AKS_RESOURCE_GROUP    = azurerm_resource_group.main.name
  }
}
