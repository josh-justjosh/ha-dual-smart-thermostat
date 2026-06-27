"""Tests for climate entity actuator support (e.g. Midea AC)."""

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

from custom_components.dual_smart_thermostat.const import DOMAIN
from custom_components.dual_smart_thermostat.hvac_action_reason.hvac_action_reason import (
    HVACActionReason,
)

from . import common, setup_sensor

ENT_MIDEA_AC = "climate.midea_ac"
TARGET = 24.0
HOT_TOLERANCE = 0.5
COLD_TOLERANCE = 0.3


@pytest.fixture
async def setup_climate_actuator(hass: HomeAssistant):
    """Set up dual-smart thermostat controlling a mock Midea-like climate entity."""
    hass.config.units = METRIC_SYSTEM
    setup_sensor(hass, 25.0)

    hass.states.async_set(
        ENT_MIDEA_AC,
        HVACMode.OFF,
        {
            ATTR_TEMPERATURE: TARGET,
            ATTR_HVAC_MODES: [
                HVACMode.OFF,
                HVACMode.COOL,
                HVACMode.FAN_ONLY,
            ],
        },
    )

    service_calls: list[tuple[str, dict]] = []

    async def handle_set_hvac_mode(call: ServiceCall) -> None:
        service_calls.append((SERVICE_SET_HVAC_MODE, dict(call.data)))
        entity_id = call.data[ATTR_ENTITY_ID]
        hass.states.async_set(entity_id, call.data["hvac_mode"])

    async def handle_set_temperature(call: ServiceCall) -> None:
        service_calls.append((SERVICE_SET_TEMPERATURE, dict(call.data)))
        entity_id = call.data[ATTR_ENTITY_ID]
        attrs = {"temperature": call.data.get(ATTR_TEMPERATURE, TARGET)}
        hass.states.async_set(
            entity_id,
            call.data.get("hvac_mode", HVACMode.COOL),
            attrs,
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
            }
        },
    )
    await hass.async_block_till_done()
    return service_calls


async def test_climate_actuator_turns_on_cool_when_too_hot(
    hass: HomeAssistant, setup_climate_actuator
) -> None:
    """Climate actuator should call set_temperature with cool mode when too hot."""
    service_calls = setup_climate_actuator
    setup_sensor(hass, TARGET + HOT_TOLERANCE + 1)

    await hass.async_block_till_done()

    assert hass.states.get(ENT_MIDEA_AC).state == HVACMode.COOL
    assert any(
        call[0] == SERVICE_SET_TEMPERATURE and call[1].get("hvac_mode") == HVACMode.COOL
        for call in service_calls
    )


async def test_climate_actuator_turns_off_when_target_reached(
    hass: HomeAssistant, setup_climate_actuator
) -> None:
    """Climate actuator should turn off when temperature target is reached."""
    service_calls = setup_climate_actuator
    hass.states.async_set(ENT_MIDEA_AC, HVACMode.COOL, {ATTR_TEMPERATURE: TARGET})
    setup_sensor(hass, TARGET - COLD_TOLERANCE)

    await hass.async_block_till_done()

    assert hass.states.get(ENT_MIDEA_AC).state == HVACMode.OFF


async def test_climate_actuator_reports_cooling_action(
    hass: HomeAssistant, setup_climate_actuator
) -> None:
    """Thermostat should report cooling when underlying climate entity is cooling."""
    setup_climate_actuator
    hass.states.async_set(ENT_MIDEA_AC, HVACMode.COOL, {ATTR_TEMPERATURE: TARGET})
    setup_sensor(hass, TARGET + HOT_TOLERANCE + 1)

    await hass.async_block_till_done()

    state = hass.states.get(common.ENTITY)
    assert state.attributes.get("hvac_action") == HVACAction.COOLING


async def test_climate_actuator_is_active_when_cooling(
    hass: HomeAssistant, setup_climate_actuator
) -> None:
    """Underlying climate entity in cool mode is treated as active."""
    setup_climate_actuator
    hass.states.async_set(ENT_MIDEA_AC, HVACMode.COOL, {ATTR_TEMPERATURE: TARGET})
    setup_sensor(hass, TARGET + HOT_TOLERANCE + 1)

    await hass.async_block_till_done()

    state = hass.states.get(common.ENTITY)
    assert state.attributes.get("hvac_action") == HVACAction.COOLING
