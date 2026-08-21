#!/usr/bin/env python3
"""Enable the PSU output at a fixed 24 V / 5 A current limit.

Usage: python enable_PSU.py [port]
Defaults to /dev/ttyACM0 if no port is given. The output is left enabled
when the script exits; run again with a different voltage/current in the
constants below, or call psu.disable_output() via the library, to change it.
"""

import sys

from ea_psu_control import DEFAULT_PORT, PS2000B

VOLTAGE = 24.0
CURRENT_LIMIT = 5.0


def main() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PORT

    with PS2000B(port) as psu:
        psu.set_current(CURRENT_LIMIT)  # set the current limit before raising voltage
        psu.set_voltage(VOLTAGE)
        psu.enable_output()

        state = psu.read_actual()
        mode = "CC" if state["constant_current"] else "CV"
        print(
            f"Output enabled: {state['voltage']:.3f} V, {state['current']:.3f} A ({mode} mode)"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
