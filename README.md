# EA-PSU-Programmable-Control
Monorepo for Eletro-Automatik's Power Supply Control Utilities

## ea_psu_control

A basic control API for Elektro-Automatik PS 2000B series power supplies,
including the EA-PS 2084-10B, over their USB-CDC serial interface (default
`/dev/ttyACM0` on Linux).

It implements the PS2000B binary telegram protocol (`SD | DN | OBJ | DATA |
CS0 | CS1`, per Elektro-Automatik's "Programming Guide PS2000B" and
`object_list_ps2000b.pdf`) directly over `pyserial` — no vendor software
required.

### Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
```

On Linux, your user needs access to the serial device:

```bash
sudo usermod -aG dialout $USER   # then log out/in
```

### Usage

```python
from ea_psu_control import PS2000B

with PS2000B("/dev/ttyACM0") as psu:
    print(psu.identify())

    psu.set_current(0.5)      # amps, set the current limit before voltage
    psu.set_voltage(5.0)      # volts
    psu.enable_output()

    print(psu.read_actual())  # measured voltage/current + status flags

    psu.disable_output()
# remote control is released automatically on exit; output state is left as-is
```

See `examples/basic_usage.py` for a runnable version.

### API surface

- `identify()` — device type, serial number, article number, firmware version, ratings
- `set_voltage(v)` / `get_voltage_setpoint()`
- `set_current(i)` / `get_current_setpoint()`
- `set_ovp(v)` / `get_ovp()`, `set_ocp(i)` / `get_ocp()`
- `enable_output()` / `disable_output()` / `get_control_state()`
- `set_remote(bool)` — required before the device will accept setpoint/output writes
- `acknowledge_alarm()` — clears a tripped OVP/OCP/OPP/OTP alarm
- `read_actual()` / `read_setpoints()` — live measured values and status flags

`set_voltage`/`set_current` raise `PSULimitError` locally if the request is
outside the unit's nominal rating (read from the device on connect); the
device itself is still the final authority and returns a `PSUDeviceError`
for anything it rejects (e.g. limits, alarms, or writes attempted while not
in remote mode).

### Safety notes

- The device must be in **remote** mode to accept setpoint or output-control
  writes; the `with PS2000B(...)` context manager handles this for you.
- Always set the current limit before raising the voltage setpoint on a
  live load.
- The output is **not** automatically disabled when the context manager
  exits — only remote control is released. Call `disable_output()`
  explicitly if you want the supply off at the end of a script.

### Tests

```bash
.venv/bin/pip install pytest
.venv/bin/pytest
```

Tests cover telegram framing, checksums, percent/real-value conversion, and
the response-sizing/pacing logic in `_transfer` (via a fake serial object) —
no hardware connection is required to run them.

### Polling / logging rate

`read_actual()` / `read_setpoints()` are capped at **~20 Hz (50 ms/sample)**.
That's not a serial-line limit — it's Elektro-Automatik's documented minimum
spacing between telegrams, which `_transfer` enforces explicitly. Each call
also reads only the exact number of bytes a response implies, instead of
blocking on an oversized buffer, so the achieved rate is that 50 ms floor
itself rather than an accidental multiple of it. Measured sustained ~19.8 Hz
against a real EA-PS 2084-10B.
