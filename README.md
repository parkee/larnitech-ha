# Larnitech Smart Home Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant integration for [Larnitech](https://www.larnitech.com/) smart home controllers (DE-MG, Metaforsa).

Communicates via the controller's WebSocket and HTTP JSON API for real-time device control and status monitoring.

## Features

- Real-time status updates via WebSocket (local push)
- Full AC control (power, mode, temperature, fan speed, vanes)
- Lighting control (on/off, dimmer brightness)
- Blinds/covers with position and tilt
- Climate valve-heating (on/off, read temperature/setpoint)
- IR remote control with learned signals and raw hex transmission
- Water valve control
- Script execution
- Scene/light scheme activation
- Temperature, humidity, illuminance, current, voltage sensors
- Motion, door, leak binary sensors
- Weather/pressure virtual sensors

## Supported Devices

| HA Platform | Larnitech Device Types |
|-------------|----------------------|
| Light | lamp, dimmer-lamp |
| Climate | AC (full control), valve-heating (on/off) |
| Cover | blinds, jalousie, gate |
| Sensor | temperature, humidity, illumination, current, voltage, virtual, climate-control |
| Binary Sensor | motion, door, leak |
| Valve | valve (water) |
| Remote | remote-control (learned IR), ir-transmitter (raw IR) |
| Button | script |
| Scene | light-scheme |

## Installation via HACS

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/parkee/larnitech-ha` with category **Integration**
4. Click **Install**
5. Restart Home Assistant
6. Go to **Settings → Devices & Services → Add Integration → Larnitech**
7. Enter your controller's IP address and API key

## Configuration

| Field | Description | Default |
|-------|-------------|---------|
| Host | IP address of your Larnitech controller | — |
| API Key | API key from LT Setup → Plugins → API → Configure | — |
| WebSocket Port | Seasocks WebSocket port | 8080 |
| HTTP API Port | HTTP JSON API port | 8888 |

## Requirements

- Larnitech controller (DE-MG or Metaforsa) on your local network
- API plugin enabled in LT Setup
- Home Assistant 2026.3.0 or later
