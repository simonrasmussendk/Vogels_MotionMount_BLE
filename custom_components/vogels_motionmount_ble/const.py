"""Constants for the Vogels MotionMount BLE integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "vogels_motionmount"

# Configuration keys
CONF_ADAPTER = "adapter"
CONF_DEVICE_ADDRESS = "device_address"
CONF_DEVICE_NAME = "device_name"
CONF_AUTO_DISCONNECT_TIMEOUT = "auto_disconnect_timeout"
CONF_LOG_LEVEL = "log_level"
CONF_DEBUG_RAW_DATA = "debug_raw_data"

# GATT UUIDs - Auto-discovered during setup
CONF_UUID_NUS_TX = "uuid_nus_tx"
CONF_UUID_EXTENSION_TARGET = "uuid_extension_target"
CONF_UUID_TURN_TARGET = "uuid_turn_target"
CONF_UUID_PRESET = "uuid_preset"

# Default values
DEFAULT_AUTO_DISCONNECT_TIMEOUT: Final = 300  # 5 minutes
DEFAULT_LOG_LEVEL: Final = "INFO"
DEFAULT_DEVICE_NAME: Final = "Vogels MotionMount"

# Entity configuration
ENTITY_EXTENSION_TARGET = "extension_target"
ENTITY_TURN_TARGET = "turn_target"
ENTITY_EXTENSION_CURRENT = "extension_current"
ENTITY_TURN_CURRENT = "turn_current"
ENTITY_IS_MOVING = "is_moving"
ENTITY_PRESET_0 = "preset_0"
ENTITY_PRESET_1 = "preset_1"
ENTITY_PRESET_2 = "preset_2"
ENTITY_PRESET_3 = "preset_3"
ENTITY_PRESET_4 = "preset_4"
ENTITY_PRESET_5 = "preset_5"
ENTITY_PRESET_6 = "preset_6"
ENTITY_STOP = "stop"
ENTITY_CONNECTION_STATUS = "connection_status"

# Value constraints
# Extension ranges from 0% (at wall) to 100% (fully extended into room).
MIN_EXTENSION_TARGET_VALUE: Final = 0
MAX_EXTENSION_TARGET_VALUE: Final = 100
# Turn is signed. In the UI we use slider-intuitive signs:
#   -100% = full left, 0% = centered (flush with wall), +100% = full right.
# The device firmware uses the opposite sign convention, so values are
# inverted in connection.py / models.py at the BLE boundary.
MIN_TURN_TARGET_VALUE: Final = -100
MAX_TURN_TARGET_VALUE: Final = 100

# Kept for backward compatibility with older imports.
MIN_TARGET_VALUE: Final = MIN_EXTENSION_TARGET_VALUE
MAX_TARGET_VALUE: Final = MAX_EXTENSION_TARGET_VALUE

# Connection settings
CONNECTION_TIMEOUT: Final = 30.0
RECONNECT_BASE_DELAY: Final = 1.0
RECONNECT_MAX_DELAY: Final = 300.0
RECONNECT_JITTER_MAX: Final = 5.0
MAX_RECONNECT_ATTEMPTS: Final = 10

# Telemetry parsing - values may be signed (turn can be negative)
TELEMETRY_EXTENSION_CURRENT_PATTERN = r"mount/extension/current\s*=\s*(-?\d+)"
TELEMETRY_TURN_CURRENT_PATTERN = r"mount/turn/current\s*=\s*(-?\d+)"
TELEMETRY_EXTENSION_TARGET_PATTERN = r"mount/extension/target\s*=\s*(-?\d+)"
TELEMETRY_TURN_TARGET_PATTERN = r"mount/turn/target\s*=\s*(-?\d+)"
TELEMETRY_MOVING_PATTERN = r"mount/isMoving\s*=\s*([01])"

# Aliases for backward compatibility
TELEMETRY_EXTENSION_PATTERN = TELEMETRY_EXTENSION_CURRENT_PATTERN
TELEMETRY_TURN_PATTERN = TELEMETRY_TURN_CURRENT_PATTERN

# Logging
LOGGER_NAME: Final = "custom_components.vogels_motionmount"
LOG_RATE_LIMIT_WINDOW: Final = 60  # seconds
LOG_RATE_LIMIT_COUNT: Final = 10   # max logs per window
