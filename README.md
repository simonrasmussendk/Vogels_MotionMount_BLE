# Vogels MotionMount BLE Integration for Home Assistant

A Home Assistant custom integration that controls Vogels MotionMount TV mounts over Bluetooth Low Energy (BLE). Built as an alternative to the stock Home Assistant integration, which only supports the *Pro* variant — this integration talks to any MotionMount with Bluetooth by reverse-engineering the GATT characteristics directly.

> ⚠️ **Still evolving.** If auto-discovery picks the wrong characteristics on your mount, enable DEBUG logs and open an issue — the detailed discovery log makes it easy to map the correct UUIDs. You can also override them manually via the integration's Configure dialog.

## Features

- **Automatic BLE discovery** — characteristics are scored and assigned at setup so the integration works without hand-coded UUIDs for each firmware variant.
- **Full control surface** — extension target, signed turn target, all seven presets, and a stop button.
- **Bidirectional targets** — sliders show the current target reported by the mount and drive new ones.
- **Connection status sensor** — see at a glance whether the mount is `connected`, `connecting`, `disconnected`, or in an `error` state.
- **Signed turn range** — `-100 %` (fully left) ↔ `0 %` (centered) ↔ `+100 %` (fully right), matching the physical direction of the slider thumb.
- **Robust reconnect logic** — BLE writes automatically wake the connection and retry with a fresh client if the cached link has gone stale during idle.
- **Bounded shutdown** — the coordinator cannot hang Home Assistant during unload/reload, so the Configure dialog always returns in a reasonable time.
- **Diagnostics** — one-click diagnostics bundle via the device page for easy issue reporting.

## Installation

### HACS (recommended)

1. Add this repository to HACS as a custom repository (type: *Integration*).
2. Install **Vogels MotionMount BLE** from HACS.
3. Restart Home Assistant.
4. Go to *Settings → Devices & Services → Add Integration* and search for *Vogels MotionMount BLE*.

### Manual

1. Copy `custom_components/vogels_motionmount_ble/` into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to *Settings → Devices & Services → Add Integration* and search for *Vogels MotionMount BLE*.

## Setup

1. **Select a Bluetooth adapter** — relevant if you have multiple adapters or a Bluetooth proxy; otherwise accept the default.
2. **Pick your mount** — nearby BLE devices are listed; pick your MotionMount.
3. **Name it** — this becomes the device name shown in Home Assistant.
4. **Auto-discovery** — the integration connects, enumerates services, and auto-maps the needed characteristics. The result is logged at INFO level for sanity checking.

> The mount can only be controlled by one BLE client at a time. If the vendor app is connected, Home Assistant can't connect until the app releases the link.

## Entities

Every configured mount exposes the following entities:

### Number (target setpoints)

| Entity | Range | Description |
| --- | --- | --- |
| `number.<name>_extension_target` | `0 … 100 %` | `0 %` = against the wall, `100 %` = fully extended into the room. |
| `number.<name>_turn_target` | `-100 … 100 %` | `-100 %` = fully left, `0 %` = flush with the wall, `+100 %` = fully right. Sign matches the slider thumb direction; the integration inverts it to the device's internal convention transparently. |

Both sliders display the *current target* the mount is driving toward (as reported over telemetry).

### Sensor (live state)

| Entity | Description |
| --- | --- |
| `sensor.<name>_extension_current` | Live extension position (`0 … 100 %`). |
| `sensor.<name>_turn_current` | Live turn position, signed (`-100 … 100 %`). |
| `sensor.<name>_connection_status` | BLE link state: `disconnected`, `connecting`, `connected`, or `error`. Useful as a trigger for automations or Lovelace indicators. |

### Binary sensor

| Entity | Description |
| --- | --- |
| `binary_sensor.<name>_is_moving` | `on` while the mount is actively repositioning. |

### Buttons

| Entity | Description |
| --- | --- |
| `button.<name>_preset_0` … `button.<name>_preset_6` | Recall the seven factory/user preset positions, matching the IR remote. |
| `button.<name>_stop` | Stop immediately by commanding both targets to the current positions. |

## Configuration options

Open them via *Settings → Devices & Services → Vogels MotionMount BLE → ⚙ Configure*.

### General

- **Auto-disconnect timeout (seconds)** — idle time before the integration releases the BLE link to save power / free the radio for other clients. Set to `0` to stay connected. The mount is re-awakened automatically the next time you touch a slider or press a button.
- **Log level** — runtime log level for `custom_components.vogels_motionmount`. Useful for troubleshooting without editing `configuration.yaml`.
- **Debug raw data** — when enabled, raw BLE notification payloads are also logged. Noisy; use only for debugging.

### Advanced — UUID overrides

- **Nordic UART TX UUID** — telemetry notifications characteristic.
- **Extension Target UUID** — write target for extension position.
- **Turn Target UUID** — write target for turn position.
- **Preset UUID** — write target for preset index.

Leave these **empty** to use the UUIDs chosen by auto-discovery during initial setup. Fill them in only if auto-discovery picked wrong on your firmware and you've identified the correct ones from the DEBUG logs.

## Troubleshooting

### Sliders don't move the mount until you press a preset

This was a bug in releases prior to 1.4 — the write path trusted a cached "connected" flag that could go stale during idle. Upgrade to 1.4+ and the write path aggressively re-establishes the BLE connection when needed. If you still see it, enable DEBUG logging and open an issue with the logs.

### Connection drops or times out

- Verify the mount isn't already connected to the vendor app or another BLE client.
- Reduce distance / interference between the adapter and the mount.
- Increase the **Auto-disconnect timeout** (or set it to `0`) if your use-case requires always-on connectivity.
- Use the **Connection status** sensor to monitor the link — it updates in real time and can drive automations (e.g. a template light card showing BLE health).

### The Configure dialog used to hang — does it still?

As of 1.4+ the coordinator shutdown is bounded with a hard timeout, so reloading the entry from the options form returns promptly even if the BLE stack gets wedged. If you somehow still hit a hang, grab a diagnostics bundle and open an issue.

### Enabling detailed logs

Either use the **Log level** option in the Configure dialog, or add to `configuration.yaml`:

```yaml
logger:
  logs:
    custom_components.vogels_motionmount: debug
```

### Diagnostics bundle

*Settings → Devices & Services → Vogels MotionMount BLE → Download diagnostics* bundles:

- Redacted device info (adapter, device address redacted).
- Connection statistics (attempts, failures, last error).
- Latest telemetry and detected UUIDs.
- Current configuration (options + data overrides).

Attach this to any bug report.

## Contributing & feedback

Issues and pull requests are welcome on [GitHub](https://github.com/simonrasmussendk/vogels-motionmount-ble). If auto-discovery misidentifies a characteristic on your mount, a DEBUG-level setup log + diagnostics bundle is the fastest path to a fix.
