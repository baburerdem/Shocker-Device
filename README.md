# Shocker-Device
Shock Device Controller for Electric Shock Avoidance Assay
Constant-current avoidance rig controller. Host GUI drives MOSFET switches on an Arduino with tight, host-side timing. Modes: Upside (U), Downside (D), All (A), None (N), and host-driven Random.

---

## Modules

### Arduino endpoint

Minimal serial listener. Parses newline-terminated commands and switches two digital outputs.
File: `ShockerDevice_Arduino.ino`

### Shock GUI (PySide6)

Compact control panel. Design phases, load random schedule, run, live log, save/clear log, manual mode when idle.
Files: 
`ShockerDevice_Windows.py` (Windows compatible)
`ShockerDevice_Ubuntu.py` (Ubuntu compatible)

---

## Quick Start

### Requirements

* Python 3.9+
* Packages: `PySide6`, `pyserial`, `numpy`
* OS: Ubuntu 22.04+ or Windows 10+

### Arduino

1. Board: Uno/Nano.
2. Flash `ShockerDevice_Arduino.ino` at 115200 baud.
3. Wiring:

   * `PIN_UP` = D2 → gate driver for Upside MOSFET
   * `PIN_DN` = D4 → gate driver for Downside MOSFET
   * Common GND between Arduino and power stage

### Run

```bash
python ShockerDevice_Windows.py
```

1. Pick serial port (`/dev/ttyACM*` or `COMx`). Connect.
2. Add phases: Name, `mm:ss`, and Side (U/D/A/N/Random).
3. If any phase = Random, click **Load Random** and select file.
4. Enter experiment name. Start.

---

## Usage

* **Manual controls**: Upside, Downside, All, None. Enabled only when idle. Each manual action beeps 3 s.
* **Run timing**: The host thread holds each state for the full phase duration. Random phases loop the random file steps until the phase budget is consumed.
* **Beep**: 3 s tone at start and between phases, and on manual actions.

### Random file format

Plain text or CSV. Two columns: `state duration_seconds`. Header optional.

```
# state duration
U 20
A 7
N 5
D 13
```

Notes:

* States: `U`, `D`, `A`, `N`
* Durations are seconds (ints or floats).
* Consecutive identical states are merged.
* During a Random phase, these steps repeat in order until the phase time ends.

### Serial protocol

Newline-terminated commands from host:

```
MODE=U   # Upside ON
MODE=D   # Downside ON
MODE=A   # Both ON
MODE=N   # Both OFF
PING     # → PONG
X        # Emergency OFF → OK
```

Arduino replies `OK` for valid `MODE=*`, `PONG` for `PING`.

### Logs

Live log shows timestamps, phase headers, state holds, random steps, and finish markers. Use **Save Log** to export `.txt`.

---

## OS notes

### Ubuntu

* Add user to dialout: `sudo usermod -a -G dialout $(whoami)` then re-login.
* Ports appear as `/dev/ttyACM*` or `/dev/ttyUSB*`.

### Windows

* Ports appear as `COMx`. Close Arduino Serial Monitor before running GUI.
* Optional: install CH340/FTDI driver if needed.

---

## Safety

This code only switches MOSFETs. You are responsible for electrical safety, isolation, compliance, and animal protocols. Validate with a dummy load first.

---

## Contact

Author: Babur Erdem • [ebabur@metu.edu.tr](mailto:ebabur@metu.edu.tr)

