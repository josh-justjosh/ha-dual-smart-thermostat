"""Tests for per-opening HVAC scope (heat vs cool openings)."""

from homeassistant.components.climate import HVACMode
from homeassistant.const import STATE_OFF, STATE_ON, STATE_OPEN
import pytest

from custom_components.dual_smart_thermostat.managers.opening_manager import (
    OpeningManager,
)


@pytest.fixture
def opening_manager(hass):
    """Opening manager with mixed heat/cool scoped sensors."""
    config = {
        "openings": [
            {"entity_id": "binary_sensor.bedroom_door", "scope": "cool"},
            {"entity_id": "binary_sensor.bedroom_draught", "scope": "heat"},
        ]
    }
    return OpeningManager(hass, config)


def test_per_opening_cool_scope_only(hass, opening_manager):
    """Cool-scoped opening affects cooling, not heating."""
    hass.states.async_set("binary_sensor.bedroom_door", STATE_OPEN)
    hass.states.async_set("binary_sensor.bedroom_draught", STATE_OFF)

    assert opening_manager.any_opening_open(HVACMode.COOL) is True
    assert opening_manager.any_opening_open(HVACMode.HEAT) is False


def test_per_opening_heat_scope_only(hass, opening_manager):
    """Heat-scoped opening affects heating, not cooling."""
    hass.states.async_set("binary_sensor.bedroom_door", STATE_OFF)
    hass.states.async_set("binary_sensor.bedroom_draught", STATE_OPEN)

    assert opening_manager.any_opening_open(HVACMode.HEAT) is True
    assert opening_manager.any_opening_open(HVACMode.COOL) is False


def test_per_opening_falls_back_to_global_scope(hass):
    """Openings without per-entity scope use global openings_scope."""
    manager = OpeningManager(
        hass,
        {
            "openings": ["binary_sensor.window"],
            "openings_scope": ["heat"],
        },
    )
    hass.states.async_set("binary_sensor.window", STATE_OPEN)

    assert manager.any_opening_open(HVACMode.HEAT) is True
    assert manager.any_opening_open(HVACMode.COOL) is False


def test_per_opening_overrides_global_scope(hass):
    """Per-opening scope overrides the global openings_scope default."""
    manager = OpeningManager(
        hass,
        {
            "openings": [
                {"entity_id": "binary_sensor.bedroom_door", "scope": "cool"},
            ],
            "openings_scope": ["heat"],
        },
    )
    hass.states.async_set("binary_sensor.bedroom_door", STATE_OPEN)

    assert manager.any_opening_open(HVACMode.COOL) is True
    assert manager.any_opening_open(HVACMode.HEAT) is False


def test_none_hvac_mode_scope_does_not_crash(hass, opening_manager):
    """Fan devices may pass hvac_mode=None before mode is assigned."""
    hass.states.async_set("binary_sensor.bedroom_door", STATE_OPEN)
    assert opening_manager.any_opening_open(None) is False


def test_global_scope_string_normalized(hass):
    """Global openings_scope stored as a string must not break membership checks."""
    manager = OpeningManager(
        hass,
        {
            "openings": [{"entity_id": "binary_sensor.window", "scope": "cool"}],
            "openings_scope": "heat",
        },
    )
    hass.states.async_set("binary_sensor.window", STATE_OPEN)

    assert manager.any_opening_open(HVACMode.COOL) is True
    assert manager.any_opening_open(HVACMode.HEAT) is False
    assert manager.any_opening_open(None) is False
