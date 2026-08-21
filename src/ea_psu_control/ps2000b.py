"""Control API for Elektro-Automatik PS 2000B series power supplies.

Covers single-channel units such as the EA-PS 2084-10B over their USB-CDC
serial interface (shows up as /dev/ttyACM0 on Linux). Object numbers and
telegram semantics follow Elektro-Automatik's "object_list_ps2000b.pdf" /
"Programming Guide PS2000B".
"""

from __future__ import annotations

import struct
from typing import Optional

import serial

from . import protocol
from .exceptions import PSULimitError

# Object numbers, per object_list_ps2000b.pdf.
OBJ_DEVICE_TYPE = 0
OBJ_SERIAL_NUMBER = 1
OBJ_NOMINAL_VOLTAGE = 2
OBJ_NOMINAL_CURRENT = 3
OBJ_NOMINAL_POWER = 4
OBJ_ARTICLE_NUMBER = 6
OBJ_MANUFACTURER = 8
OBJ_FW_VERSION = 9
OBJ_DEVICE_CLASS = 19
OBJ_OVP = 38
OBJ_OCP = 39
OBJ_VOLTAGE_SETPOINT = 50
OBJ_CURRENT_SETPOINT = 51
OBJ_CONTROL = 54
OBJ_ACTUAL = 71
OBJ_SETPOINTS = 72

DEVICE_CLASSES = {
    0x0010: "PS 2000 B Single",
    0x0018: "PS 2000 B Triple",
}

# Setpoints/limits are transferred as a 0-25600 integer representing 0-100.00%
# of the device's nominal rating (see Programming Guide, "percent value").
_PERCENT_SCALE = 25600.0

DEFAULT_PORT = "/dev/ttyACM0"


def _percent_to_real(nominal: float, percent_value: float) -> float:
    return (nominal * percent_value) / _PERCENT_SCALE


def _real_to_percent(nominal: float, value: float) -> int:
    return int(round((_PERCENT_SCALE * value) / nominal))


