locals {
  front_door_name = "eligibility-server-${local.env_name}"
}

resource "azurerm_cdn_frontdoor_profile" "main" {
  name                = local.front_door_name
  resource_group_name = data.azurerm_resource_group.main.name
  sku_name            = "Standard_AzureFrontDoor"
}

resource "azurerm_cdn_frontdoor_endpoint" "main" {
  # used in the front door URL
  name                     = "mst-courtesy-cards-eligibility-server-${local.env_name}"
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id
}

resource "azurerm_cdn_frontdoor_origin_group" "main" {
  name                     = local.front_door_name
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id
  session_affinity_enabled = true

  load_balancing {}
}

resource "azurerm_cdn_frontdoor_origin" "main" {
  name                          = local.front_door_name
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.main.id

  enabled                        = true
  host_name                      = azurerm_linux_web_app.main.default_hostname
  http_port                      = 80
  https_port                     = 443
  origin_host_header             = azurerm_linux_web_app.main.default_hostname
  certificate_name_check_enabled = true
  priority                       = 1
  weight                         = 1000
}

resource "azurerm_cdn_frontdoor_route" "main" {
  name                          = local.front_door_name
  cdn_frontdoor_endpoint_id     = azurerm_cdn_frontdoor_endpoint.main.id
  cdn_frontdoor_origin_group_id = azurerm_cdn_frontdoor_origin_group.main.id
  cdn_frontdoor_origin_ids      = [azurerm_cdn_frontdoor_origin.main.id]

  https_redirect_enabled = true
  supported_protocols    = ["Http", "Https"]
  patterns_to_match      = ["/*"]
  forwarding_protocol    = "HttpsOnly"
  link_to_default_domain = true
}

resource "azurerm_cdn_frontdoor_security_policy" "main" {
  name                     = local.front_door_name
  cdn_frontdoor_profile_id = azurerm_cdn_frontdoor_profile.main.id

  security_policies {
    firewall {
      cdn_frontdoor_firewall_policy_id = azurerm_cdn_frontdoor_firewall_policy.main.id
      association {
        patterns_to_match = ["/*"]
        domain {
          cdn_frontdoor_domain_id = azurerm_cdn_frontdoor_endpoint.main.host_name
        }
      }
    }
  }
}

resource "azurerm_cdn_frontdoor_firewall_policy" "main" {
  name                              = "${local.env_name}waf"
  resource_group_name               = data.azurerm_resource_group.main.name
  sku_name                          = azurerm_cdn_frontdoor_profile.main.sku_name
  enabled                           = true
  mode                              = "Prevention"
  custom_block_response_status_code = 403
  custom_block_response_body        = base64encode("Blocked")

  custom_rule {
    name     = "iprestriction${local.env_name}"
    enabled  = true
    type     = "MatchRule"
    priority = 1
    action   = "Block"

    match_condition {
      match_variable     = "SocketAddr"
      operator           = "Contains"
      negation_condition = true
      match_values       = var.IP_ADDRESS_WHITELIST
    }
  }
}
