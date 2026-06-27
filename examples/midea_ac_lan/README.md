# Midea AC LAN + Dual Smart Thermostat

This example shows how to use **Dual Smart Thermostat** as a smart controller on top of a **Midea AC LAN** climate entity, without wrapper automations.

## What you get

- Room temperature-based cooling with tolerances and min cycle protection
- Direct control of the Midea unit via `climate.set_hvac_mode` and `climate.set_temperature`
- **Fan on setpoint reached**: after the cooling target is met, the AC switches to `fan_only` instead of turning fully off
- Optional pre-cool fan staging via `fan_hot_tolerance` (fan before compressor engages)

## Prerequisites

- [Midea AC LAN](https://github.com/wuwentao/midea_ac_lan) integration installed and paired
- [Dual Smart Thermostat](https://github.com/swingerman/ha-dual-smart-thermostat) installed (this repo)
- A room temperature sensor (any `sensor.*` with a temperature reading, or Midea's optional indoor temperature sensor)

## Setup via UI (recommended)

1. **Settings → Devices & Services → Add Integration → Dual Smart Thermostat**
2. Choose **Air conditioning only**
3. On **Basic Configuration**, select your Midea entity as **Air conditioning device** (`climate.{device_id}_climate`)
4. On **Fan circulation**, enable **Fan on setpoint reached** for post-cool fan-only mode
5. Finish the wizard (optional features: separate fan switch, humidity, openings, presets)

## Setup via YAML

1. Find your Midea climate entity ID (e.g. `climate.1234567890_climate`) under **Settings → Devices & Services → Midea AC LAN**.

2. Copy [configuration.yaml](configuration.yaml) into your Home Assistant config (or merge the `climate:` block).

3. Replace placeholders:
   - `climate.1234567890_climate` → your Midea climate entity
   - `sensor.bedroom_temperature` → your room temperature sensor

4. Restart Home Assistant.

## Configuration reference

| Option | Purpose |
|--------|---------|
| `heater` | Midea `climate.*_climate` entity (required for AC-only mode) |
| `ac_mode: true` | Treats `heater` as a cooler |
| `fan_on_setpoint_reached` | Switch to `fan_only` after target temperature is reached |
| `fan_cold_tolerance` | Extra band below setpoint where fan may still run |
| `fan_hot_tolerance` | Optional pre-cool fan band before compressor starts |
| `hot_tolerance` / `cold_tolerance` | When cooling starts and stops |

## Temperature behavior

With target 24°C, hot_tolerance 0.5, cold_tolerance 0.3, and `fan_on_setpoint_reached: true`:

1. **Too hot** (≥ 24.5°C) → Midea set to `cool`
2. **Target reached** (within comfort band) → Midea set to `fan_only`
3. **Too hot again** → back to `cool`
4. **Well below target** → `off`

## Notes

- No changes to the Midea integration are required.
- Do **not** also control the same Midea entity with separate automations — dual-smart owns the actuator.
- Heat + cool on one Midea unit is not covered by this example (single-mode AC-only setup).
- For a **fan heater on a switch** plus Midea AC in **heat/cool mode**, see [../midea_ac_fan_heater/README.md](../midea_ac_fan_heater/README.md).
