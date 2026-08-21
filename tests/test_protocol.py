import pytest

from ea_psu_control import protocol
from ea_psu_control.exceptions import PSUCommunicationError, PSUDeviceError


def test_build_telegram_query_has_no_data():
    telegram = protocol.build_telegram(protocol.TYPE_QUERY, node=0, obj=2)
    assert telegram[0] == 0x30 + protocol.TYPE_QUERY
    assert telegram[1] == 0
    assert telegram[2] == 2
    assert len(telegram) == 5  # SD, DN, OBJ, CS0, CS1


def test_build_telegram_checksum_matches_manual_sum():
    telegram = protocol.build_telegram(protocol.TYPE_SEND, node=0, obj=50, data=b"\x64\x00")
    checksum = sum(telegram[:-2])
    assert telegram[-2] == (checksum >> 8) & 0xFF
    assert telegram[-1] == checksum & 0xFF


def test_build_telegram_encodes_data_length_in_sd():
    one_byte = protocol.build_telegram(protocol.TYPE_SEND, node=0, obj=54, data=b"\x01")
    two_byte = protocol.build_telegram(protocol.TYPE_SEND, node=0, obj=54, data=b"\x01\x02")
    assert one_byte[0] == 0x30 + protocol.TYPE_SEND
    assert two_byte[0] == 0x30 + protocol.TYPE_SEND + 1


def _with_checksum(header_and_data: bytes) -> bytes:
    checksum = sum(header_and_data)
    return header_and_data + bytes([(checksum >> 8) & 0xFF, checksum & 0xFF])


def test_parse_response_returns_data_payload():
    response = _with_checksum(bytes([0x30, 0x00, 0x02]) + b"\x42\x28\x00\x00")
    assert protocol.parse_response(response) == b"\x42\x28\x00\x00"


def test_parse_response_rejects_short_frame():
    with pytest.raises(PSUCommunicationError):
        protocol.parse_response(b"\x30\x00")


def test_parse_response_rejects_bad_checksum():
    response = bytes([0x30, 0x00, 0x02, 0xAA, 0xAA])
    with pytest.raises(PSUCommunicationError):
        protocol.parse_response(response)


def test_parse_response_raises_on_device_error():
    response = _with_checksum(bytes([0x30, 0x00, 0xFF, 0x30]))  # 0x30 = upper limit exceeded
    with pytest.raises(PSUDeviceError):
        protocol.parse_response(response)


def test_parse_response_treats_status_zero_as_ok():
    response = _with_checksum(bytes([0x30, 0x00, 0xFF, 0x00]))
    assert protocol.parse_response(response) == b"\x00"
