"""Hardware probe and capability verification diagnostics."""

from __future__ import annotations

from typing import Any

from controller.devices.wreath import WreathController
from controller.discovery.ble_discovery import discover_ble_devices
from controller.discovery.wifi_discovery import discover_wifi_devices


def run_discovery_audit(*, include_ble: bool = True, timeout: float = 2.0) -> dict[str, Any]:
    """Discover Wi-Fi (UDP 48899) and BLE (IOTWFC*) controllers on local interfaces."""
    wifi = discover_wifi_devices(timeout=timeout, enrich_at_info=True)
    ble = discover_ble_devices(timeout=timeout) if include_ble else []
    return {
        "wifi": [d.__dict__ for d in wifi],
        "ble": [d.__dict__ for d in ble],
    }


def probe_controller_details(host: str, port: int = 5577) -> dict[str, Any]:
    """Connect to a live Wi-Fi controller and collect read-only state/time/remote details."""
    ctrl = WreathController(host, port=port)
    try:
        ctrl.connect()
        diag = ctrl.get_diagnostics()
        diag["rtc_time"] = ctrl.query_time().isoformat()
        rc = ctrl.query_remote_config()
        diag["remote_config"] = {"state_flag": rc.state_flag, "remote_mode": rc.remote_mode}
        return diag
    finally:
        ctrl.disconnect()
