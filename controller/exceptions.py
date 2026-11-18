"""Typed exception hierarchy for the Holiday Bright Lights controller."""


class ControllerError(Exception):
    """Base exception for all controller errors."""


class ValidationError(ControllerError, ValueError):
    """Raised when caller arguments violate protocol or hardware bounds."""


class UnsupportedCapabilityError(ControllerError, NotImplementedError):
    """Raised when requesting an operation unsupported or unverified on hardware."""


class TransportError(ControllerError, OSError):
    """Raised on network/BLE connection, timeout, or write failures."""


class ProtocolError(ControllerError):
    """Raised when received packets are malformed or fail checksum checks."""
