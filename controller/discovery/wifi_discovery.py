"""Wi-Fi UDP 48899 discovery and safe AT read-only module probing."""

from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass

from controller.protocol.constants import (
    AT_LVER_QUERY,
    AT_SOCKB_QUERY,
    AT_WMODE_QUERY,
    DISCOVERY_QUERY,
    DISCOVERY_UDP_PORT,
)


@dataclass(frozen=True)
class DiscoveredWiFiDevice:
    """Device record returned by UDP 48899 discovery + optional AT queries."""

    ip: str
    mac: str
    model: str
    device_id: str = ""
    firmware_info: str = ""
    cloud_endpoint: str = ""
    wifi_mode: str = ""
    raw_discovery: str = ""

    @property
    def formatted_mac(self) -> str:
        clean = self.mac.replace(":", "").upper()
        if len(clean) == 12:
            return ":".join(clean[i : i + 2] for i in range(0, 12, 2))
        return self.mac


def parse_discovery_reply(raw: str) -> DiscoveredWiFiDevice | None:
    """Parse ``ip,MAC,model[,token]`` from ``HF-A11ASSISTHREAD`` reply."""
    text = raw.strip()
    parts = [p.strip() for p in text.split(",")]
    if len(parts) < 3:
        return None
    try:
        ipaddress.IPv4Address(parts[0])
    except ValueError:
        return None
    return DiscoveredWiFiDevice(
        ip=parts[0],
        mac=parts[1],
        model=parts[2],
        device_id=parts[3] if len(parts) >= 4 else "",
        raw_discovery=text,
    )


def _udp_at_query(ip: str, query: bytes, timeout: float = 0.6) -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    try:
        sock.sendto(query, (ip, DISCOVERY_UDP_PORT))
        data, _ = sock.recvfrom(1024)
        text = data.decode("utf-8", errors="replace").strip()
        if text.startswith("+ok="):
            return text[4:]
        return text
    except OSError:
        return ""
    finally:
        sock.close()


def query_module_at_info(ip: str, timeout: float = 0.6) -> dict[str, str]:
    """Send safe read-only AT queries (LVER, SOCKB, WMODE) over UDP 48899."""
    return {
        "firmware_info": _udp_at_query(ip, AT_LVER_QUERY, timeout),
        "cloud_endpoint": _udp_at_query(ip, AT_SOCKB_QUERY, timeout),
        "wifi_mode": _udp_at_query(ip, AT_WMODE_QUERY, timeout),
    }


def discover_wifi_devices(
    timeout: float = 2.0,
    broadcast_addr: str = "255.255.255.255",
    enrich_at_info: bool = True,
) -> list[DiscoveredWiFiDevice]:
    """Broadcast ``HF-A11ASSISTHREAD`` on UDP 48899 and collect responding devices."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(0.25)
    found: dict[str, DiscoveredWiFiDevice] = {}
    try:
        deadline = time.monotonic() + timeout
        # Send twice 0.25s apart to tolerate UDP broadcast packet loss
        next_send = 0.0
        while time.monotonic() < deadline:
            now = time.monotonic()
            if now >= next_send:
                try:
                    sock.sendto(DISCOVERY_QUERY, (broadcast_addr, DISCOVERY_UDP_PORT))
                except OSError:
                    pass
                next_send = now + 0.5
            try:
                data, addr = sock.recvfrom(1024)
            except socket.timeout:
                continue
            except OSError:
                break
            parsed = parse_discovery_reply(data.decode("utf-8", errors="replace"))
            if parsed is not None:
                found[parsed.ip] = parsed
            elif addr and addr[0] not in found:
                # Ignore echoed broadcast or non-CSV packets
                continue
    finally:
        sock.close()

    results: list[DiscoveredWiFiDevice] = []
    for ip, dev in sorted(found.items()):
        if enrich_at_info:
            info = query_module_at_info(ip, timeout=min(0.6, timeout))
            dev = DiscoveredWiFiDevice(
                ip=dev.ip,
                mac=dev.mac,
                model=dev.model,
                device_id=dev.device_id,
                firmware_info=info["firmware_info"],
                cloud_endpoint=info["cloud_endpoint"],
                wifi_mode=info["wifi_mode"],
                raw_discovery=dev.raw_discovery,
            )
        results.append(dev)
    return results
