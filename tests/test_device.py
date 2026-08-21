import time

from ea_psu_control.ps2000b import MIN_COMMAND_INTERVAL, PS2000B


class _FakeSerial:
    """Minimal stand-in for pyserial's Serial: queues one canned response
    per write() call, and hands it back in whatever chunk sizes read() asks
    for - just like a real serial port would."""

    def __init__(self, responses):
        self._pending = b""
        self._responses = list(responses)
        self.read_sizes = []

    def reset_input_buffer(self):
        pass

    def write(self, data):
        self._pending += self._responses.pop(0)

    def read(self, size):
        self.read_sizes.append(size)
        chunk, self._pending = self._pending[:size], self._pending[size:]
        return chunk

    @property
    def is_open(self):
        return True

    def close(self):
        pass


def _framed(obj: int, data: bytes) -> bytes:
    header = bytes([0x30, 0x00, obj]) + data
    checksum = sum(header)
    return header + bytes([(checksum >> 8) & 0xFF, checksum & 0xFF])


def _make_psu(responses) -> PS2000B:
    psu = PS2000B.__new__(PS2000B)  # bypass __init__: no real serial port needed
    psu.node = 0
    psu._serial = _FakeSerial(responses)
    psu._last_transfer_at = None
    psu.nominal_voltage = 84.0
    psu.nominal_current = 10.0
    return psu


def test_read_uses_exact_response_length_not_a_fixed_buffer():
    response = _framed(71, bytes([0x03, 0x01, 0x28, 0x00, 0x00, 0x00]))
    psu = _make_psu([response])

    data = psu._read(71, expected_data_len=6)

    assert data == bytes([0x03, 0x01, 0x28, 0x00, 0x00, 0x00])
    # header (3) then exactly data+checksum (8) - never the old fixed 128
    assert psu._serial.read_sizes == [3, 8]


def test_error_response_is_recognized_from_header_alone():
    response = _framed(0xFF, bytes([0x30]))  # 0x30 = upper limit exceeded
    psu = _make_psu([response])

    from ea_psu_control.exceptions import PSUDeviceError

    try:
        psu._read(50, expected_data_len=2)
        assert False, "expected PSUDeviceError"
    except PSUDeviceError:
        pass

    # even though expected_data_len=2, an error frame is read as 1 status byte
    assert psu._serial.read_sizes == [3, 3]


def test_consecutive_transfers_are_paced_to_the_minimum_interval():
    ok = _framed(71, bytes(6))
    psu = _make_psu([ok, ok])

    start = time.monotonic()
    psu._read(71, expected_data_len=6)
    psu._read(71, expected_data_len=6)
    elapsed = time.monotonic() - start

    assert elapsed >= MIN_COMMAND_INTERVAL
