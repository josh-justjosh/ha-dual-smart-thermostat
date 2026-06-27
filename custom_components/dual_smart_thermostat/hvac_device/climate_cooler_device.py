import logging

from homeassistant.components.climate import HVACAction, HVACMode
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.helpers.event import async_track_state_change_event

from ..hvac_action_reason.hvac_action_reason import HVACActionReason
from ..hvac_controller.climate_controller import ClimateHvacController
from ..hvac_device.climate_hvac_device import ClimateHvacDeviceMixin
from ..hvac_device.cooler_device import CoolerDevice
from ..managers.environment_manager import EnvironmentManager
from ..managers.feature_manager import FeatureManager
from ..managers.hvac_power_manager import HvacPowerManager
from ..managers.opening_manager import OpeningManager

_LOGGER = logging.getLogger(__name__)


class ClimateCoolerDevice(CoolerDevice, ClimateHvacDeviceMixin):
    """Cooler device that drives a climate entity (e.g. Midea AC) directly."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str,
        min_cycle_duration,
        initial_hvac_mode: HVACMode,
        environment: EnvironmentManager,
        openings: OpeningManager,
        features: FeatureManager,
        hvac_power: HvacPowerManager,
    ) -> None:
        super().__init__(
            hass,
            entity_id,
            min_cycle_duration,
            initial_hvac_mode,
            environment,
            openings,
            features,
            hvac_power,
        )
        self.hvac_controller = ClimateHvacController(
            hass,
            entity_id,
            min_cycle_duration,
            environment,
            openings,
            self.async_turn_on,
            self.async_turn_off,
            active_modes=(HVACMode.COOL,),
        )
        self._fan_hot_tolerance_on = True
        self._fan_on_setpoint_reached_on = True
        self._set_fan_hot_tolerance_on_state()
        self._set_fan_on_setpoint_reached_on_state()

    def _set_fan_hot_tolerance_on_state(self) -> None:
        toggle = self.features.fan_hot_tolerance_on_entity
        if toggle is None:
            self._fan_hot_tolerance_on = True
            return
        if isinstance(toggle, bool):
            self._fan_hot_tolerance_on = toggle
            return
        state = self.hass.states.get(toggle)
        if state is None:
            self._fan_hot_tolerance_on = True
            return
        self._fan_hot_tolerance_on = state.state == STATE_ON

    def _set_fan_on_setpoint_reached_on_state(self) -> None:
        toggle = self.features.fan_on_setpoint_reached_toggle_entity
        if toggle is None:
            self._fan_on_setpoint_reached_on = True
            return
        if isinstance(toggle, bool):
            self._fan_on_setpoint_reached_on = toggle
            return
        state = self.hass.states.get(toggle)
        if state is None:
            self._fan_on_setpoint_reached_on = True
            return
        self._fan_on_setpoint_reached_on = state.state == STATE_ON

    async def async_on_startup(self, async_write_ha_state_cb=None) -> None:
        await super().async_on_startup(async_write_ha_state_cb)
        entities = []
        if isinstance(self.features.fan_hot_tolerance_on_entity, str):
            entities.append(self.features.fan_hot_tolerance_on_entity)
        if isinstance(self.features.fan_on_setpoint_reached_toggle_entity, str):
            entities.append(self.features.fan_on_setpoint_reached_toggle_entity)
        if entities:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass,
                    list(set(entities)),
                    self._async_tolerance_toggle_changed,
                )
            )

    async def _async_tolerance_toggle_changed(
        self, event: Event[EventStateChangedData]
    ) -> None:
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return
        self._set_fan_hot_tolerance_on_state()
        self._set_fan_on_setpoint_reached_on_state()
        await self.async_control_hvac()
        if self._async_write_ha_state_cb:
            self._async_write_ha_state_cb()

    async def _async_check_device_initial_state(self) -> None:
        if self._hvac_mode == HVACMode.OFF and self._climate_is_running():
            _LOGGER.warning(
                "Climate mode is OFF but %s is running; turning off",
                self.entity_id,
            )
            await self.async_set_hvac_mode(HVACMode.OFF)

    def _climate_is_running(self) -> bool:
        return self._climate_state in (HVACMode.COOL, HVACMode.FAN_ONLY)

    @property
    def is_active(self) -> bool:
        """True when the climate unit is cooling or circulating (fan_only)."""
        return self._climate_is_running()

    @property
    def is_on(self) -> bool:
        return self.is_active

    @property
    def hvac_action(self) -> HVACAction:
        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self.hvac_controller.is_active:
            return HVACAction.COOLING
        if self.is_circulating:
            return HVACAction.FAN
        return HVACAction.IDLE

    def _should_pre_cool_fan(self) -> bool:
        if not self._fan_hot_tolerance_on:
            return False
        if self.environment.fan_hot_tolerance is None:
            return False
        if self.environment.fan_hot_tolerance <= 0:
            return False
        is_fan_air_outside = self.features.is_fan_uses_outside_air
        if is_fan_air_outside and self.environment.is_warmer_outside:
            return False
        return self.environment.is_within_fan_tolerance(self.target_env_attr)

    def _should_post_cool_fan(self) -> bool:
        if not self.features.is_configured_for_fan_on_setpoint_reached:
            return False
        if not self._fan_on_setpoint_reached_on:
            return False
        return self.environment.is_within_post_cool_fan_band(self.target_env_attr)

    async def async_control_hvac(self, time=None, force=False):
        _LOGGER.debug(
            "%s - async_control_hvac time: %s force: %s",
            self._device_type,
            time,
            force,
        )
        self._set_fan_hot_tolerance_on_state()
        self._set_fan_on_setpoint_reached_on_state()
        self._set_self_active()

        if not self.hvac_controller.needs_control(
            self._active, self.hvac_mode, time, force
        ):
            return

        if self._hvac_mode == HVACMode.OFF:
            if self._climate_is_running():
                await self.async_set_hvac_mode(HVACMode.OFF)
            return

        any_opening_open = self.openings.any_opening_open(self.hvac_mode)
        if any_opening_open:
            await self.async_set_hvac_mode(HVACMode.OFF)
            self._hvac_action_reason = HVACActionReason.OPENING
            return

        force_override = (
            True
            if (
                self.environment.fan_hot_tolerance is not None
                or self.features.is_configured_for_fan_on_setpoint_reached
            )
            else force
        )

        if (
            self.hvac_controller.is_active
            and not self.hvac_controller.ran_long_enough()
            and not force_override
        ):
            self._hvac_action_reason = HVACActionReason.MIN_CYCLE_DURATION_NOT_REACHED
            return

        if self.environment.is_too_hot(self.target_env_attr):
            if self._should_pre_cool_fan():
                await self.async_set_hvac_mode(HVACMode.FAN_ONLY)
                self._hvac_action_reason = (
                    HVACActionReason.TARGET_TEMP_NOT_REACHED_WITH_FAN
                )
            else:
                await self.async_set_cool_temperature()
                self._hvac_action_reason = HVACActionReason.TARGET_TEMP_NOT_REACHED
        elif self._should_post_cool_fan():
            await self.async_set_hvac_mode(HVACMode.FAN_ONLY)
            self._hvac_action_reason = HVACActionReason.TARGET_TEMP_REACHED_WITH_FAN
        else:
            await self.async_set_hvac_mode(HVACMode.OFF)
            self._hvac_action_reason = HVACActionReason.TARGET_TEMP_REACHED

        self.hvac_power.update_hvac_power(
            self.strategy, self.target_env_attr, self.hvac_action
        )
