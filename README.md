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

## Random shock sequence

A random 5-minute shock sequence found the `random_shock_seq_5min.txt` file. 
We use a constrained semi-Markov random schedule to remove predictable patterns while keeping shock exposure typical for Electric Shock Avoidance Assay. Four states: Upside (U), Downside (D), Both (A), None (N). Dwells: 7–15 s for U/D/N, 7–12 s for A. Quotas: U 31%, D 31%, A 12%, N 26%. Constraints: start with N; never A→A; place ≥1 N between any two A; keep Upside≈Downside; keep self-transitions low.

Why this setup: bees learn side avoidance quickly when contingencies are stable, often within minutes; short, jittered dwells prevent timing- or side-based prediction (Kirkerud et al., 2017; Marchal et al., 2019; Agarwal et al., 2011). Quotas match standard exposure so effects are not due to too little or too much stimulation. The structure also supports master–yoked logic: when shock is uncontrollable, avoidance degrades even with matched totals, so we hold totals constant to isolate controllability (Dinges et al., 2017). Using semi-Markov timing rather than fixed intervals removes periodic cues that animals can exploit (Daw & Touretzky, 2002).

References
Agarwal, M., Giannoni-Guzmán, M. A., Morales-Matos, C., Del Valle Díaz, R., Abramson, C. I., & Giray, T. (2011). Dopamine and octopamine influence avoidance learning of honey bees in a place preference assay. PLoS ONE, 6(9), e25371. 
Daw, N. D., & Touretzky, D. S. (2002). Dopamine and inference about timing. Advances in Neural Information Processing Systems, 14, 1–7. 
Princeton University
Dinges, C. W., et al. (2017). Studies of learned helplessness in honey bees (Apis mellifera ligustica). Journal of Experimental Psychology: Animal Learning and Cognition, 43(3), 147–158. 
Kirkerud, N. H., Mota, T., & Lind, O. (2017). Aversive learning of colored lights in walking honeybees. Frontiers in Behavioral Neuroscience, 11, 94. 
Marchal, P., et al. (2019). Inhibitory learning of phototaxis by honeybees in a passive avoidance paradigm. Journal of Experimental Biology, 222, jeb201475.

ChatGPT prompt to produce n seconds random shock sequence:
```
Task: Generate a `<TOTAL_SECONDS>`-second random shock sequence for a honey-bee ESA using a constrained semi-Markov process.
States and codes
- U = Upside
- D = Downside
- A = Both
- N = None
Hard requirements
1) Total duration = <TOTAL_SECONDS>.
2) Dwell bounds (s): U,D,N ∈ [7,15]; A ∈ [7,12]. Integer seconds only.
3) Exposure quotas scaled to <TOTAL_SECONDS> with ±max(2 s, 1%) tolerance:
   - U = 31% of total
   - D = 31% of total
   - A = 12% of total (keep within 10–15%)
   - N = 26% of total (never <20%)
4) Topology constraints:
   - Start with N.
   - No consecutive A.
   - At least one N between any two A.
   - Keep self-transitions low overall.
   - Keep U and D totals within ±2 s of each other.
Algorithm
- Build a constraint-compliant state skeleton.
- Assign lower-bound dwells, then allocate remaining seconds randomly without breaching item upper bounds or constraints. Resample if any check fails.
- Convert to contiguous durations that sum exactly to <TOTAL_SECONDS>.
Output format (strict)
- Return ONLY a tab-delimited table with EXACTLY two columns in this order and header row:
state	duration_s
- No extra text, notes, or summaries. No code fences. No totals row. One line per state in sequence.
```

---

## Contact

Author: Babur Erdem • [ebabur@metu.edu.tr](mailto:ebabur@metu.edu.tr)

