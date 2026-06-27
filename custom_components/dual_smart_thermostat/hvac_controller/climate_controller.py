from datetime import timedelta
import logging
from typing import Callable

from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant, split_entity_id

from ..hvac_controller.generic_controller import GenericHvacController
from ..managers.environment_manager import EnvironmentManager
from ..managers.opening_manager import OpeningManager

_LOGGER = logging.getLogger(__name__)

CLIMATE_DOMAIN = "climate"


class ClimateHvacController(GenericHvacController):
    """HVAC controller for climate-domain actuators (e.g. Midea AC)."""

    _active_modes: tuple[str, ...] = (HVACMode.COOL,)

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id,
        min_cycle_duration: timedelta,
        environment: EnvironmentManager,
        openings: OpeningManager,
        turn_on_callback: Callable,
        turn_off_callback: Callable,
        active_modes: tuple[str, ...] | None = None,
    ) -> None:
        super().__init__(
            hass,
            entity_id,
            min_cycle_duration,
            environment,
            openings,
            turn_on_callback,
            turn_off_callback,
        )
        if active_modes is not None:
            self._active_modes = active_modes

    @property
    def _climate_state(self) -> str | None:
        state = self.hass.states.get(self.entity_id)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        return state.state

    @property
    def is_active(self) -> bool:
        climate_state = self._climate_state
        if climate_state is None:
            return False
        return climate_state in self._active_modes

    @property
    def is_circulating(self) -> bool:
        return self._climate_state == HVACMode.FAN_ONLY

    def ran_long_enough(self) -> bool:
        climate_state = self._climate_state
        if climate_state is None:
            return True
        if climate_state in self._active_modes:
            current_state = climate_state
        else:
            current_state = HVACMode.OFF

        from homeassistant.exceptions import ConditionError
        from homeassistant.helpers import condition
        import homeassistant.util.dt as dt_util

        _LOGGER.debug(
            "Climate controller checking min cycle for %s state %s",
            self.entity_id,
            current_state,
        )
        try:
            return condition.state(
                self.hass,
                self.entity_id,
                current_state,
                self.min_cycle_duration,
            )
        except ConditionError:
            return False


def is_climate_entity(entity_id: str) -> bool:
    """Return True if entity_id belongs to the climate domain."""
    if not entity_id:
        return False
    return split_entity_id(entity_id)[0] == CLIMATE_DOMAIN
