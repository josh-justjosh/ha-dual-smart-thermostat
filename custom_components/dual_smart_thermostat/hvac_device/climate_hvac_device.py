import logging

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class ClimateHvacDeviceMixin:
    """Mixin providing climate service calls for climate-domain actuators."""

    hass: HomeAssistant
    entity_id: str
    _context = None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode on the underlying climate entity."""
        if self.entity_id is None:
            return

        entity_state = self.hass.states.get(self.entity_id)
        if entity_state is None or entity_state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            _LOGGER.debug(
                "Skipping set_hvac_mode for unavailable entity %s", self.entity_id
            )
            return

        if entity_state.state == hvac_mode:
            _LOGGER.debug(
                "%s already in mode %s, skipping service call",
                self.entity_id,
                hvac_mode,
            )
            return

        _LOGGER.info(
            "%s. Setting climate mode %s on %s",
            self.__class__.__name__,
            hvac_mode,
            self.entity_id,
        )
        try:
            await self.hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_HVAC_MODE,
                {ATTR_ENTITY_ID: self.entity_id, "hvac_mode": hvac_mode},
                context=self._context,
                blocking=True,
            )
        except Exception as err:
            _LOGGER.error(
                "Error setting hvac_mode %s on %s: %s",
                hvac_mode,
                self.entity_id,
                err,
            )

    async def async_set_cool_temperature(self) -> None:
        """Set cool mode with the current thermostat target temperature."""
        target_temp = getattr(self.environment, self.target_env_attr)
        if target_temp is None:
            await self.async_set_hvac_mode(HVACMode.COOL)
            return

        entity_state = self.hass.states.get(self.entity_id)
        if entity_state is None or entity_state.state in (
            STATE_UNAVAILABLE,
            STATE_UNKNOWN,
        ):
            _LOGGER.debug(
                "Skipping set_temperature for unavailable entity %s", self.entity_id
            )
            return

        if (
            entity_state.state == HVACMode.COOL
            and entity_state.attributes.get(ATTR_TEMPERATURE) == target_temp
        ):
            _LOGGER.debug(
                "%s already cooling to %s, skipping service call",
                self.entity_id,
                target_temp,
            )
            return

        _LOGGER.info(
            "%s. Setting cool mode at %s on %s",
            self.__class__.__name__,
            target_temp,
            self.entity_id,
        )
        try:
            await self.hass.services.async_call(
                CLIMATE_DOMAIN,
                SERVICE_SET_TEMPERATURE,
                {
                    ATTR_ENTITY_ID: self.entity_id,
                    ATTR_TEMPERATURE: target_temp,
                    "hvac_mode": HVACMode.COOL,
                },
                context=self._context,
                blocking=True,
            )
        except Exception as err:
            _LOGGER.error(
                "Error setting cool temperature on %s: %s", self.entity_id, err
            )

    @property
    def _climate_state(self) -> str | None:
        state = self.hass.states.get(self.entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        return state.state

    @property
    def is_circulating(self) -> bool:
        return self._climate_state == HVACMode.FAN_ONLY

    async def _async_turn_on_entity(self) -> None:
        await self.async_set_cool_temperature()

    async def _async_turn_off_entity(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)
