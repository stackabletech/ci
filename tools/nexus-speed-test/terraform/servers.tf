terraform {
  required_version = ">= 0.15, < 2.0.0"
}

terraform {
  required_providers {
    hcloud = {
      source = "hetznercloud/hcloud"
      version = "1.35.2"
    }
  }
}

variable "hcloud_token" {
  description = "Token to be used with Hetzner cloud"
  type        = string
  sensitive   = true
}

variable "key_id" {
  description = "ID of the public SSH key stored at Hetzner cloud"
  type        = string
  sensitive   = false
}

provider "hcloud" {
  token = var.hcloud_token
}

resource "hcloud_server" "node" {
  count       = 10
  name        = "nexus-speed-test-${count.index}"
  server_type = "cx11"
  image       = "centos-stream-9"
  location    = "hel1"
  ssh_keys    = [ var.key_id ]
}

resource "local_file" "ansible-inventory" {
  filename = "../ansible/inventory/inventory"
  content = templatefile("templates/ansible-inventory.tpl",
    {
      nodes = hcloud_server.node
    }
  )
  file_permission = "0440"
} 
