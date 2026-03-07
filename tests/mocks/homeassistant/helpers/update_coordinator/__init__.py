from homeassistant.exceptions import UpdateFailed

class DataUpdateCoordinator:
    def __init__(self, hass, logger, name, update_interval):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.data = {}
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
