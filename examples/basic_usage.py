#!/usr/bin/env python3
"""Basic usage example for the EA-PS 2084-10B (or any PS2000B-series unit).

Connects, prints identity/rating info, sets a low, safe voltage/current
limit, briefly enables the output, reads back the measurement, then turns
the output off again and releases remote control.

Run with the output disconnected or connected to a load you've confirmed
can safely take a few volts before trying this against real equipment.
"""

import sys
import time

from ea_psu_control import DEFAULT_PORT, PS2000B


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT

    with PS2000B(port) as psu:
        info = psu.identify()
        print(f"Connected to {info['device_type']} (serial {info['serial_number']})")
        print(f"Rating: {info['nominal_voltage']} V / {info['nominal_current']} A")

        psu.set_current(0.5)
        psu.set_voltage(5.0)
        psu.set_ovp(psu.nominal_voltage)
        psu.set_ocp(psu.nominal_current)

        psu.enable_output()
        time.sleep(0.5)
        measurement = psu.read_actual()
        print(f"Measured: {measurement['voltage']:.3f} V, {measurement['current']:.3f} A")
        psu.disable_output()

    return 0


if __name__ == "__main__":
    sys.exit(main())
