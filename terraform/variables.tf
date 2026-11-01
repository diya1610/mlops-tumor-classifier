variable "subscription_id" {
  description = "Azure subscription to deploy into."
  type        = string
}

variable "github_repository" {
  description = "Repository allowed to deploy, as owner/name."
  type        = string
}

variable "project" {
  description = "Prefix for resource names."
  type        = string
  default     = "mlops"
}

variable "location" {
  description = "Azure region."
  type        = string
  default     = "centralindia"
}

variable "node_count" {
  description = "Number of AKS nodes."
  type        = number
  default     = 1
}

variable "node_vm_size" {
  description = "VM size of the AKS nodes."
  type        = string
  default     = "Standard_B2ms"
}
