"""Constants for the Qiara integration."""

DOMAIN = "qiara"
COORDINATOR = "coordinator"

# Configuration
CONF_CUSTOMER_ID = "customer_id"
CONF_SECRET_KEY = "secret_key"
CONF_BASE_URL = "base_url"
DEFAULT_BASE_URL = "https://api.qiara.co/api/v1"

# Sensor types
SENSOR_TYPE_DOOR = "door"
SENSOR_TYPE_WINDOW = "window"
SENSOR_TYPE_MOTION = "motion"
SENSOR_TYPE_SMOKE = "smoke"
SENSOR_TYPE_CO = "co"

# System modes
SYSTEM_MODE_DAY = "day"
SYSTEM_MODE_NIGHT = "night"
SYSTEM_MODE_DISARMED = "off"