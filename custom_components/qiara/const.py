"""Constants for the Qiara integration."""

DOMAIN = "qiara"

# Configuration
CONF_CUSTOMER_ID = "customer_id"
CONF_SECRET_KEY = "secret_key"
CONF_BASE_URL = "base_url"
# The Qiara hub is polled directly on the LAN over HTTPS (self-signed cert).
# The hub runs the lwIP stack and registers the DHCP hostname "lwip", so it is
# usually reachable at lwip.<router-domain> — more stable than its IP across
# DHCP leases. The domain suffix and port vary per network, so this remains an
# editable default users should confirm during setup.
DEFAULT_BASE_URL = "https://lwip.localdomain:64218/api/v1"

# System modes
SYSTEM_MODE_DAY = "day"
SYSTEM_MODE_NIGHT = "night"
SYSTEM_MODE_DISARMED = "off"