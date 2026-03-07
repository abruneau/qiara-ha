class HomeAssistantError(Exception): pass
class ConfigEntryAuthFailed(HomeAssistantError): pass
class ConfigEntryNotReady(HomeAssistantError): pass
class UpdateFailed(HomeAssistantError): pass
