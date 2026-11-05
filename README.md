# Meta Thermostat for Home Assistant

`meta_thermostat` is a custom Home Assistant climate integration that acts as a
wrapper to control multiple child thermostats simultaneously. It synchronizes
target temperatures, HVAC modes, and preset behaviors across all connected
entities while allowing fine-grained per-entity overrides.

**Note on Behavior:** This integration functions strictly as a one-way command
dispatcher. It pushes configuration changes down to the configured child
entities, but it does not reconcile conflicting states or aggregate state
updates back from the underlying devices.

---

## Features

- **Group Control:** Synchronize temperature settings and HVAC modes across multiple climate entities.
- **Custom Presets:** Define custom presets mapped directly to target temperatures.
- **Preset Passthrough:** Choose whether to pass preset mode names directly to child entities or convert them into target temperatures.
- **HVAC Propagation:** Enable or disable forwarding HVAC mode changes globally or per entity.
- **Custom Script Triggers:** Run custom Home Assistant scripts whenever an HVAC mode change occurs (`hvac_mode_action`).
- **State Restoration:** Automatically restores target temperatures, HVAC modes, and active presets after a Home Assistant restart.

---

## Installation

### HACS (Recommended)

1. Open **HACS** in your Home Assistant instance.
2. Go to **Integrations**.
3. Click the menu icon (three dots) in the top-right corner and select **Custom repositories**.
4. Add your repository URL, set the category to **Integration**, and click **Add**.
5. Search for **Meta Thermostat**, click **Download**, and restart Home Assistant.

### Manual Installation

1. Copy the `custom_components/meta_thermostat` directory into your Home Assistant `<config_dir>/custom_components/` directory.
2. Restart Home Assistant.

---

## Configuration

Add the platform configuration to your `configuration.yaml` file under the
`climate:` section.

### Minimal Example

```yaml
climate:
  - platform: meta_thermostat
    name: Downstairs Climate
    entities:
      - climate.living_room_thermostat
      - climate.hallway_thermostat
```

### Advanced Example

```yaml
climate:
  - platform: meta_thermostat
    name: Main House Thermostat
    preset_mode_passthrough: false
    hvac_mode_propagation: true
    hvac_mode_action: script.global_hvac_trigger
    presets:
      Comfort: 21.5
      Eco: 18.0
      Away: 15.0
    entities:
      - climate.bedroom_thermostat
      - entity_id: climate.kitchen_thermostat
        preset_mode_passthrough: true
        hvac_mode_propagation: false
        hvac_mode_action: script.kitchen_hvac_override
```

---

## Configuration Options

### Global Platform Parameters

| Key | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `platform` | string | **Yes** | — | Must be set to `meta_thermostat`. |
| `name` | string | **Yes** | — | Display name for the meta-thermostat entity. |
| `entities` | list | **Yes** | — | List of child climate entities. Accepts strings (entity IDs) or dictionaries for advanced settings. |
| `presets` | map | No | `{}` | Key-value pairs mapping preset names to target temperatures (e.g., `Comfort: 21.5`). |
| `preset_mode_passthrough` | boolean | No | `false` | When `true`, preset mode selections are passed directly to child entities as preset names rather than temperature values. |
| `hvac_mode_propagation` | boolean | No | `true` | When `true`, changing the HVAC mode on the meta-thermostat forwards the change to child entities. |
| `hvac_mode_action` | string | No | `none` | Home Assistant script to call whenever the HVAC mode is changed. |

### Per-Entity Overrides

When defining an entity under `entities` using dictionary format, you can override global behaviors for that specific child device:

| Key | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `entity_id` | string | **Yes** | — | The target child entity ID (e.g., `climate.kitchen_thermostat`). |
| `preset_mode_passthrough` | boolean | No | Inherited | Overrides the global `preset_mode_passthrough` setting for this entity. |
| `hvac_mode_propagation` | boolean | No | Inherited | Overrides the global `hvac_mode_propagation` setting for this entity. |
| `hvac_mode_action` | string | No | Inherited | Overrides the global `hvac_mode_action` script trigger for this entity. |
