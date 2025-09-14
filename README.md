# Vogels MotionMount BLE Integration for Home Assistant

Created this integration as I was frustrated that the original integration in Home Assistant only supported the MotionMount with Pro extension. It's been built by reverse engineering the Bluetooth connection from the mount.

Testing of the mappings are still under development, so if you have any issues please enable debugging and share your logs to help me map Bluetooth discoveries correctly.

A comprehensive Home Assistant custom integration for controlling Vogels MotionMount devices via Bluetooth Low Energy (BLE) with automatic characteristic discovery.

## Features

- **Automatic BLE Discovery**: Intelligent characteristic discovery that works on Bluetooth enabledMotionMount models
- **Full BLE Integration**: Connect to Vogels MotionMount devices using Bleak and Home Assistant's Bluetooth integration
- **Multiple Entities**: Control extension and turn targets, monitor current positions and movement state
- **7 Preset Support**: Quick access to all preset positions (0-6) matching the remote control functionality
- **Robust Connection Management**: Exponential backoff reconnection, auto-disconnect, and connection health monitoring
- **Advanced Configuration**: Runtime configurable logging levels and connection timeouts
- **Comprehensive Diagnostics**: Built-in diagnostics endpoint for troubleshooting
- **Home Assistant Best Practices**: Config flow, options flow, proper entity categories, and device grouping

## Installation

### HACS (Recommended)

1. Add this repository to HACS as a custom repository
2. Install "Vogels MotionMount BLE" from HACS
3. Restart Home Assistant
4. Add the integration via Settings → Devices & Services → Add Integration

### Manual Installation

1. Copy the `custom_components/vogels_motionmount` directory to your Home Assistant `custom_components` directory
2. Restart Home Assistant
3. Add the integration via Settings → Devices & Services → Add Integration

## Setup

### Initial Configuration

1. **Select Bluetooth Adapter**: Choose which Bluetooth adapter to use (important on multi-adapter systems)
2. **Device Discovery**: The integration will scan for nearby BLE devices
3. **Device Validation**: Select your MotionMount and provide a friendly name
4. **Automatic Discovery**: The integration will auto-discover and map the correct GATT characteristics for your specific device

### Device Preparation

Before setup, ensure your Vogels MotionMount is:

- Powered on and in pairing mode
- Within Bluetooth range (typically 10 meters)
- Not connected to another device (only one controller can connect at a time)

**Factory Reset Instructions:**
1. Power off the MotionMount
2. Hold the reset button while powering on
3. Default PIN after reset is `0000`
4. The device will be discoverable for pairing

## Entities

The integration creates the following entities for each configured MotionMount:

### Number Entities
- **Extension Target** (`number.vogels_extension_target`): Set extension position (0-100%)
- **Turn Target** (`number.vogels_turn_target`): Set turn position (0-100%)

### Sensor Entities
- **Extension Current** (`sensor.vogels_extension_current`): Current extension position
- **Turn Current** (`sensor.vogels_turn_current`): Current turn position

### Binary Sensor Entities
- **Is Moving** (`binary_sensor.vogels_is_moving`): Whether the mount is currently moving

### Button Entities
- **Preset 0** (`button.vogels_preset_0`): Activate preset position 0
- **Preset 1** (`button.vogels_preset_1`): Activate preset position 1
- **Preset 2** (`button.vogels_preset_2`): Activate preset position 2
- **Preset 3** (`button.vogels_preset_3`): Activate preset position 3
- **Preset 4** (`button.vogels_preset_4`): Activate preset position 4
- **Preset 5** (`button.vogels_preset_5`): Activate preset position 5
- **Preset 6** (`button.vogels_preset_6`): Activate preset position 6
- **Stop** (`button.vogels_stop`): Emergency stop (sets targets to current positions)

## Configuration Options

Access advanced options via Settings → Devices & Services → Vogels MotionMount → Configure:

### Connection Settings
- **Auto-disconnect Timeout**: Automatically disconnect after inactivity (0 to disable)
- **Bluetooth Adapter**: Change the Bluetooth adapter used for connection

### Logging Settings
- **Log Level**: Set logging verbosity (DEBUG, INFO, WARNING, ERROR)
- **Debug Raw Data**: Enable raw telemetry payload logging (DEBUG level only)

### Advanced Settings (UUID Overrides)
- **Nordic UART TX UUID**: Override auto-discovered telemetry characteristic
- **Extension Target UUID**: Override auto-discovered extension target characteristic
- **Turn Target UUID**: Override auto-discovered turn target characteristic
- **Preset UUID**: Override auto-discovered preset characteristic

*Note: UUIDs are automatically discovered during setup. Manual overrides are only needed for troubleshooting or special cases.*

## Troubleshooting

### Connection Issues

1. **Device Not Found**: Ensure the MotionMount is powered on and in range
2. **Connection Timeout**: Check for interference from other Bluetooth devices
3. **Device Busy**: Only one controller can connect at a time - disconnect other apps

### Logging

Enable DEBUG logging for detailed auto-discovery and connection information:

```yaml
logger:
  logs:
    custom_components.vogels_motionmount: debug
```

**For Auto-Discovery Issues**: Set logging to DEBUG level to see detailed characteristic discovery and mapping information. This helps identify if the integration is correctly finding and assigning UUIDs for your specific device model.

### Diagnostics

The integration provides comprehensive diagnostics via Settings → Devices & Services → Vogels MotionMount → Download Diagnostics. This includes:

- Connection statistics and error history
- Current telemetry values
- Configuration details
- Bluetooth adapter information

### Common Solutions

- **Frequent Disconnections**: Increase auto-disconnect timeout or disable it
- **Slow Response**: Check Bluetooth signal strength and reduce interference
- **Missing Entities**: Verify device validation passed during setup
- **Permission Errors**: Ensure Home Assistant has Bluetooth permissions

## Technical Details

### Automatic Characteristic Discovery

The integration uses intelligent auto-discovery to identify the correct GATT characteristics for your specific MotionMount model:

- **Multi-Criteria Analysis**: Uses BLE properties, current values, and UUID patterns to identify characteristics
- **Value-Based Heuristics**: Distinguishes extension vs turn targets based on their current value ranges
- **Scoring System**: Prioritizes characteristics using multiple factors for accurate mapping
- **Fallback Protection**: Graceful handling when characteristics can't be read during discovery

### Discovered Characteristics

The integration automatically finds and maps:

- **Nordic UART Service TX**: Telemetry notifications (notify-only characteristic)
- **Extension Target**: Write extension target (read+write+notify, typically higher values 0-650mm)
- **Turn Target**: Write turn target (read+write+notify, typically lower values -90°/+90°)
- **Preset Control**: Write preset index (write-only characteristic, excluding Nordic UART RX)

### Telemetry Format

The device sends ASCII telemetry via Nordic UART:

```
mount/extension/current = 50
mount/turn/current = 75
mount/isMoving = 1
```

### Connection Management

- **Exponential Backoff**: Automatic reconnection with increasing delays
- **Connection Health**: Heartbeat monitoring via telemetry subscription
- **Rate Limited Logging**: Prevents log spam during connection issues
- **Graceful Shutdown**: Clean disconnection on Home Assistant stop

## Development

### Code Quality

The integration follows Home Assistant development standards:
- Type hints throughout
- Async/await patterns
- Proper error handling
- Comprehensive logging
- Automatic characteristic discovery

## Support

For issues and feature requests, please use the GitHub repository issue tracker.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