class PS2000B:
    """A connection to one EA PS2000B-series power supply.

    Not thread-safe: one telegram is in flight on the serial link at a time.
    Use as a context manager to put the device into remote mode on entry and
    return it to local (front-panel) control on exit; the output state is
    left untouched on exit, so call `disable_output()` explicitly if you
    want the supply off when your script ends.
    """

    def __init__(
        self,
        port: str = DEFAULT_PORT,
        node: int = 0,
        baudrate: int = 115200,
        timeout: float = 0.1,
    ) -> None:
        self.node = node
        self._serial = serial.Serial(
            port,
            baudrate=baudrate,
            parity=serial.PARITY_ODD,
            timeout=timeout,
        )
        # Setpoints are percent-of-nominal, so we need these to convert.
        self.nominal_voltage = self._read_float(OBJ_NOMINAL_VOLTAGE)
        self.nominal_current = self._read_float(OBJ_NOMINAL_CURRENT)
        self.nominal_power = self._read_float(OBJ_NOMINAL_POWER)

    def __enter__(self) -> "PS2000B":
        self.set_remote(True)
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.set_remote(False)
        self.close()

    def close(self) -> None:
        if self._serial.is_open:
            self._serial.close()

    # -- low-level transfer -------------------------------------------------

    def _transfer(self, telegram_type: int, obj: int, data: bytes = b"") -> bytes:
        telegram = protocol.build_telegram(telegram_type, self.node, obj, data)
        self._serial.reset_input_buffer()
        self._serial.write(telegram)
        response = self._serial.read(128)
        return protocol.parse_response(response)

    def _read(self, obj: int) -> bytes:
        return self._transfer(protocol.TYPE_QUERY, obj)

    def _read_str(self, obj: int) -> str:
        return self._read(obj).decode("ascii", errors="replace").strip("\x00").strip()

    def _read_float(self, obj: int) -> float:
        return struct.unpack(">f", self._read(obj))[0]

    def _read_uint16(self, obj: int) -> int:
        return struct.unpack(">H", self._read(obj))[0]

    def _write_uint16(self, obj: int, value: int) -> None:
        data = bytes([(value >> 8) & 0xFF, value & 0xFF])
        self._transfer(protocol.TYPE_SEND, obj, data)

    def _write_control(self, mask: int, data: int) -> None:
        self._transfer(protocol.TYPE_SEND, OBJ_CONTROL, bytes([mask, data]))

    # -- identification -------------------------------------------------

    def identify(self) -> dict:
        """Return static device identity/rating info."""
        class_code = self._read_uint16(OBJ_DEVICE_CLASS)
        return {
            "device_type": self._read_str(OBJ_DEVICE_TYPE),
            "serial_number": self._read_str(OBJ_SERIAL_NUMBER),
            "article_number": self._read_str(OBJ_ARTICLE_NUMBER),
            "manufacturer": self._read_str(OBJ_MANUFACTURER),
            "firmware_version": self._read_str(OBJ_FW_VERSION),
            "device_class": DEVICE_CLASSES.get(class_code, f"unknown (0x{class_code:04x})"),
            "nominal_voltage": self.nominal_voltage,
            "nominal_current": self.nominal_current,
            "nominal_power": self.nominal_power,
        }

    # -- remote/output control -------------------------------------------------

    def set_remote(self, enabled: bool = True) -> None:
        """Enable (or release) remote control. Required before changing setpoints."""
        self._write_control(0x10, 0x10 if enabled else 0x00)

    def enable_output(self) -> None:
        self._write_control(0x01, 0x01)

    def disable_output(self) -> None:
        self._write_control(0x01, 0x00)

    def acknowledge_alarm(self) -> None:
        """Clear a tripped OVP/OCP/OPP/OTP alarm so the output can be re-enabled."""
        self._write_control(0x0A, 0x0A)

    def get_control_state(self) -> dict:
        data = self._read(OBJ_CONTROL)
        return {
            "remote": bool(data[0] & 0x01),
            "output_on": bool(data[1] & 0x01),
        }

    # -- setpoints -------------------------------------------------

    def set_voltage(self, volts: float) -> None:
        """Set the output voltage setpoint, in volts."""
        if not 0 <= volts <= self.nominal_voltage:
            raise PSULimitError(
                f"requested voltage {volts} V is outside the device's rating "
                f"of 0-{self.nominal_voltage} V"
            )
        self._write_uint16(OBJ_VOLTAGE_SETPOINT, _real_to_percent(self.nominal_voltage, volts))

    def set_current(self, amps: float) -> None:
        """Set the output current limit, in amps."""
        if not 0 <= amps <= self.nominal_current:
            raise PSULimitError(
                f"requested current {amps} A is outside the device's rating "
                f"of 0-{self.nominal_current} A"
            )
        self._write_uint16(OBJ_CURRENT_SETPOINT, _real_to_percent(self.nominal_current, amps))

    def set_ovp(self, volts: float) -> None:
        """Set the over-voltage-protection threshold, in volts."""
        if volts < 0:
            raise PSULimitError(f"OVP threshold {volts} V cannot be negative")
        self._write_uint16(OBJ_OVP, _real_to_percent(self.nominal_voltage, volts))

    def set_ocp(self, amps: float) -> None:
        """Set the over-current-protection threshold, in amps."""
        if amps < 0:
            raise PSULimitError(f"OCP threshold {amps} A cannot be negative")
        self._write_uint16(OBJ_OCP, _real_to_percent(self.nominal_current, amps))

    def get_voltage_setpoint(self) -> float:
        return _percent_to_real(self.nominal_voltage, self._read_uint16(OBJ_VOLTAGE_SETPOINT))

    def get_current_setpoint(self) -> float:
        return _percent_to_real(self.nominal_current, self._read_uint16(OBJ_CURRENT_SETPOINT))

    def get_ovp(self) -> float:
        return _percent_to_real(self.nominal_voltage, self._read_uint16(OBJ_OVP))

    def get_ocp(self) -> float:
        return _percent_to_real(self.nominal_current, self._read_uint16(OBJ_OCP))

    # -- measurements -------------------------------------------------

    def read_actual(self) -> dict:
        """Read live measured voltage/current and status flags (object 71)."""
        return self._decode_measurement(self._read(OBJ_ACTUAL))

    def read_setpoints(self) -> dict:
        """Read the device's own view of the current setpoints (object 72)."""
        return self._decode_measurement(self._read(OBJ_SETPOINTS))

    def _decode_measurement(self, data: bytes) -> dict:
        status0, status1 = data[0], data[1]
        raw_voltage = (data[2] << 8) | data[3]
        raw_current = (data[4] << 8) | data[5]
        return {
            "remote": bool(status0 & 0x03),
            "output_on": bool(status1 & 0x01),
            "constant_current": bool(status1 & 0x06),
            "constant_voltage": not bool(status1 & 0x06),
            "ovp_tripped": bool(status1 & 0x10),
            "ocp_tripped": bool(status1 & 0x20),
            "opp_tripped": bool(status1 & 0x40),
            "otp_tripped": bool(status1 & 0x80),
            "voltage": _percent_to_real(self.nominal_voltage, raw_voltage),
            "current": _percent_to_real(self.nominal_current, raw_current),
        }
