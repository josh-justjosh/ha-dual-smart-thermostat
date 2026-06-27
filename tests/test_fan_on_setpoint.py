"""Tests for fan-on-setpoint-reached feature."""

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    HVACAction,
    HVACMode,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.climate.const import ATTR_HVAC_MODES
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM
import pytest

from custom_components.dual_smart_thermostat.const import ATTR_HVAC_ACTION_REASON, DOMAIN
from custom_components.dual_smart_thermostat.hvac_action_reason.hvac_action_reason import (
    HVACActionReason,
)
from custom_components.dual_smart_thermostat.managers.environment_manager import (
    EnvironmentManager,
)

from . import common, setup_sensor, setup_switch

ENT_MIDEA_AC = "climate.midea_ac"
TARGET = 24.0
HOT_TOLERANCE = 0.5
COLD_TOLERANCE = 0.3


@pytest.fixture
async def setup_climate_fan_on_setpoint(hass: HomeAssistant):
    """Climate actuator with fan_on_setpoint_reached enabled."""
    hass.config.units = METRIC_SYSTEM
    setup_sensor(hass, 25.0)

    hass.states.async_set(
        ENT_MIDEA_AC,
        HVACMode.OFF,
        {
            ATTR_TEMPERATURE: TARGET,
            ATTR_HVAC_MODES: [HVACMode.OFF, HVACMode.COOL, HVACMode.FAN_ONLY],
        },
    )

    async def handle_set_hvac_mode(call: ServiceCall) -> None:
        hass.states.async_set(call.data[ATTR_ENTITY_ID], call.data["hvac_mode"])

    async def handle_set_temperature(call: ServiceCall) -> None:
        hass.states.async_set(
            call.data[ATTR_ENTITY_ID],
            call.data.get("hvac_mode", HVACMode.COOL),
            {"temperature": call.data.get(ATTR_TEMPERATURE, TARGET)},
        )

    hass.services.async_register(
        CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE, handle_set_hvac_mode
    )
    hass.services.async_register(
        CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, handle_set_temperature
    )

    assert await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            "climate": {
                "platform": DOMAIN,
                "name": "test",
                "ac_mode": True,
                "heater": ENT_MIDEA_AC,
                "target_sensor": common.ENT_SENSOR,
                "initial_hvac_mode": HVACMode.COOL,
                "hot_tolerance": HOT_TOLERANCE,
                "cold_tolerance": COLD_TOLERANCE,
                "target_temp": TARGET,
                "fan_on_setpoint_reached": True,
                "fan_cold_tolerance": 0.5,
            }
        },
    )
    await hass.async_block_till_done()


@pytest.fixture
async def setup_switch_fan_on_setpoint(hass: HomeAssistant):
    """Switch cooler with separate fan and fan_on_setpoint_reached."""
    hass.config.units = METRIC_SYSTEM
    setup_sensor(hass, 25.0)
    setup_switch(hass, False)
    setup_switch(hass, False, entity_id=common.ENT_FAN)

    assert await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            "climate": {
                "platform": DOMAIN,
                "name": "test",
                "ac_mode": True,
                "heater": common.ENT_SWITCH,
                "fan": common.ENT_FAN,
                "fan_on_with_ac": False,
                "target_sensor": common.ENT_SENSOR,
                "initial_hvac_mode": HVACMode.COOL,
                "hot_tolerance": HOT_TOLERANCE,
                "cold_tolerance": COLD_TOLERANCE,
                "target_temp": TARGET,
                "fan_on_setpoint_reached": True,
                "fan_cold_tolerance": 0.5,
            }
        },
    )
    await hass.async_block_till_done()


def test_is_within_post_cool_fan_band(hass: HomeAssistant) -> None:
    """Environment manager post-cool band helper."""
    env = EnvironmentManager(
        hass,
        {
            "target_sensor": common.ENT_SENSOR,
            "cold_tolerance": COLD_TOLERANCE,
            "hot_tolerance": HOT_TOLERANCE,
            "fan_cold_tolerance": 0.5,
            "target_temp": TARGET,
        },
    )
    env.set_hvac_mode(HVACMode.COOL)
    env._cur_temp = TARGET
    assert env.is_within_post_cool_fan_band() is True

    env._cur_temp = TARGET + HOT_TOLERANCE
    assert env.is_within_post_cool_fan_band() is False

    env._cur_temp = TARGET - COLD_TOLERANCE - 0.6
    assert env.is_within_post_cool_fan_band() is False


async def test_climate_switches_to_fan_only_after_setpoint(
    hass: HomeAssistant, setup_climate_fan_on_setpoint
) -> None:
    """After cooling target is reached, climate actuator switches to fan_only."""
    setup_climate_fan_on_setpoint
    hass.states.async_set(ENT_MIDEA_AC, HVACMode.COOL, {ATTR_TEMPERATURE: TARGET})
    setup_sensor(hass, TARGET)

    await hass.async_block_till_done()

    assert hass.states.get(ENT_MIDEA_AC).state == HVACMode.FAN_ONLY
    state = hass.states.get(common.ENTITY)
    assert (
        state.attributes.get(ATTR_HVAC_ACTION_REASON)
        == HVACActionReason.TARGET_TEMP_REACHED_WITH_FAN
    )
    assert state.attributes.get("hvac_action") == HVACAction.FAN


async def test_climate_returns_to_cool_when_too_hot_again(
    hass: HomeAssistant, setup_climate_fan_on_setpoint
) -> None:
    """Climate actuator resumes cooling when temperature rises above tolerance."""
    setup_climate_fan_on_setpoint
    hass.states.async_set(ENT_MIDEA_AC, HVACMode.FAN_ONLY)
    setup_sensor(hass, TARGET + HOT_TOLERANCE + 1)

    await hass.async_block_till_done()

    assert hass.states.get(ENT_MIDEA_AC).state == HVACMode.COOL


async def test_switch_fan_runs_after_setpoint_reached(
    hass: HomeAssistant, setup_switch_fan_on_setpoint
) -> None:
    """Separate fan switch turns on after cooler reaches setpoint."""
    setup_switch_fan_on_setpoint
    hass.states.async_set(common.ENT_SWITCH, "on")
    setup_sensor(hass, TARGET - 0.1)

    await hass.async_block_till_done()

    assert hass.states.get(common.ENT_SWITCH).state == "off"
    assert hass.states.get(common.ENT_FAN).state == "on"
