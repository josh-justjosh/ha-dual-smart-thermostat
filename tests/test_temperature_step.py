"""Tests for target_temp_step and precision handling."""

from homeassistant.components.climate import DOMAIN as CLIMATE
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import METRIC_SYSTEM

from custom_components.dual_smart_thermostat.const import DOMAIN
from tests import common, setup_sensor


async def test_target_temp_step_yaml(hass):
    """YAML target_temp_step is exposed on the climate entity."""
    hass.config.units = METRIC_SYSTEM
    setup_sensor(hass, 22.0)

    assert await async_setup_component(
        hass,
        CLIMATE,
        {
            "climate": {
                "platform": DOMAIN,
                "name": "bedroom",
                "heater": common.ENT_HEATER,
                "cooler": common.ENT_COOLER,
                "target_sensor": common.ENT_SENSOR,
                "heat_cool_mode": True,
                "precision": 0.5,
                "target_temp_step": 0.5,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("climate.bedroom")
    assert state.attributes.get("target_temp_step") == 0.5


async def test_set_temperature_snaps_to_step(hass):
    """Setting temperature snaps to the configured step."""
    hass.config.units = METRIC_SYSTEM
    setup_sensor(hass, 22.0)

    assert await async_setup_component(
        hass,
        CLIMATE,
        {
            "climate": {
                "platform": DOMAIN,
                "name": "bedroom",
                "heater": common.ENT_HEATER,
                "target_sensor": common.ENT_SENSOR,
                "target_temp_step": 0.5,
                "precision": 0.5,
            }
        },
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        CLIMATE,
        "set_temperature",
        {"entity_id": "climate.bedroom", "temperature": 20.3},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("climate.bedroom")
    assert state.attributes.get("temperature") == 20.5
