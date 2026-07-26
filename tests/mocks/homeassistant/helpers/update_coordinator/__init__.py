from homeassistant.exceptions import UpdateFailed

class DataUpdateCoordinator:
    """Mock coordinator mirroring homeassistant.helpers.update_coordinator.

    `name`, `update_interval` and `config_entry` are keyword-only, matching
    real HA. Real HA falls back to the `current_entry` ContextVar when
    `config_entry` is omitted; integrations should not rely on that, so
    test_coordinator asserts the entry is passed explicitly.
    """

    def __init__(self, hass, logger, *, name, update_interval=None, config_entry=None):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.config_entry = config_entry
        self.data = {}

    def __class_getitem__(cls, item):
        """Support DataUpdateCoordinator[T] subscripting."""
        return cls
    async def _async_update_data(self):
        pass
    @property
    def available(self) -> bool:
        return True

class CoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator
    @property
    def available(self) -> bool:
        return self.coordinator.available
