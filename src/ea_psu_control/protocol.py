"""Binary telegram framing for the EA PS2000B series serial protocol.

The PS2000B series (which includes the EA-PS 2084-10B) is controlled over a
USB-CDC serial link using a fixed binary telegram format, documented by
Elektro-Automatik in "Programming Guide PS2000B" and "object_list_ps2000b.pdf".
Every telegram has the shape::

    SD | DN | OBJ | DATA (0-16 bytes) | CS0 | CS1

- SD  (1 byte): start delimiter, encodes the telegram type and, when data is
  present, the data length.
- DN  (1 byte): device/channel node number (0 for single-channel units).
- OBJ (1 byte): object number being read or written (see object list PDF).
- DATA (0-16 bytes): payload, meaning depends on the object.
- CS0/CS1 (2 bytes): big-endian 16-bit sum of every preceding byte.

Responses use the same shape; OBJ echoes 0xFF followed by a status byte when
the device is reporting an error rather than data (see ERROR_CODES).
"""

from __future__ import annotations

from .exceptions import PSUCommunicationError, PSUDeviceError

# Telegram "type" nibble combined into the start delimiter byte.
TYPE_QUERY = 0x40   # host -> device: read an object
TYPE_SEND = 0xC0    # host -> device: write an object

_SD_BASE = 0x30
MIN_RESPONSE_LENGTH = 5  # SD, DN, OBJ, CS0, CS1 at minimum

# Status byte returned in place of data when OBJ == 0xFF in a response.
ERROR_CODES = {
    0x00: "OK: acknowledged",
    0x03: "communication error: checksum incorrect",
    0x04: "communication error: start delimiter incorrect",
    0x05: "communication error: wrong address / node",
    0x07: "communication error: object not defined",
    0x08: "user error: object length incorrect",
    0x09: "user error: access denied (device not in remote mode?)",
    0x0F: "user error: device is locked",
    0x30: "user error: upper limit exceeded",
    0x31: "user error: lower limit exceeded",
}


def build_telegram(telegram_type: int, node: int, obj: int, data: bytes = b"") -> bytes:
    """Construct a telegram to send to the device.

    ``telegram_type`` is TYPE_QUERY or TYPE_SEND. ``data`` is empty for a
    query and 1-2 bytes for a write, depending on the object.
    """
    telegram = bytearray()
    telegram.append(_SD_BASE + telegram_type)
    telegram.append(node)
    telegram.append(obj)
    if data:
        telegram.extend(data)
        telegram[0] += len(data) - 1  # SD encodes (length - 1) when data is present

    checksum = sum(telegram)
    telegram.append((checksum >> 8) & 0xFF)
    telegram.append(checksum & 0xFF)
    return bytes(telegram)


def parse_response(response: bytes) -> bytes:
    """Validate a response telegram and return its data payload (may be empty).

    Raises PSUCommunicationError on a short/malformed frame or bad checksum,
    and PSUDeviceError if the device reported an explicit error status.
    """
    if len(response) < MIN_RESPONSE_LENGTH:
        raise PSUCommunicationError(
            f"short response: got {len(response)} bytes, expected at least "
            f"{MIN_RESPONSE_LENGTH} (device not connected, wrong port, or wrong baud rate?)"
        )

    checksum = sum(response[:-2])
    expected = (response[-2] << 8) | response[-1]
    if checksum != expected:
        raise PSUCommunicationError(
            f"checksum mismatch: computed 0x{checksum:04x}, device sent 0x{expected:04x}"
        )

    obj = response[2]
    if obj == 0xFF:
        status = response[3]
        if status != 0x00:
            message = ERROR_CODES.get(status, f"unknown error (status 0x{status:02x})")
            raise PSUDeviceError(f"device rejected telegram: {message}")

    return bytes(response[3:-2])
