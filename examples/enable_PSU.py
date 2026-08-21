#!/usr/bin/env python3
"""Enable the PSU output at a caller-specified voltage and current limit.

Usage: python examples/enable_PSU.py --volt 24 --amp 5 [--port /dev/ttyACM0]

Both --volt and --amp are required; the script refuses to power on the
output without an explicit setpoint. Prompts for confirmation before
touching the hardware, and leaves the output enabled when it exits.
"""

import argparse
import sys

from ea_psu_control import DEFAULT_PORT, PS2000B


class _SafeArgumentParser(argparse.ArgumentParser):
    """Replaces argparse's usage/traceback-style error output with a plain,
    hardware-appropriate message: don't power on anything if the arguments
    weren't understood."""

    def error(self, message):
        print("Voltage & Current Limits not configured!")
        print("Exiting power-on for safety reasons!")
        raise SystemExit(1)


def parse_args() -> argparse.Namespace:
    parser = _SafeArgumentParser(
        description="Enable the PSU output at a configured voltage and current limit.",
        usage="enable_PSU.py --volt VOLT --amp AMP [--port PORT]",
    )
    parser.add_argument("--volt", type=float, default=None, help="Voltage setpoint, in volts")
    parser.add_argument("--amp", type=float, default=None, help="Current limit, in amps")
    parser.add_argument("--port", default=DEFAULT_PORT, help=f"Serial port (default: {DEFAULT_PORT})")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.volt is None or args.amp is None:
        print("Voltage & Current Limits not configured!")
        print("Exiting power-on for safety reasons!")
        return 1

    print("####### Safety Warning ######")
    print("Starting PSU....")
    answer = input(
        f"Are you sure you want to set {args.volt} Volt and {args.amp} Amp for the session? [y/N]: "
    )
    if answer.strip().lower() not in ("y", "yes"):
        print("Aborted - PSU output was not enabled.")
        return 1

    with PS2000B(args.port) as psu:
        psu.set_current(args.amp)  # set the current limit before raising voltage
        psu.set_voltage(args.volt)
        psu.enable_output()

        state = psu.read_actual()
        mode = "CC" if state["constant_current"] else "CV"
        print(
            f"Output enabled: {state['voltage']:.3f} V, {state['current']:.3f} A ({mode} mode)"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
