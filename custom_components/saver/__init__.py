import logging

import homeassistant.helpers.config_validation as cv
from homeassistant.core import Context

from homeassistant.helpers.entity import Entity
from homeassistant.helpers.script import Script
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME

import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'saver'

CONF_DELETE_AFTER_RUN = 'delete_after_run'
CONF_RESTORE_SCRIPT = 'restore_script'
CONF_SCRIPT = 'script'
CONF_VALUE = 'value'

SERVICE_DELETE = 'delete'
SERVICE_DELETE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id
})

SERVICE_DELETE_VARIABLE = 'delete_variable'
SERVICE_DELETE_VARIABLE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string
})

SERVICE_EXECUTE = 'execute'
SERVICE_EXECUTE_SCHEMA = vol.Schema({
    vol.Required(CONF_SCRIPT): cv.SCRIPT_SCHEMA
})

SERVICE_RESTORE_STATE = 'restore_state'
SERVICE_RESTORE_STATE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Required(CONF_RESTORE_SCRIPT): cv.SCRIPT_SCHEMA,
    vol.Optional(CONF_DELETE_AFTER_RUN, default=True): cv.boolean
})

SERVICE_SAVE_STATE = 'save_state'
SERVICE_SAVE_STATE_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id
})

SERVICE_SET_VARIABLE = 'set_variable'
SERVICE_SET_VARIABLE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
    vol.Required(CONF_VALUE): cv.string
})


def setup(hass, config):
    component = EntityComponent(_LOGGER, DOMAIN, hass)
    saver_entity = SaverEntity()
    component.add_entities([saver_entity])

    def delete(call):
        data = call.data
        entity_id = data[CONF_ENTITY_ID]
        saver_entity.delete(entity_id)

    def delete_variable(call):
        data = call.data
        variable = data[CONF_NAME]
        saver_entity.delete_variable(variable)

    def execute(call):
        data = call.data
        script = data[CONF_SCRIPT]
        saver_entity.execute(script)

    def restore_state(call):
        data = call.data
        entity_id = data[CONF_ENTITY_ID]
        restore_script = data[CONF_RESTORE_SCRIPT]
        should_delete = data[CONF_DELETE_AFTER_RUN]
        saver_entity.restore(entity_id, restore_script, should_delete)

    def save_state(call):
        data = call.data
        entity_id = data[CONF_ENTITY_ID]
        saver_entity.save(entity_id)

    def set_variable(call):
        data = call.data
        name = data[CONF_NAME]
        value = data[CONF_VALUE]
        saver_entity.set_variable(name, value)

    hass.services.register(DOMAIN, SERVICE_DELETE, delete, SERVICE_DELETE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_DELETE_VARIABLE, delete_variable, SERVICE_DELETE_VARIABLE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_EXECUTE, execute, SERVICE_EXECUTE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_RESTORE_STATE, restore_state, SERVICE_RESTORE_STATE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_SAVE_STATE, save_state, SERVICE_SAVE_STATE_SCHEMA)
    hass.services.register(DOMAIN, SERVICE_SET_VARIABLE, set_variable, SERVICE_SET_VARIABLE_SCHEMA)

    return True


class SaverEntity(Entity):

    def __init__(self):
        self._entities_db = {}
        self._variables_db = {}

    @property
    def name(self):
        return DOMAIN

    def delete(self, entity_id):
        self._entities_db.pop(entity_id)
        self.schedule_update_ha_state()

    def delete_variable(self, variable):
        self._variables_db.pop(variable)
        self.schedule_update_ha_state()

    def execute(self, script):
        script = Script(self.hass, script)
        variables = {}
        variables.update(self._variables_db)
        for entity_id in self._entities_db:
            variables.update(SaverEntity.convert_to_variables(self._entities_db[entity_id], entity_id))
        script.run(variables=variables, context=Context())
        self.schedule_update_ha_state()

    def restore(self, entity_id, restore_script, delete):
        if entity_id not in self._entities_db:
            return
        old = self._entities_db[entity_id]
        variables = SaverEntity.convert_to_variables(old)
        if delete:
            self._entities_db.pop(entity_id)
        script = Script(self.hass, restore_script)
        script.run(variables=variables, context=Context())
        self.schedule_update_ha_state()

    def save(self, entity_id):
        self._entities_db[entity_id] = self.hass.states.get(entity_id)
        self.schedule_update_ha_state()

    def set_variable(self, variable, value):
        self._variables_db[variable] = value
        self.schedule_update_ha_state()

    @property
    def state_attributes(self):
        return {
            "entities": list(self._entities_db.keys()),
            "variables": list(self._variables_db.keys())
        }

    @property
    def state(self):
        return len(self._entities_db) + len(self._variables_db)

    @staticmethod
    def convert_to_variables(state, entity_id=None):
        prefix = ""
        if entity_id is not None:
            prefix = f"{entity_id}_".replace(".", "_")
        variables = {f"{prefix}state": state.state}
        for attr in state.attributes:
            variables[f"{prefix}attr_{attr}"] = state.attributes[attr]
        return variables
