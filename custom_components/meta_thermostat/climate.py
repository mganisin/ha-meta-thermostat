"""Meta Thermostat platform for Home Assistant.

This platform allows you to create a meta-thermostat entity that controls
multiple child thermostat entities. It supports setting HVAC modes, target
temperatures, and preset modes across all child entities simultaneously.

Example YAML configuration:
climate:
  - platform: meta_thermostat
    name: Living Room Thermostat
    entities:
      - climate.living_room_thermostat
      - entity_id: climate.kitchen_thermostat
        hvac_mode_action: script.kitchen_heating
      - entity_id: climate.bedroom_thermostat
        preset_mode_passthrough: true
    presets:
      Comfort: 22.0
      Eco: 18.0
"""

import logging
import voluptuous as vol

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_SET_PRESET_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
)
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_TEMPERATURE,
    CONF_NAME,
    UnitOfTemperature,
)
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ENTITIES,
    CONF_PRESETS,
    CONF_ENTITY_ID,
    CONF_HVAC_MODE_ACTION,
    CONF_PRESET_MODE_PASSTHROUGH,
    CONF_HVAC_MODE_PROPAGATION,
)

_LOGGER = logging.getLogger(__name__)

ENTITY_SCHEMA = vol.Any(
    cv.entity_id,
    vol.Schema(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id,
            vol.Optional(CONF_HVAC_MODE_ACTION): cv.entity_id,
            vol.Optional(CONF_PRESET_MODE_PASSTHROUGH): cv.boolean,
            vol.Optional(CONF_HVAC_MODE_PROPAGATION): cv.boolean,
        }
    ),
)

PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_ENTITIES): vol.All(cv.ensure_list, [ENTITY_SCHEMA]),
        vol.Optional(CONF_PRESETS): vol.Schema({cv.string: vol.Coerce(float)}),
        vol.Optional(CONF_PRESET_MODE_PASSTHROUGH, default=False): cv.boolean,
        vol.Optional(CONF_HVAC_MODE_PROPAGATION, default=True): cv.boolean,
        vol.Optional(CONF_HVAC_MODE_ACTION): cv.entity_id,
    }
)


# pylint: disable=unused-argument
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the meta_thermostat platform."""
    async_add_entities([MetaThermostat(config)])


class MetaThermostat(ClimateEntity, RestoreEntity):
    """MetaThermostat with state persistence and hierarchical propagation control."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(self, config):
        """Initialize and merge configurations."""
        self._attr_name = config.get(CONF_NAME)
        self._attr_unique_id = f"meta_{self._attr_name.lower().replace(' ', '_')}"
        self._presets = config.get(CONF_PRESETS, {})

        g_passthrough = config.get(CONF_PRESET_MODE_PASSTHROUGH, False)
        g_propagate = config.get(CONF_HVAC_MODE_PROPAGATION, True)
        g_action = config.get(CONF_HVAC_MODE_ACTION)

        self._entities_config = []
        for ent in config.get(CONF_ENTITIES):
            if isinstance(ent, str):
                self._entities_config.append(
                    {
                        CONF_ENTITY_ID: ent,
                        CONF_PRESET_MODE_PASSTHROUGH: g_passthrough,
                        CONF_HVAC_MODE_PROPAGATION: g_propagate,
                        CONF_HVAC_MODE_ACTION: g_action,
                    }
                )
            else:
                self._entities_config.append(
                    {
                        CONF_ENTITY_ID: ent[CONF_ENTITY_ID],
                        CONF_PRESET_MODE_PASSTHROUGH: ent.get(
                            CONF_PRESET_MODE_PASSTHROUGH, g_passthrough
                        ),
                        CONF_HVAC_MODE_PROPAGATION: ent.get(
                            CONF_HVAC_MODE_PROPAGATION, g_propagate
                        ),
                        CONF_HVAC_MODE_ACTION: ent.get(CONF_HVAC_MODE_ACTION, g_action),
                    }
                )

        self._attr_hvac_mode = HVACMode.OFF
        self._attr_target_temperature = 21.0
        self._attr_preset_mode = None

    async def async_added_to_hass(self):
        """Restore state on startup."""
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_hvac_mode = last_state.state
            self._attr_target_temperature = float(
                last_state.attributes.get(ATTR_TEMPERATURE, 21.0)
            )
            self._attr_preset_mode = last_state.attributes.get(ATTR_PRESET_MODE)

    @property
    def preset_modes(self):
        """Return available preset modes."""
        return list(self._presets.keys())

    @property
    def extra_state_attributes(self):
        """Return attributes to show connected entities."""
        return {CONF_ENTITIES: [e[CONF_ENTITY_ID] for e in self._entities_config]}

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode with single action script support."""
        self._attr_hvac_mode = hvac_mode
        for entity_conf in self._entities_config:
            if not entity_conf.get(CONF_HVAC_MODE_PROPAGATION, True):
                continue

            eid = entity_conf[CONF_ENTITY_ID]
            script_id = entity_conf.get(CONF_HVAC_MODE_ACTION)

            if script_id:
                domain, service = script_id.split(".", 1)
                await self.hass.services.async_call(
                    domain,
                    service,
                    {"entity_id": eid, "hvac_mode": str(hvac_mode)},
                    blocking=False,
                )
            else:
                await self.hass.services.async_call(
                    "climate",
                    SERVICE_SET_HVAC_MODE,
                    {ATTR_ENTITY_ID: eid, ATTR_HVAC_MODE: hvac_mode},
                    blocking=False,
                )
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        """Set temperature for children."""
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = temp
            if ATTR_PRESET_MODE not in kwargs:
                self._attr_preset_mode = None

            target_ids = kwargs.get(
                "target_entities", [e[CONF_ENTITY_ID] for e in self._entities_config]
            )
            if target_ids:
                await self.hass.services.async_call(
                    "climate",
                    SERVICE_SET_TEMPERATURE,
                    {ATTR_ENTITY_ID: target_ids, ATTR_TEMPERATURE: temp},
                    blocking=False,
                )
            self.async_write_ha_state()

    async def async_set_preset_mode(self, preset_mode):
        """Apply preset with passthrough logic."""
        if (temp := self._presets.get(preset_mode)) is not None:
            self._attr_preset_mode = preset_mode
            self._attr_target_temperature = temp

            if self._attr_hvac_mode == HVACMode.OFF:
                await self.async_set_hvac_mode(HVACMode.HEAT)

            for entity_conf in self._entities_config:
                eid = entity_conf[CONF_ENTITY_ID]
                if entity_conf.get(CONF_PRESET_MODE_PASSTHROUGH, False):
                    await self.hass.services.async_call(
                        "climate",
                        SERVICE_SET_PRESET_MODE,
                        {ATTR_ENTITY_ID: eid, ATTR_PRESET_MODE: preset_mode},
                        blocking=False,
                    )
                else:
                    await self.hass.services.async_call(
                        "climate",
                        SERVICE_SET_TEMPERATURE,
                        {ATTR_ENTITY_ID: eid, ATTR_TEMPERATURE: temp},
                        blocking=False,
                    )
            self.async_write_ha_state()
