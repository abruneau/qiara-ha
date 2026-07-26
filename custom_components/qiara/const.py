"""Constants for the Qiara integration."""

DOMAIN = "qiara"

# Configuration
CONF_CUSTOMER_ID = "customer_id"
CONF_SECRET_KEY = "secret_key"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_BASE_URL = "base_url"

# The Qiara hub is polled directly on the LAN over HTTPS (self-signed cert).
# Users enter just the host; the API port (64218) and path (/api/v1) are the
# same across hubs, so the full base URL is derived from the host. The hub runs
# the lwIP stack and registers the DHCP hostname "lwip", so it is usually
# reachable at lwip.<router-domain> — more stable than its IP across leases.
DEFAULT_API_PORT = 64218
API_PATH = "/api/v1"


def build_base_url(host: str, port: int = DEFAULT_API_PORT) -> str:
    """Build the hub's HTTPS API base URL from a host (and optional port)."""
    return f"https://{host.strip()}:{port}{API_PATH}"


# Fallback used only when an entry has no host/base_url (should not happen).
DEFAULT_BASE_URL = build_base_url("lwip.localdomain")

# System modes
SYSTEM_MODE_DAY = "day"
SYSTEM_MODE_NIGHT = "night"
SYSTEM_MODE_DISARMED = "off"