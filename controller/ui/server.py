"""Pure-stdlib HTTP/JSON server powering the Holiday Bright Lights Lighting Console UI."""

from __future__ import annotations

import json
import mimetypes
import threading
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from controller.devices.manager import ControllerManager
from controller.effects.base import TimelineAnimation
from controller.effects.library import list_host_effects
from controller.effects.native import list_native_overlays, list_native_scenes
from controller.effects.telegraphy import transmit_binary, transmit_morse
from controller.effects.weather_sync import (
    apply_weather_to_controller,
    fetch_current_weather_code,
    fetch_lat_lon,
)
from controller.exceptions import ControllerError, ValidationError
from controller.pixels.color import validate_rgb
from controller.pixels.wreath_layout import build_wreath_layout
from controller.protocol.encoder.tunnel import wrap_tcp_tunnel

STATIC_DIR = Path(__file__).resolve().parent / "static"

_SAFE_READ_PREFIXES = (
    b"\x81\x8a\x8b",
    b"\x11\x1a\x1b\x0f",
    b"\x2b\x2c\x2d",
)


class _ConsoleState:
    def __init__(self, manager: ControllerManager) -> None:
        self.manager = manager
        self.telegraph_stop = threading.Event()
        self.telegraph_thread: threading.Thread | None = None
        self.telegraph_lock = threading.Lock()

    def stop_telegraphy(self) -> None:
        with self.telegraph_lock:
            self.telegraph_stop.set()
            t = self.telegraph_thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            t.join(timeout=1.5)
        with self.telegraph_lock:
            self.telegraph_thread = None


