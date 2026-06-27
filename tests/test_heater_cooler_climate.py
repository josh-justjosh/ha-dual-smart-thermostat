"""Tests for heater+cooler with climate actuator (Midea AC) in heat/cool mode."""

import datetime

from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
    HVACAction,
    HVACMode,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
)
from homeassistant.components.climate.const import ATTR_HVAC_MODES
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM
import pytest

from custom_components.dual_smart_thermostat.const import DOMAIN
from tests import common, setup_sensor, setup_switch

ENT_MIDEA_AC = "climate.midea_ac"
TARGET_LOW = 20.0
TARGET_HIGH = 24.0
HOT_TOLERANCE = 0.5
COLD_TOLERANCE = 0.3


@pytest.fixture
async def setup_heater_cooler_climate(hass: HomeAssistant):
    """Switch heater + Midea-like climate cooler in heat_cool mode."""
    hass.config.units = METRIC_SYSTEM
    setup_sensor(hass, 22.0)
    setup_switch(hass, False, entity_id=common.ENT_HEATER)

    hass.states.async_set(
        ENT_MIDEA_AC,
        HVACMode.OFF,
        {
            ATTR_TEMPERATURE: TARGET_HIGH,
            ATTR_HVAC_MODES: [HVACMode.OFF, HVACMode.COOL, HVACMode.FAN_ONLY],
        },
    )

    climate_calls: list[tuple[str, dict]] = []

    async def handle_set_hvac_mode(call: ServiceCall) -> None:
        climate_calls.append((SERVICE_SET_HVAC_MODE, dict(call.data)))
        hass.states.async_set(call.data[ATTR_ENTITY_ID], call.data["hvac_mode"])

    async def handle_set_temperature(call: ServiceCall) -> None:
        climate_calls.append((SERVICE_SET_TEMPERATURE, dict(call.data)))
        hass.states.async_set(
            call.data[ATTR_ENTITY_ID],
            call.data.get("hvac_mode", HVACMode.COOL),
            {"temperature": call.data.get(ATTR_TEMPERATURE, TARGET_HIGH)},
        )

    @callback
    def log_switch_call(call) -> None:
        entity_id = call.data[ATTR_ENTITY_ID]
        if call.service == SERVICE_TURN_ON:
            hass.states.async_set(entity_id, STATE_ON)
        else:
            hass.states.async_set(entity_id, STATE_OFF)

    hass.services.async_register(
        CLIMATE_DOMAIN, SERVICE_SET_HVAC_MODE, handle_set_hvac_mode
    )
    hass.services.async_register(
        CLIMATE_DOMAIN, SERVICE_SET_TEMPERATURE, handle_set_temperature
    )
    hass.services.async_register("homeassistant", SERVICE_TURN_ON, log_switch_call)
    hass.services.async_register("homeassistant", SERVICE_TURN_OFF, log_switch_call)

    assert await async_setup_component(
        hass,
        CLIMATE_DOMAIN,
        {
            "climate": {
                "platform": DOMAIN,
                "name": "test",
                "heater": common.ENT_HEATER,
                "cooler": ENT_MIDEA_AC,
                "target_sensor": common.ENT_SENSOR,
                "heat_cool_mode": True,
                "initial_hvac_mode": HVACMode.HEAT_COOL,
                "target_temp_low": TARGET_LOW,
                "target_temp_high": TARGET_HIGH,
                "cold_tolerance": COLD_TOLERANCE,
                "hot_tolerance": HOT_TOLERANCE,
                "min_cycle_duration": datetime.timedelta(seconds=0),
                "fan_on_setpoint_reached": True,
                "fan_cold_tolerance": 0.5,
            }
        },
    )
    await hass.async_block_till_done()


async def test_heat_cool_too_cold_turns_on_heater(hass: HomeAssistant, setup_heater_cooler_climate):
    """When too cold, heater on and climate cooler off."""
    setup_heater_cooler_climate
    setup_sensor(hass, 19.0)
    await hass.async_block_till_done()

    assert hass.states.get(common.ENT_HEATER).state == STATE_ON
    assert hass.states.get(ENT_MIDEA_AC).state == HVACMode.OFF


async def test_heat_cool_too_hot_cools(hass: HomeAssistant, setup_heater_cooler_climate):
    """When too hot, Midea AC set to cool and heater off."""
    setup_heater_cooler_climate
    setup_sensor(hass, 25.0)
    await hass.async_block_till_done()

    assert hass.states.get(ENT_MIDEA_AC).state == HVACMode.COOL
    assert hass.states.get(common.ENT_HEATER).state == STATE_OFF
    assert hass.states.get(ENT_MIDEA_AC).attributes.get(ATTR_TEMPERATURE) == TARGET_HIGH


async def test_heat_cool_in_range_both_off(hass: HomeAssistant, setup_heater_cooler_climate):
    """Within comfort band, both heater and climate cooler are off."""
    setup_heater_cooler_climate
    setup_sensor(hass, 22.0)
    await hass.async_block_till_done()

    assert hass.states.get(common.ENT_HEATER).state == STATE_OFF
    assert hass.states.get(ENT_MIDEA_AC).state == HVACMode.OFF


async def test_heat_cool_post_cool_fan(hass: HomeAssistant, setup_heater_cooler_climate):
    """After cooling target reached, AC switches to fan_only."""
    setup_heater_cooler_climate
    setup_sensor(hass, 25.0)
    await hass.async_block_till_done()
    assert hass.states.get(ENT_MIDEA_AC).state == HVACMode.COOL

    setup_sensor(hass, 23.8)
    await hass.async_block_till_done()
    assert hass.states.get(ENT_MIDEA_AC).state == HVACMode.FAN_ONLY


async def test_heat_cool_heating_turns_off_ac_fan(hass: HomeAssistant, setup_heater_cooler_climate):
    """Heating must turn off AC even when it is in fan_only circulation."""
    setup_heater_cooler_climate
    hass.states.async_set(ENT_MIDEA_AC, HVACMode.FAN_ONLY)
    setup_sensor(hass, 19.0)
    await hass.async_block_till_done()

    assert hass.states.get(common.ENT_HEATER).state == STATE_ON
    assert hass.states.get(ENT_MIDEA_AC).state == HVACMode.OFF


async def test_heat_cool_hvac_action_fan_when_circulating(
    hass: HomeAssistant, setup_heater_cooler_climate
):
    """Thermostat reports fan action while AC circulates after cooling."""
    setup_heater_cooler_climate
    setup_sensor(hass, 25.0)
    await hass.async_block_till_done()
    setup_sensor(hass, 23.8)
    await hass.async_block_till_done()

    assert hass.states.get(ENT_MIDEA_AC).state == HVACMode.FAN_ONLY
    state = hass.states.get("climate.test")
    assert state.attributes.get("hvac_action") == HVACAction.FAN
