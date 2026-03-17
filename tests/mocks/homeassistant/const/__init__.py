from enum import Enum
class Platform(str, Enum):
    BINARY_SENSOR = "binary_sensor"
    SENSOR = "sensor"
    ALARM_CONTROL_PANEL = "alarm_control_panel"
    CAMERA = "camera"

PERCENTAGE = "%"

class UnitOfTemperature:
    CELSIUS = "°C"
    FAHRENHEIT = "°F"
