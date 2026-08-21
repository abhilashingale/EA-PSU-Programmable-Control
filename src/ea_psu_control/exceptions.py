"""Exceptions raised by the EA PS2000B control API."""


class PSUError(Exception):
    """Base class for all errors raised by this package."""


class PSUCommunicationError(PSUError):
    """Raised when a response is missing, too short, or fails checksum verification."""


class PSUDeviceError(PSUError):
    """Raised when the device itself reports an error status for a telegram."""


class PSULimitError(PSUError):
    """Raised when a requested setpoint falls outside the device's nominal rating."""
