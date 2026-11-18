"""Thread-safe Wi-Fi TCP 5577 transport with B0 B1 B2 B3 framing and recovery."""

from __future__ import annotations

import socket
import threading
import time
from typing import Optional

from controller.diagnostics.capture import PacketCaptureLog
from controller.exceptions import ProtocolError, TransportError
from controller.protocol.constants import DEFAULT_TCP_PORT, TUNNEL_VERSION_DEFAULT
from controller.protocol.decoder.responses import TunnelFrame, extract_tunnel_frames
from controller.protocol.encoder.tunnel import wrap_tcp_tunnel
from controller.transports.base import BaseTransport, TransportStats


class WiFiTCPTransport(BaseTransport):
    """TCP port 5577 transport using the ``B0 B1 B2 B3`` tunnel protocol."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_TCP_PORT,
        *,
        connect_timeout: float = 3.0,
        io_timeout: float = 2.0,
        tunnel_version: int = TUNNEL_VERSION_DEFAULT,
        capture: Optional[PacketCaptureLog] = None,
    ) -> None:
        super().__init__(capture=capture)
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.io_timeout = io_timeout
        self.tunnel_version = tunnel_version

        self._lock = threading.RLock()
        self._sock: socket.socket | None = None
        self._rx_buf = bytearray()
        self._seq = 0
        self._tx_packets = 0
        self._rx_packets = 0
        self._tx_bytes = 0
        self._rx_bytes = 0
        self._reconnects = 0
        self._errors = 0
        self._last_latency_ms: float | None = None
        self._latency_samples = 0
        self._latency_sum_ms = 0.0
        self._last_error: str | None = None

    @property
    def name(self) -> str:
        return "wifi"

    @property
    def endpoint(self) -> str:
        return f"{self.host}:{self.port}"

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._sock is not None

    def _next_seq(self) -> int:
        seq = self._seq
        self._seq = (self._seq + 1) & 0xFF
        return seq

    def _close_socket_locked(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._rx_buf.clear()

    def connect(self) -> None:
        with self._lock:
            self._close_socket_locked()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.connect_timeout)
            try:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                pass
            try:
                t0 = time.monotonic()
                sock.connect((self.host, self.port))
                self._sock = sock
                self._record_latency((time.monotonic() - t0) * 1000.0)
                self._last_error = None
            except OSError as exc:
                try:
                    sock.close()
                except OSError:
                    pass
                self._errors += 1
                self._last_error = str(exc)
                raise TransportError(f"Failed to connect to {self.endpoint}: {exc}") from exc

    def disconnect(self) -> None:
        with self._lock:
            self._close_socket_locked()

    def _record_latency(self, ms: float) -> None:
        self._last_latency_ms = round(ms, 2)
        self._latency_samples += 1
        self._latency_sum_ms += ms

    def _drain_pending_locked(self) -> None:
        if self._sock is None:
            return
        prev_timeout = self._sock.gettimeout()
        self._sock.settimeout(0.0)
        try:
            while True:
                try:
                    chunk = self._sock.recv(4096)
                except (BlockingIOError, socket.timeout):
                    break
                if not chunk:
                    raise TransportError(f"Peer closed connection ({self.endpoint})")
                self._rx_bytes += len(chunk)
                self._rx_buf.extend(chunk)
        finally:
            if self._sock is not None:
                self._sock.settimeout(prev_timeout)

        # Parse and log any unsolicited push frames sitting in the buffer
        try:
            for frame in extract_tunnel_frames(self._rx_buf):
                self._rx_packets += 1
                self.capture.record(
                    direction="RX",
                    transport=self.name,
                    endpoint=self.endpoint,
                    seq=frame.seq,
                    wire_bytes=frame.raw,
                    inner_bytes=frame.inner,
                )
        except ProtocolError as exc:
            self._errors += 1
            self._last_error = str(exc)
            self._rx_buf.clear()

    def _read_matching_frame_locked(
        self,
        *,
        expected_seq: int,
        expected_prefix: bytes | None,
        timeout: float,
        t_start: float,
    ) -> TunnelFrame:
        assert self._sock is not None
        deadline = time.monotonic() + timeout
        while True:
            frames = extract_tunnel_frames(self._rx_buf)
            for frame in frames:
                self._rx_packets += 1
                latency_ms = round((time.monotonic() - t_start) * 1000.0, 2)
                self.capture.record(
                    direction="RX",
                    transport=self.name,
                    endpoint=self.endpoint,
                    seq=frame.seq,
                    wire_bytes=frame.raw,
                    inner_bytes=frame.inner,
                    latency_ms=latency_ms,
                )
                prefix_ok = expected_prefix is None or frame.inner.startswith(expected_prefix)
                if prefix_ok and (frame.seq == expected_seq or expected_prefix is not None):
                    self._record_latency(latency_ms)
                    return frame

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError(
                    f"Timed out waiting for response from {self.endpoint} after {timeout:.2f}s"
                )
            self._sock.settimeout(remaining)
            try:
                chunk = self._sock.recv(4096)
            except socket.timeout as exc:
                raise TransportError(
                    f"Timed out reading from {self.endpoint} after {timeout:.2f}s"
                ) from exc
            if not chunk:
                raise TransportError(f"Connection closed by {self.endpoint}")
            self._rx_bytes += len(chunk)
            self._rx_buf.extend(chunk)

    def send_command(
        self,
        inner_payload: bytes,
        *,
        expect_response: bool = False,
        expected_prefix: bytes | None = None,
        idempotent: bool = True,
        timeout: float | None = None,
    ) -> bytes | None:
        eff_timeout = self.io_timeout if timeout is None else timeout
        with self._lock:
            if self._sock is None:
                self.connect()

            attempts = 2 if idempotent else 1
            last_exc: Exception | None = None
            for attempt in range(attempts):
                if attempt > 0:
                    self._reconnects += 1
                    self.connect()
                assert self._sock is not None
                seq = self._next_seq()
                wire = wrap_tcp_tunnel(inner_payload, seq=seq, version=self.tunnel_version)
                t0 = time.monotonic()
                try:
                    if expect_response:
                        self._drain_pending_locked()
                    self._sock.settimeout(eff_timeout)
                    self._sock.sendall(wire)
                    self._tx_packets += 1
                    self._tx_bytes += len(wire)
                    self.capture.record(
                        direction="TX",
                        transport=self.name,
                        endpoint=self.endpoint,
                        seq=seq,
                        wire_bytes=wire,
                        inner_bytes=inner_payload,
                    )
                    if not expect_response:
                        return None
                    frame = self._read_matching_frame_locked(
                        expected_seq=seq,
                        expected_prefix=expected_prefix,
                        timeout=eff_timeout,
                        t_start=t0,
                    )
                    return frame.inner
                except (OSError, TransportError, ProtocolError) as exc:
                    self._errors += 1
                    self._last_error = str(exc)
                    self.capture.record(
                        direction="RX",
                        transport=self.name,
                        endpoint=self.endpoint,
                        seq=seq,
                        wire_bytes=b"",
                        inner_bytes=b"",
                        error=str(exc),
                    )
                    self._close_socket_locked()
                    last_exc = exc
                    if isinstance(exc, ProtocolError):
                        raise
            raise TransportError(f"Command failed on {self.endpoint}: {last_exc}") from last_exc

    def stats(self) -> TransportStats:
        with self._lock:
            avg = (
                round(self._latency_sum_ms / self._latency_samples, 2)
                if self._latency_samples
                else None
            )
            return TransportStats(
                transport_type=self.name,
                endpoint=self.endpoint,
                connected=self._sock is not None,
                tx_packets=self._tx_packets,
                rx_packets=self._rx_packets,
                tx_bytes=self._tx_bytes,
                rx_bytes=self._rx_bytes,
                reconnects=self._reconnects,
                errors=self._errors,
                last_latency_ms=self._last_latency_ms,
                avg_latency_ms=avg,
                last_error=self._last_error,
            )