def create_app_handler(manager: ControllerManager) -> type[BaseHTTPRequestHandler]:
    """Create a request handler class bound to ``manager``."""
    app_state = _ConsoleState(manager)

    class ConsoleHandler(BaseHTTPRequestHandler):
        server_version = "HolidayBrightConsole/2.0"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return  # Keep console stdout clean

        def _send_json(self, status: int, payload: Any, headers: dict[str, str] | None = None) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            if headers:
                for k, v in headers.items():
                    self.send_header(k, v)
            self.end_headers()
            self.wfile.write(raw)

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            body = self.rfile.read(length)
            try:
                parsed = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValidationError(f"Invalid JSON request body: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ValidationError("JSON body must be an object")
            return parsed

        def _serve_static(self, rel_path: str) -> None:
            target = (STATIC_DIR / rel_path.lstrip("/")).resolve()
            if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
                self._send_json(HTTPStatus.NOT_FOUND, {"error": f"Static file not found: {rel_path}"})
                return
            mime, _ = mimetypes.guess_type(str(target))
            data = target.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", mime or "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                if path in ("/", "/index.html"):
                    self._serve_static("index.html")
                    return
                if path.startswith("/static/"):
                    self._serve_static(path[len("/static/") :])
                    return
                if path == "/api/state":
                    ctrl = app_state.manager.get_active()
                    if qs.get("poll", ["0"])[0] == "1" and ctrl.is_connected:
                        try:
                            ctrl.get_status()
                        except ControllerError:
                            pass
                    diag = ctrl.get_diagnostics()
                    pixels = [list(px) for px in ctrl.framebuffer.snapshot_rgb(apply_brightness=False)]
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "diagnostics": diag,
                            "pixels": pixels,
                            "wreath_layout": [n.to_dict() for n in build_wreath_layout(ctrl.led_count)],
                            "controllers": app_state.manager.list_controllers(),
                            "host_effects": [e.__dict__ for e in list_host_effects()],
                            "native_scenes": list_native_scenes(),
                            "native_overlays": list_native_overlays(),
                            "patterns": app_state.manager.list_patterns(),
                            "timelines": app_state.manager.list_timelines(),
                        },
                    )
                    return
                if path == "/api/query/time":
                    ctrl = app_state.manager.get_active()
                    t = ctrl.query_time()
                    self._send_json(HTTPStatus.OK, {"ok": True, "time": t.isoformat(), "raw": t.raw.hex()})
                    return
                if path == "/api/query/remote":
                    ctrl = app_state.manager.get_active()
                    rc = ctrl.query_remote_config()
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "state_flag": rc.state_flag,
                            "remote_mode": rc.remote_mode,
                            "raw": rc.raw.hex(),
                        },
                    )
                    return
                if path == "/api/dev/packets":
                    ctrl = app_state.manager.get_active()
                    limit = int(qs.get("limit", ["100"])[0])
                    self._send_json(HTTPStatus.OK, {"ok": True, "packets": ctrl.capture.recent(limit)})
                    return
                if path == "/api/dev/export":
                    ctrl = app_state.manager.get_active()
                    blob = ctrl.capture.export_json(metadata=ctrl.get_diagnostics()).encode("utf-8")
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Content-Disposition", 'attachment; filename="wreath-diagnostics.json"')
                    self.send_header("Content-Length", str(len(blob)))
                    self.end_headers()
                    self.wfile.write(blob)
                    return
                self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": f"Unknown endpoint: {path}"})
            except ControllerError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})

        def do_POST(self) -> None:  # noqa: N802
            path = urllib.parse.urlparse(self.path).path
            try:
                body = self._read_json()

                if path == "/api/discover":
                    timeout = float(body.get("timeout", 2.0))
                    include_ble = bool(body.get("include_ble", False))
                    res = app_state.manager.discover_all(timeout=timeout, include_ble=include_ble)
                    self._send_json(HTTPStatus.OK, {"ok": True, "discovered": res})
                    return

                if path == "/api/connect":
                    kind = str(body.get("transport", "wifi")).lower()
                    if kind == "simulator":
                        ctrl = app_state.manager.register_simulator(
                            str(body.get("id", "sim://wreath-50")),
                            led_count=int(body.get("led_count", 50)),
                        )
                        app_state.manager.set_active(ctrl.transport.endpoint)
                    elif kind == "ble":
                        ident = str(body.get("identifier", "IOTWFC00")).strip() or "IOTWFC00"
                        ctrl = app_state.manager.add_ble(ident, connect_now=True)
                    else:
                        host = str(body.get("host", "")).strip()
                        if not host:
                            raise ValidationError("host IP address is required")
                        port = int(body.get("port", 5577))
                        ctrl = app_state.manager.add_wifi(host, port=port, connect_now=True)
                    self._send_json(HTTPStatus.OK, {"ok": True, "diagnostics": ctrl.get_diagnostics()})
                    return

                if path == "/api/controllers/active":
                    cid = str(body.get("id", ""))
                    ctrl = app_state.manager.set_active(cid)
                    self._send_json(HTTPStatus.OK, {"ok": True, "diagnostics": ctrl.get_diagnostics()})
                    return

                if path == "/api/disconnect":
                    app_state.stop_telegraphy()
                    ctrl = app_state.manager.get_active()
                    ctrl.disconnect()
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return

                ctrl = app_state.manager.get_active()

                if path == "/api/power":
                    app_state.stop_telegraphy()
                    on = bool(body.get("on", True))
                    if on:
                        ctrl.power_on()
                    else:
                        ctrl.power_off()
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return

                if path == "/api/color":
                    app_state.stop_telegraphy()
                    r = int(body["r"])
                    g = int(body["g"])
                    b = int(body["b"])
                    white = int(body.get("white", 0))
                    ctrl.set_color(r, g, b, white=white)
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return

                if path == "/api/brightness":
                    level = float(body["level"])
                    ctrl.set_brightness(level)
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return

                if path == "/api/effect":
                    app_state.stop_telegraphy()
                    if body.get("stop"):
                        ctrl.stop_effect()
                        self._send_json(HTTPStatus.OK, {"ok": True})
                        return
                    name = str(body.get("name", ""))
                    speed = body.get("speed")
                    fps = body.get("fps")
                    ctrl.set_effect(
                        name,
                        speed=None if speed is None else float(speed),
                        target_fps=None if fps is None else float(fps),
                    )
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return

                if path == "/api/speed":
                    ctrl.set_speed(float(body["speed"]))
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return

                if path == "/api/fps":
                    ctrl.set_target_fps(float(body["fps"]))
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return

                if path == "/api/mapping":
                    origin = int(body.get("origin", 0))
                    reverse = bool(body.get("reverse", False))
                    ctrl.set_mapping(origin=origin, reverse=reverse)
                    if body.get("push", False):
                        ctrl.show()
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return

                if path == "/api/pixels":
                    app_state.stop_telegraphy()
                    if "origin" in body or "reverse" in body:
                        ctrl.set_mapping(
                            origin=int(body.get("origin", ctrl.mapper.origin)),
                            reverse=bool(body.get("reverse", ctrl.mapper.reverse)),
                        )
                    action = body.get("action")
                    if action == "fill":
                        r, g, b = validate_rgb(int(body["r"]), int(body["g"]), int(body["b"]))
                        ctrl.fill(r, g, b)
                    elif action == "clear":
                        ctrl.clear()
                    elif action == "rotate":
                        ctrl.framebuffer.rotate(int(body.get("steps", 1)))
                    elif action == "gradient":
                        stops = [validate_rgb(int(c[0]), int(c[1]), int(c[2])) for c in body["stops"]]
                        start = int(body.get("start", 0))
                        end = int(body.get("end", ctrl.led_count - 1))
                        ctrl.framebuffer.apply_gradient(stops, start=start, end=end)
                    elif "pixels" in body:
                        pxs = [validate_rgb(int(c[0]), int(c[1]), int(c[2])) for c in body["pixels"]]
                        ctrl.stop_effect()
                        ctrl.framebuffer.set_all_rgb(pxs)
                    if body.get("show", True):
                        ctrl.show()
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "pixels": [list(p) for p in ctrl.framebuffer.snapshot_rgb(apply_brightness=False)],
                        },
                    )
                    return

                if path == "/api/zones":
                    app_state.stop_telegraphy()
                    zones = [validate_rgb(int(c[0]), int(c[1]), int(c[2])) for c in body["zones"]]
                    ctrl.set_zones(zones, white=int(body.get("white", 0)))
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return

                if path == "/api/patterns":
                    op = str(body.get("op", "save"))
                    name = str(body.get("name", ""))
                    if op == "delete":
                        app_state.manager.delete_pattern(name)
                    else:
                        pxs = [validate_rgb(int(c[0]), int(c[1]), int(c[2])) for c in body["pixels"]]
                        app_state.manager.save_pattern(name, pxs)
                    self._send_json(HTTPStatus.OK, {"ok": True, "patterns": app_state.manager.list_patterns()})
                    return

                if path == "/api/timelines":
                    op = str(body.get("op", "save"))
                    if op == "delete":
                        app_state.manager.delete_timeline(str(body.get("name", "")))
                    else:
                        tl = TimelineAnimation.from_dict(body["timeline"])
                        app_state.manager.save_timeline(tl)
                    self._send_json(HTTPStatus.OK, {"ok": True, "timelines": app_state.manager.list_timelines()})
                    return

                if path == "/api/timeline/play":
                    app_state.stop_telegraphy()
                    tl = TimelineAnimation.from_dict(body["timeline"])
                    speed = float(body.get("speed", 0.5))
                    fps = body.get("fps")
                    ctrl.play_timeline(tl, speed=speed, target_fps=None if fps is None else float(fps))
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return

                if path == "/api/telegraphy":
                    if body.get("stop"):
                        app_state.stop_telegraphy()
                        self._send_json(HTTPStatus.OK, {"ok": True})
                        return
                    mode = str(body.get("mode", "morse")).lower()
                    text = str(body.get("text", "SOS"))
                    loop = bool(body.get("loop", False))
                    app_state.stop_telegraphy()
                    app_state.telegraph_stop.clear()
                    if mode == "binary":
                        t = threading.Thread(
                            target=transmit_binary,
                            kwargs={
                                "ctrl": ctrl,
                                "text": text,
                                "one_color": str(body.get("one_color", "BLUE")),
                                "zero_color": str(body.get("zero_color", "RED")),
                                "bps": float(body.get("bps", 2.0)),
                                "loop": loop,
                                "stop_event": app_state.telegraph_stop,
                            },
                            daemon=True,
                        )
                    else:
                        t = threading.Thread(
                            target=transmit_morse,
                            kwargs={
                                "ctrl": ctrl,
                                "text": text,
                                "color": str(body.get("color", "GREEN")),
                                "wpm": float(body.get("wpm", 15.0)),
                                "loop": loop,
                                "stop_event": app_state.telegraph_stop,
                            },
                            daemon=True,
                        )
                    with app_state.telegraph_lock:
                        app_state.telegraph_thread = t
                    t.start()
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return

                if path == "/api/weather":
                    app_state.stop_telegraphy()
                    location = str(body.get("location", "48910")).strip() or "48910"
                    use_fx = bool(body.get("use_effect", False))
                    geo = fetch_lat_lon(location)
                    if geo is None:
                        lat, lon, name = 42.7325, -84.5555, "Lansing (Fallback)"
                    else:
                        lat, lon, name = geo
                    code = fetch_current_weather_code(lat, lon)
                    app = apply_weather_to_controller(ctrl, code, use_per_pixel_effect=use_fx)
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "location_name": name,
                            "lat": lat,
                            "lon": lon,
                            "wmo_code": code,
                            "label": app.label,
                            "rgb": list(app.rgb),
                            "effect": app.recommended_effect if use_fx else None,
                        },
                    )
                    return

                if path == "/api/dev/clear":
                    ctrl.capture.clear()
                    self._send_json(HTTPStatus.OK, {"ok": True})
                    return

                if path == "/api/dev/raw":
                    hex_str = str(body.get("hex", "")).replace(" ", "").strip()
                    if not hex_str:
                        raise ValidationError("hex payload must not be empty")
                    try:
                        inner = bytes.fromhex(hex_str)
                    except ValueError as exc:
                        raise ValidationError(f"Invalid hex string: {exc}") from exc
                    is_read_only = any(inner.startswith(p) for p in _SAFE_READ_PREFIXES)
                    if not is_read_only and not bool(body.get("confirmed", False)):
                        raise ValidationError(
                            "Safety guard: non-read-only raw commands require explicit confirmation ('confirmed': true)."
                        )
                    expect_resp = bool(body.get("expect_response", is_read_only))
                    preview = wrap_tcp_tunnel(inner, seq=0).hex()
                    resp = ctrl.send_raw_command(inner, expect_response=expect_resp)
                    self._send_json(
                        HTTPStatus.OK,
                        {
                            "ok": True,
                            "tx_inner_hex": inner.hex(),
                            "tx_tunnel_preview_hex": preview,
                            "rx_inner_hex": resp.hex() if resp else None,
                        },
                    )
                    return

                self._send_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": f"Unknown endpoint: {path}"})
            except ControllerError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": str(exc)})
            except KeyError as exc:
                self._send_json(HTTPStatus.BAD_REQUEST, {"ok": False, "error": f"Missing field: {exc}"})
            except Exception as exc:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"ok": False, "error": str(exc)})

    return ConsoleHandler


class LightingConsoleServer:
    """Lifecycle wrapper around ``ThreadingHTTPServer`` for the web console."""

    def __init__(
        self,
        manager: ControllerManager | None = None,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self.manager = manager if manager is not None else ControllerManager()
        self.host = host
        self.port = port
        handler = create_app_handler(self.manager)
        self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self.actual_port = self._httpd.server_address[1]
        self._thread: threading.Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.actual_port}"

    def start(self, *, background: bool = True) -> None:
        if background:
            self._thread = threading.Thread(
                target=self._httpd.serve_forever, name="LightingConsoleHTTP", daemon=True
            )
            self._thread.start()
        else:
            self._httpd.serve_forever()

    def stop(self) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.manager.shutdown()
