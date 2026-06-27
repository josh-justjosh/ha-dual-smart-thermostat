"""Tests for swing mode passthrough to climate actuators."""

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    HVACMode,
    SERVICE_SET_SWING_MODE,
)
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODES,
    ATTR_SWING_MODE,
    ATTR_SWING_MODES,
    SWING_OFF,
    SWING_VERTICAL,
    ClimateEntityFeature,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM
import pytest

from custom_components.dual_smart_thermostat.const import DOMAIN
from tests import common, setup_sensor, setup_switch

ENT_MIDEA_AC = "climate.bedroom_ac"
SWING_MODES = [SWING_OFF, SWING_VERTICAL, "horizontal", "both"]


@pytest.fixture
async def setup_swing_passthrough(hass: HomeAssistant):
    """Heater+cooler with Midea-like swing modes on the climate actuator."""
    hass.config.units = METRIC_SYSTEM
    setup_sensor(hass, 22.0)
    setup_switch(hass, False, entity_id=common.ENT_HEATER)

    hass.states.async_set(
        ENT_MIDEA_AC,
        HVACMode.OFF,
        {
            ATTR_HVAC_MODES: [HVACMode.OFF, HVACMode.COOL, HVACMode.FAN_ONLY],
            ATTR_SWING_MODES: SWING_MODES,
            ATTR_SWING_MODE: SWING_OFF,
            ATTR_SUPPORTED_FEATURES: ClimateEntityFeature.SWING_MODE,
        },
    )

    swing_calls: list[dict] = []

    async def handle_set_swing_mode(call: ServiceCall) -> None:
        swing_calls.append(dict(call.data))
        entity_id = call.data[ATTR_ENTITY_ID]
        attrs = dict(hass.states.get(entity_id).attributes)
        attrs[ATTR_SWING_MODE] = call.data[ATTR_SWING_MODE]
        hass.states.async_set(entity_id, hass.states.get(entity_id).state, attrs)

    hass.services.async_register(
        CLIMATE_DOMAIN, SERVICE_SET_SWING_MODE, handle_set_swing_mode
    )

    assert await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            "climate": {
                "platform": DOMAIN,
                "name": "bedroom",
                "heater": common.ENT_HEATER,
                "cooler": ENT_MIDEA_AC,
                "target_sensor": common.ENT_SENSOR,
                "heat_cool_mode": True,
                "initial_hvac_mode": HVACMode.HEAT_COOL,
                "target_temp_low": 20,
                "target_temp_high": 24,
            }
        },
    )
    await hass.async_block_till_done()
    return swing_calls


async def test_swing_modes_exposed(hass: HomeAssistant, setup_swing_passthrough):
    """Thermostat exposes swing modes from the underlying climate entity."""
    setup_swing_passthrough
    state = hass.states.get("climate.bedroom")
    assert SWING_VERTICAL in (state.attributes.get(ATTR_SWING_MODES) or [])


async def test_set_swing_mode_passthrough(hass: HomeAssistant, setup_swing_passthrough):
    """Setting swing on the thermostat forwards to the climate actuator."""
    swing_calls = setup_swing_passthrough
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_SWING_MODE,
        {ATTR_ENTITY_ID: "climate.bedroom", ATTR_SWING_MODE: SWING_VERTICAL},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert any(
        call.get(ATTR_ENTITY_ID) == ENT_MIDEA_AC
        and call.get(ATTR_SWING_MODE) == SWING_VERTICAL
        for call in swing_calls
    )
    assert (
        hass.states.get(ENT_MIDEA_AC).attributes.get(ATTR_SWING_MODE) == SWING_VERTICAL
    )
