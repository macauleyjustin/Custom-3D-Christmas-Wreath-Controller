"""Multi-controller registry and preset storage for patterns and timeline animations."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from controller.devices.wreath import WreathController
from controller.discovery.ble_discovery import DiscoveredBLEDevice, discover_ble_devices
from controller.discovery.wifi_discovery import DiscoveredWiFiDevice, discover_wifi_devices
from controller.effects.base import TimelineAnimation
from controller.exceptions import ValidationError
from controller.pixels.color import RGB, validate_rgb
from controller.transports.ble import BLETransport
from controller.transports.simulator import SimulatorTransport


class ControllerManager:
    """Manages multiple Wi-Fi, BLE, or Simulator controllers and JSON preset files."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._lock = threading.RLock()
        self._controllers: dict[str, WreathController] = {}
        self._active_id: str | None = None
        self.data_dir = (
            data_dir
            if data_dir is not None
            else Path.home() / ".holiday_bright_lights"
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._patterns_file = self.data_dir / "patterns.json"
        self._timelines_file = self.data_dir / "timelines.json"

    def register_simulator(self, cid: str = "sim://wreath-50", led_count: int = 50) -> WreathController:
        with self._lock:
            if cid in self._controllers:
                return self._controllers[cid]
            ctrl = WreathController(SimulatorTransport(endpoint_name=cid), led_count=led_count)
            ctrl.connect()
            self._controllers[cid] = ctrl
            if self._active_id is None:
                self._active_id = cid
            return ctrl

    def add_wifi(self, host: str, port: int = 5577, *, connect_now: bool = True) -> WreathController:
        cid = f"{host}:{port}"
        with self._lock:
            if cid in self._controllers:
                ctrl = self._controllers[cid]
                if connect_now and not ctrl.is_connected:
                    ctrl.connect()
                self._active_id = cid
                return ctrl
            ctrl = WreathController(host, port=port)
            if connect_now:
                ctrl.connect()
            self._controllers[cid] = ctrl
            self._active_id = cid
            return ctrl

    def add_ble(self, identifier: str = "IOTWFC00", *, connect_now: bool = True) -> WreathController:
        cid = f"ble://{identifier}"
        with self._lock:
            if cid in self._controllers:
                ctrl = self._controllers[cid]
                if connect_now and not ctrl.is_connected:
                    ctrl.connect()
                self._active_id = cid
                return ctrl
            ctrl = WreathController(BLETransport(identifier))
            if connect_now:
                ctrl.connect()
            self._controllers[cid] = ctrl
            self._active_id = cid
            return ctrl

    def set_active(self, cid: str) -> WreathController:
        with self._lock:
            if cid not in self._controllers:
                raise ValidationError(f"Unknown controller ID: {cid}")
            self._active_id = cid
            return self._controllers[cid]

    def get_active(self) -> WreathController:
        with self._lock:
            if self._active_id and self._active_id in self._controllers:
                return self._controllers[self._active_id]
            return self.register_simulator()

    def list_controllers(self) -> list[dict[str, Any]]:
        with self._lock:
            out: list[dict[str, Any]] = []
            for cid, ctrl in self._controllers.items():
                st = ctrl.transport_stats()
                out.append(
                    {
                        "id": cid,
                        "active": cid == self._active_id,
                        "transport": st.transport_type,
                        "endpoint": st.endpoint,
                        "connected": st.connected,
                        "led_count": ctrl.led_count,
                        "last_latency_ms": st.last_latency_ms,
                    }
                )
            return out

    def discover_all(self, *, timeout: float = 2.0, include_ble: bool = False) -> dict[str, Any]:
        wifi_devs: list[DiscoveredWiFiDevice] = discover_wifi_devices(timeout=timeout)
        ble_devs: list[DiscoveredBLEDevice] = discover_ble_devices(timeout=timeout) if include_ble else []
        return {
            "wifi": [
                {
                    "ip": d.ip,
                    "mac": d.formatted_mac,
                    "model": d.model,
                    "firmware_info": d.firmware_info,
                    "cloud_endpoint": d.cloud_endpoint,
                    "wifi_mode": d.wifi_mode,
                }
                for d in wifi_devs
            ],
            "ble": [
                {
                    "name": d.name,
                    "identifier": d.identifier,
                    "rssi": d.rssi,
                    "mac": d.mac,
                    "model_id": f"0x{d.model_id:04X}" if d.model_id is not None else None,
                    "fw_minor": d.fw_minor,
                }
                for d in ble_devs
            ],
        }

    # --- Preset Persistence ---
    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_patterns(self) -> dict[str, list[list[int]]]:
        data = self._load_json(self._patterns_file)
        return {str(k): v for k, v in data.items()}

    def save_pattern(self, name: str, pixels: list[RGB]) -> None:
        clean = name.strip()
        if not clean:
            raise ValidationError("Pattern name cannot be empty")
        validated = [list(validate_rgb(*px)) for px in pixels]
        data = self.list_patterns()
        data[clean] = validated
        self._save_json(self._patterns_file, data)

    def delete_pattern(self, name: str) -> None:
        data = self.list_patterns()
        data.pop(name, None)
        self._save_json(self._patterns_file, data)

    def list_timelines(self) -> dict[str, dict[str, Any]]:
        data = self._load_json(self._timelines_file)
        return {str(k): v for k, v in data.items()}

    def save_timeline(self, timeline: TimelineAnimation) -> None:
        clean = timeline.name.strip()
        if not clean:
            raise ValidationError("Timeline name cannot be empty")
        data = self.list_timelines()
        data[clean] = timeline.to_dict()
        self._save_json(self._timelines_file, data)

    def delete_timeline(self, name: str) -> None:
        data = self.list_timelines()
        data.pop(name, None)
        self._save_json(self._timelines_file, data)

    def shutdown(self) -> None:
        with self._lock:
            ctrls = list(self._controllers.values())
        for ctrl in ctrls:
            try:
                ctrl.disconnect()
            except Exception:
                pass
