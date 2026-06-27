# Fan Heater + Midea AC (Heat/Cool Mode)

This example covers a common setup:

- **Heater:** a “dumb” fan heater on a smart switch (`switch.*`)
- **Cooler:** a Midea AC LAN climate entity (`climate.*`) with `cool` and `fan_only`
- **Mode:** `heat_cool` — automatic switching between heating and cooling

## What you get

- Room temperature kept between `target_temp_low` and `target_temp_high`
- Fan heater turns on when it gets too cold
- Midea AC cools when it gets too hot (via `climate.set_hvac_mode` / `set_temperature`)
- Optional **fan on setpoint reached**: after the cooling target is met, the AC switches to `fan_only` instead of turning fully off
- Both devices off when temperature is within the comfort band

## Prerequisites

- [Midea AC LAN](https://github.com/wuwentao/midea_ac_lan) integration (cool + fan_only + off)
- [Dual Smart Thermostat](https://github.com/swingerman/ha-dual-smart-thermostat) (this repo)
- A room temperature sensor
- A smart switch controlling your fan heater

## Bedroom example (your entities)

See [bedroom.yaml](bedroom.yaml) for a ready-to-use config with:

| Entity | Role |
|--------|------|
| `switch.bedroom_heater` | Fan heater |
| `climate.bedroom_ac` | Midea AC (cooling + swing passthrough) |
| `fan.bed` | Separate room fan |
| `input_boolean.bedroom_fan` | Toggle for the room fan during post-cool |

**Swing:** set vertical swing on the dual-smart thermostat card — it passes through to `climate.bedroom_ac`.

**Fans after cooling:**
- AC → `fan_only` when `fan_on_setpoint_reached: true`
- Room fan (`fan.bed`) → runs only when `fan_toggle` input_boolean is on

**Openings (per sensor scope):**
- `binary_sensor.bedroom_door` with `scope: cool` — pauses cooling only
- `binary_sensor.bedroom_draught` with `scope: heat` — pauses heating only

## Setup via UI

1. **Settings → Devices & Services → Add Integration → Dual Smart Thermostat**
2. Choose **Heater + cooler**
3. On **Basic Configuration**:
   - **Heater switch** → your fan heater switch
   - **Cooler** → your Midea `climate.*_climate` entity
   - Enable **Heat/Cool mode**
4. On **Fan circulation**, enable **Fan on setpoint reached** for post-cool `fan_only` on the Midea unit
5. Finish the wizard

## Setup via YAML

Copy [configuration.yaml](configuration.yaml) and replace:

| Placeholder | Your entity |
|-------------|-------------|
| `switch.fan_heater` | Fan heater switch |
| `climate.1234567890_climate` | Midea climate entity |
| `sensor.living_room_temperature` | Room temperature sensor |

Restart Home Assistant after editing `configuration.yaml`.

## Behavior (example: 20–24 °C)

| Condition | Heater | Midea AC |
|-----------|--------|----------|
| Too cold (below ~19.7 °C) | On | Off |
| Comfort band (20–24 °C) | Off | Off |
| Too hot (above ~24.5 °C) | Off | Cool |
| Cooling target reached | Off | `fan_only` (if enabled) |

Tolerances and `fan_cold_tolerance` adjust the exact thresholds.

## Notes

- Do not control the same Midea entity with separate automations — dual-smart owns the cooler actuator.
- The fan heater is a simple on/off switch; only the AC supports staged fan circulation.
- For AC-only cooling (no separate heater), see [../midea_ac_lan/README.md](../midea_ac_lan/README.md).
