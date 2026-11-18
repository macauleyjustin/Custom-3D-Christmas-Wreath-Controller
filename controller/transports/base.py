"""Abstract base class and telemetry stats for controller transports."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import Optional

from controller.diagnostics.capture import PacketCaptureLog


@dataclass
class TransportStats:
    """Live connection quality and I/O counters."""

    transport_type: str
    endpoint: str
    connected: bool = False
    tx_packets: int = 0
    rx_packets: int = 0
    tx_bytes: int = 0
    rx_bytes: int = 0
    reconnects: int = 0
    errors: int = 0
    last_latency_ms: float | None = None
    avg_latency_ms: float | None = None
    last_error: str | None = None


class BaseTransport(abc.ABC):
    """Abstract interface implemented by Wi-Fi, BLE, and Simulator transports."""

    def __init__(self, capture: Optional[PacketCaptureLog] = None) -> None:
        self.capture = capture if capture is not None else PacketCaptureLog()

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Transport identifier ('wifi', 'ble', or 'simulator')."""

    @property
    @abc.abstractmethod
    def endpoint(self) -> str:
        """Human-readable endpoint identifier."""

    @property
    @abc.abstractmethod
    def is_connected(self) -> bool:
        """Whether the transport currently holds an active link."""

    @abc.abstractmethod
    def connect(self) -> None:
        """Establish transport connection."""

    @abc.abstractmethod
    def disconnect(self) -> None:
        """Close transport connection cleanly."""

    @abc.abstractmethod
    def send_command(
        self,
        inner_payload: bytes,
        *,
        expect_response: bool = False,
        expected_prefix: bytes | None = None,
        idempotent: bool = True,
        timeout: float = 2.0,
    ) -> bytes | None:
        """Send an inner command payload and optionally await/return its inner response."""

    @abc.abstractmethod
    def stats(self) -> TransportStats:
        """Return a snapshot of connection health metrics."""
