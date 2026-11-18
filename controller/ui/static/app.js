const state = {
  pixels: Array.from({ length: 50 }, () => [255, 0, 0]),
  wreathLayout: [],
  diagnostics: null,
  keyframes: [],
  selectedKf: -1,
  painting: false,
  ledPositions: [],
};

const $ = (id) => document.getElementById(id);

function showToast(msg, isError = false) {
  const el = $("toast");
  el.textContent = msg;
  el.className = "toast" + (isError ? " err" : "");
  clearTimeout(el._timer);
  el._timer = setTimeout(() => el.classList.add("hidden"), 3200);
}

async function api(path, method = "GET", body = null) {
  const opts = { method, headers: {} };
  if (body !== null) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const resp = await fetch(path, opts);
  const data = await resp.json();
  if (!resp.ok || data.ok === false) {
    throw new Error(data.error || `HTTP ${resp.status}`);
  }
  return data;
}

function hexToRgb(hex) {
  const clean = hex.replace("#", "");
  return [
    parseInt(clean.slice(0, 2), 16),
    parseInt(clean.slice(2, 4), 16),
    parseInt(clean.slice(4, 6), 16),
  ];
}

function rgbToHex(rgb) {
  return "#" + rgb.map((v) => Math.max(0, Math.min(255, v)).toString(16).padStart(2, "0")).join("");
}

// --- Tabs ---
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $("tab-" + btn.dataset.tab).classList.add("active");
    if (btn.dataset.tab === "pixels") drawWreath();
    if (btn.dataset.tab === "developer") refreshPackets();
  });
});

// --- State Sync ---
async function refreshState(poll = false) {
  try {
    const data = await api(`/api/state?poll=${poll ? 1 : 0}`);
    state.diagnostics = data.diagnostics;
    if (Array.isArray(data.pixels) && data.pixels.length > 0) {
      state.pixels = data.pixels;
    }
    if (Array.isArray(data.wreath_layout)) {
      state.wreathLayout = data.wreath_layout;
    }
    renderControllers(data.controllers);
    renderDiagnostics(data.diagnostics);
    renderEffectCatalogs(data.host_effects, data.native_scenes, data.native_overlays, data.diagnostics);
    renderSavedPatterns(data.patterns);
    renderSavedTimelines(data.timelines);
    drawWreath();
    renderLinearStrip();
  } catch (err) {
    showToast(err.message, true);
  }
}

function renderControllers(controllers) {
  const sel = $("controller-select");
  sel.innerHTML = "";
  for (const c of controllers) {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = `${c.endpoint} (${c.transport})`;
    opt.selected = c.active;
    sel.appendChild(opt);
  }
}

function renderDiagnostics(d) {
  if (!d) return;
  const pill = $("conn-pill");
  pill.textContent = d.connected ? `Connected · ${d.endpoint}` : `Disconnected · ${d.endpoint}`;
  pill.className = "pill" + (d.connected ? "" : " offline");

  const ts = d.transport_stats || {};
  const sc = d.scheduler || {};
  const rtt = ts.last_latency_ms != null ? `${ts.last_latency_ms}ms` : "—";
  const fps = sc.running ? `${sc.actual_fps || sc.target_fps} FPS` : "idle";
  $("metrics-pill").textContent = `RTT ${rtt} · ${fps}`;

  const caps = d.capabilities || {};
  const st = d.state || {};
  $("info-model").textContent = `${caps.model_name || "—"} (${caps.model_id || "?"})`;
  $("info-fw").textContent = (d.at_info && d.at_info.firmware_info) || caps.firmware_family || "—";
  $("info-leds").textContent = `${caps.led_count || 50} LEDs · ${st.mode || d.output_mode || "—"} (${st.is_on === false ? "OFF" : "ON"})`;
  $("info-quality").textContent = `TX:${ts.tx_packets || 0} RX:${ts.rx_packets || 0} Reconn:${ts.reconnects || 0} Err:${ts.errors || 0}`;
  $("active-mode-badge").textContent = sc.running ? `Streaming: ${sc.effect_name}` : `Mode: ${d.output_mode}`;

  if (d.mapping) {
    $("map-origin").value = d.mapping.origin;
    $("map-reverse").checked = !!d.mapping.reverse;
  }
  $("slider-brightness").value = Math.round((d.brightness ?? 1.0) * 100);
  $("val-brightness").textContent = `${$("slider-brightness").value}%`;
  $("dev-capabilities-json").textContent = JSON.stringify({ capabilities: caps, state: st, transport_stats: ts }, null, 2);
}

function renderEffectCatalogs(hostEffects, nativeScenes, overlays, diag) {
  const activeId = diag?.scheduler?.running ? diag.scheduler.effect_id : null;
  const hostGrid = $("host-effects-grid");
  hostGrid.innerHTML = "";
  for (const fx of hostEffects) {
    const btn = document.createElement("button");
    btn.className = "fx-btn" + (activeId === fx.id ? " active" : "");
    btn.innerHTML = `<span class="fx-name">${fx.name}</span><span class="fx-cat">${fx.category}</span>`;
    btn.title = fx.description;
    btn.addEventListener("click", async () => {
      try {
        await api("/api/effect", "POST", {
          name: fx.id,
          speed: Number($("slider-speed").value) / 100,
          fps: Number($("slider-fps").value),
        });
        showToast(`Started ${fx.name}`);
        refreshState();
      } catch (e) { showToast(e.message, true); }
    });
    hostGrid.appendChild(btn);
  }

  const natGrid = $("native-scenes-grid");
  natGrid.innerHTML = "";
  for (const sc of nativeScenes) {
    const btn = document.createElement("button");
    btn.className = "fx-btn";
    btn.innerHTML = `<span class="fx-name">${sc.name}</span><span class="fx-cat">E1 21 · 0x${sc.program.toString(16).padStart(2, "0")}</span>`;
    btn.addEventListener("click", async () => {
      try {
        await api("/api/effect", "POST", {
          name: `native:${sc.id}`,
          speed: Number($("slider-speed").value) / 100,
        });
        showToast(`Activated ${sc.name}`);
        refreshState();
      } catch (e) { showToast(e.message, true); }
    });
    natGrid.appendChild(btn);
  }

  const ovGrid = $("native-overlays-grid");
  ovGrid.innerHTML = "";
  for (const ov of overlays) {
    const btn = document.createElement("button");
    btn.className = "fx-btn";
    btn.innerHTML = `<span class="fx-name">${ov.id.replaceAll("_", " ")}</span><span class="fx-cat">E1 26 · 0x${ov.oo.toString(16).padStart(2, "0")}</span>`;
    btn.addEventListener("click", async () => {
      try {
        await api("/api/effect", "POST", {
          name: `overlay:${ov.id}`,
          speed: Number($("slider-speed").value) / 100,
        });
        showToast(`Applied overlay ${ov.id}`);
        refreshState();
      } catch (e) { showToast(e.message, true); }
    });
    ovGrid.appendChild(btn);
  }
}

// --- Topbar & Device Panel Actions ---
$("controller-select").addEventListener("change", async (e) => {
  try {
    await api("/api/controllers/active", "POST", { id: e.target.value });
    refreshState();
  } catch (err) { showToast(err.message, true); }
});

$("btn-power-on").addEventListener("click", async () => {
  try { await api("/api/power", "POST", { on: true }); showToast("Power ON"); refreshState(true); }
  catch (e) { showToast(e.message, true); }
});

$("btn-power-off").addEventListener("click", async () => {
  try { await api("/api/power", "POST", { on: false }); showToast("Power OFF"); refreshState(true); }
  catch (e) { showToast(e.message, true); }
});

for (const id of ["btn-stop-effect", "btn-stop-effect-2"]) {
  $(id).addEventListener("click", async () => {
    try { await api("/api/effect", "POST", { stop: true }); showToast("Effect stopped"); refreshState(); }
    catch (e) { showToast(e.message, true); }
  });
}

async function runScan(includeBle) {
  const list = $("discovery-list");
  list.innerHTML = `<div class="hint">Scanning network${includeBle ? " & BLE" : ""}...</div>`;
  try {
    const res = await api("/api/discover", "POST", { timeout: 2.0, include_ble: includeBle });
    list.innerHTML = "";
    for (const w of res.discovered.wifi) {
      const row = document.createElement("div");
      row.className = "disc-item";
      row.innerHTML = `<span><strong>Wi-Fi ${w.ip}</strong> · ${w.model} · MAC ${w.mac} · ${w.firmware_info || ""}</span>`;
      const btn = document.createElement("button");
      btn.className = "btn small primary";
      btn.textContent = "Connect";
      btn.addEventListener("click", async () => {
        $("input-host").value = w.ip;
        await api("/api/connect", "POST", { transport: "wifi", host: w.ip });
        showToast(`Connected to ${w.ip}`);
        refreshState();
      });
      row.appendChild(btn);
      list.appendChild(row);
    }
    for (const b of res.discovered.ble) {
      const row = document.createElement("div");
      row.className = "disc-item";
      row.innerHTML = `<span><strong>BLE ${b.name}</strong> · MAC ${b.mac || "?"} · RSSI ${b.rssi}</span>`;
      const btn = document.createElement("button");
      btn.className = "btn small primary";
      btn.textContent = "Connect BLE";
      btn.addEventListener("click", async () => {
        await api("/api/connect", "POST", { transport: "ble", identifier: b.name || b.identifier });
        showToast(`Connected BLE ${b.name}`);
        refreshState();
      });
      row.appendChild(btn);
      list.appendChild(row);
    }
    if (!list.children.length) list.innerHTML = `<div class="hint">No devices answered discovery.</div>`;
  } catch (e) {
    list.innerHTML = "";
    showToast(e.message, true);
  }
}

$("btn-scan-wifi").addEventListener("click", () => runScan(false));
$("btn-scan-ble").addEventListener("click", () => runScan(true));

$("btn-connect-wifi").addEventListener("click", async () => {
  try {
    const host = $("input-host").value.trim();
    await api("/api/connect", "POST", { transport: "wifi", host });
    showToast(`Connected to ${host}`);
    refreshState();
  } catch (e) { showToast(e.message, true); }
});

$("btn-connect-ble").addEventListener("click", async () => {
  try {
    await api("/api/connect", "POST", { transport: "ble", identifier: "IOTWFC00" });
    showToast("Connected BLE IOTWFC00");
    refreshState();
  } catch (e) { showToast(e.message, true); }
});

$("btn-connect-sim").addEventListener("click", async () => {
  try {
    await api("/api/connect", "POST", { transport: "simulator" });
    showToast("Switched to Simulator");
    refreshState();
  } catch (e) { showToast(e.message, true); }
});

$("btn-disconnect").addEventListener("click", async () => {
  try { await api("/api/disconnect", "POST", {}); showToast("Disconnected"); refreshState(); }
  catch (e) { showToast(e.message, true); }
});

$("btn-refresh-state").addEventListener("click", () => refreshState(true));
$("btn-query-rtc").addEventListener("click", async () => {
  try {
    const res = await api("/api/query/time");
    $("diag-output").classList.remove("hidden");
    $("diag-output").textContent = `Controller RTC Time: ${res.time}\nRaw 0F 11: ${res.raw}`;
  } catch (e) { showToast(e.message, true); }
});
$("btn-query-remote").addEventListener("click", async () => {
  try {
    const res = await api("/api/query/remote");
    $("diag-output").classList.remove("hidden");
    $("diag-output").textContent = `Remote Flag: ${res.state_flag}, Mode: ${res.remote_mode}\nRaw 2B: ${res.raw}`;
  } catch (e) { showToast(e.message, true); }
});

// --- Lighting Controls ---
async function pushSolidColor() {
  const [r, g, b] = hexToRgb($("color-picker").value);
  const white = Number($("slider-white").value);
  try {
    await api("/api/color", "POST", { r, g, b, white });
    refreshState();
  } catch (e) { showToast(e.message, true); }
}

$("color-picker").addEventListener("change", pushSolidColor);
$("slider-white").addEventListener("input", () => { $("val-white").textContent = `${$("slider-white").value}%`; });
$("slider-white").addEventListener("change", pushSolidColor);

$("slider-brightness").addEventListener("input", () => { $("val-brightness").textContent = `${$("slider-brightness").value}%`; });
$("slider-brightness").addEventListener("change", async () => {
  try { await api("/api/brightness", "POST", { level: Number($("slider-brightness").value) / 100 }); refreshState(); }
  catch (e) { showToast(e.message, true); }
});

$("slider-speed").addEventListener("input", () => { $("val-speed").textContent = `${$("slider-speed").value}%`; });
$("slider-speed").addEventListener("change", async () => {
  try { await api("/api/speed", "POST", { speed: Number($("slider-speed").value) / 100 }); }
  catch (_) { /* ignore when idle */ }
});

$("slider-fps").addEventListener("input", () => { $("val-fps").textContent = `${$("slider-fps").value} FPS`; });
$("slider-fps").addEventListener("change", async () => {
  try { await api("/api/fps", "POST", { fps: Number($("slider-fps").value) }); }
  catch (e) { showToast(e.message, true); }
});

document.querySelectorAll(".swatch").forEach((sw) => {
  sw.addEventListener("click", async () => {
    const [r, g, b] = sw.dataset.rgb.split(",").map(Number);
    $("color-picker").value = rgbToHex([r, g, b]);
    await pushSolidColor();
  });
});

// --- Telegraphy & Weather ---
$("btn-tel-start").addEventListener("click", async () => {
  try {
    const mode = $("tel-mode").value;
    const text = $("tel-text").value;
    const rate = Number($("tel-rate").value);
    const body = mode === "binary" ? { mode, text, bps: rate } : { mode, text, wpm: rate };
    await api("/api/telegraphy", "POST", body);
    showToast(`Transmitting ${mode.toUpperCase()}: ${text}`);
  } catch (e) { showToast(e.message, true); }
});
$("btn-tel-stop").addEventListener("click", async () => {
  try { await api("/api/telegraphy", "POST", { stop: true }); showToast("Telegraphy stopped"); }
  catch (e) { showToast(e.message, true); }
});
$("btn-weather-sync").addEventListener("click", async () => {
  try {
    const res = await api("/api/weather", "POST", {
      location: $("weather-loc").value,
      use_effect: $("weather-fx").checked,
    });
    $("weather-result").textContent = `${res.location_name}: WMO ${res.wmo_code} (${res.label}) -> RGB(${res.rgb.join(",")})`;
    showToast(`Weather synced: ${res.label}`);
    refreshState();
  } catch (e) { showToast(e.message, true); }
});

// --- Pixel Editor ---
function drawWreath() {
  const canvas = $("wreath-canvas");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  const cx = w / 2, cy = h / 2, maxRadius = 175;
  ctx.clearRect(0, 0, w, h);

  const use3D = $("chk-3d-layout")?.checked && state.wreathLayout.length === state.pixels.length;

  // Guide rings (inner / crown / outer in 3D mode)
  const guideRadii = use3D ? [maxRadius * 0.56, maxRadius * 0.78, maxRadius] : [maxRadius];
  for (const rad of guideRadii) {
    ctx.beginPath();
    ctx.arc(cx, cy, rad, 0, Math.PI * 2);
    ctx.strokeStyle = "#1f2a3d";
    ctx.lineWidth = use3D ? 2 : 14;
    ctx.stroke();
  }

  const count = state.pixels.length || 50;
  state.ledPositions = [];
  for (let i = 0; i < count; i++) {
    let x, y, nodeMeta = null;
    if (use3D) {
      nodeMeta = state.wreathLayout[i];
      // Slight deterministic offset when multiple back LEDs share the exact same clock hour
      const jitterAng = nodeMeta.layer === "back" ? ((i % 3) - 1) * 0.05 : 0;
      const rad = maxRadius * nodeMeta.radius;
      const ang = (nodeMeta.angle_deg * Math.PI) / 180 + jitterAng - Math.PI / 2;
      x = cx + Math.cos(ang) * rad;
      y = cy + Math.sin(ang) * rad;
    } else {
      const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
      x = cx + Math.cos(angle) * maxRadius;
      y = cy + Math.sin(angle) * maxRadius;
    }
    state.ledPositions.push({ i, x, y, meta: nodeMeta });

    const [r, g, b] = state.pixels[i] || [0, 0, 0];
    ctx.beginPath();
    ctx.arc(x, y, nodeMeta?.layer === "back" ? 7.0 : 8.8, 0, Math.PI * 2);
    ctx.fillStyle = `rgb(${r},${g},${b})`;
    ctx.fill();
    ctx.lineWidth = nodeMeta?.layer === "back" ? 1.2 : 1.6;
    if (nodeMeta?.layer === "back") ctx.setLineDash([2, 2]);
    ctx.strokeStyle = nodeMeta?.layer === "inner" ? "#38bdf8" : "rgba(255,255,255,0.45)";
    ctx.stroke();
    ctx.setLineDash([]);

    if (use3D || i % 5 === 0) {
      ctx.fillStyle = "#e6ecf5";
      ctx.font = "9px sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(i), x, y);
    }
  }
}

$("chk-3d-layout")?.addEventListener("change", drawWreath);

function renderLinearStrip() {
  const strip = $("linear-strip");
  if (!strip) return;
  strip.innerHTML = "";
  state.pixels.forEach((rgb, i) => {
    const cell = document.createElement("div");
    cell.className = "strip-cell";
    cell.style.background = `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
    cell.textContent = String(i);
    cell.addEventListener("click", () => handlePixelClick(i));
    strip.appendChild(cell);
  });
}

let pushDebounce = null;
function schedulePushPixels() {
  if (!$("chk-auto-push").checked) return;
  clearTimeout(pushDebounce);
  pushDebounce = setTimeout(async () => {
    try {
      await api("/api/pixels", "POST", {
        pixels: state.pixels,
        show: true,
        origin: Number($("map-origin").value),
        reverse: $("map-reverse").checked,
      });
    } catch (e) { showToast(e.message, true); }
  }, 60);
}

function handlePixelClick(idx) {
  if ($("pixel-tool").value === "eyedropper") {
    $("pixel-brush-color").value = rgbToHex(state.pixels[idx]);
    $("pixel-tool").value = "paint";
    showToast(`Picked LED #${idx}`);
    return;
  }
  state.pixels[idx] = hexToRgb($("pixel-brush-color").value);
  drawWreath();
  renderLinearStrip();
  schedulePushPixels();
}

function hitTestCanvas(ev) {
  const canvas = $("wreath-canvas");
  const rect = canvas.getBoundingClientRect();
  const sx = canvas.width / rect.width;
  const sy = canvas.height / rect.height;
  const x = (ev.clientX - rect.left) * sx;
  const y = (ev.clientY - rect.top) * sy;
  let best = -1;
  let bestDist = 14;
  for (const pt of state.ledPositions) {
    const d = Math.hypot(pt.x - x, pt.y - y);
    if (d <= bestDist) {
      bestDist = d;
      best = pt.i;
    }
  }
  return best;
}

$("wreath-canvas").addEventListener("mousedown", (ev) => {
  state.painting = true;
  const idx = hitTestCanvas(ev);
  if (idx >= 0) handlePixelClick(idx);
});
$("wreath-canvas").addEventListener("mousemove", (ev) => {
  const idx = hitTestCanvas(ev);
  const meta = idx >= 0 ? state.wreathLayout[idx] : null;
  const loc = meta ? ` · ${meta.clock_hour}h (${meta.layer})` : "";
  $("hover-pixel-info").textContent = idx >= 0
    ? `LED #${idx}${loc} · RGB(${state.pixels[idx].join(", ")})`
    : "Click or drag LEDs on the ring or strip below to paint.";
  if (state.painting && idx >= 0 && $("pixel-tool").value === "paint") {
    handlePixelClick(idx);
  }
});
window.addEventListener("mouseup", () => { state.painting = false; });

$("btn-push-pixels").addEventListener("click", async () => {
  try {
    await api("/api/pixels", "POST", {
      pixels: state.pixels,
      show: true,
      origin: Number($("map-origin").value),
      reverse: $("map-reverse").checked,
    });
    showToast("Pushed 50-pixel frame (E1 23)");
    refreshState();
  } catch (e) { showToast(e.message, true); }
});

$("btn-px-fill").addEventListener("click", () => {
  const c = hexToRgb($("pixel-brush-color").value);
  state.pixels = state.pixels.map(() => [...c]);
  drawWreath(); renderLinearStrip(); schedulePushPixels();
});
$("btn-px-clear").addEventListener("click", () => {
  state.pixels = state.pixels.map(() => [0, 0, 0]);
  drawWreath(); renderLinearStrip(); schedulePushPixels();
});
$("btn-px-rot-cw").addEventListener("click", () => {
  state.pixels = [state.pixels[state.pixels.length - 1], ...state.pixels.slice(0, -1)];
  drawWreath(); renderLinearStrip(); schedulePushPixels();
});
$("btn-px-rot-ccw").addEventListener("click", () => {
  state.pixels = [...state.pixels.slice(1), state.pixels[0]];
  drawWreath(); renderLinearStrip(); schedulePushPixels();
});
$("btn-seg-paint").addEventListener("click", () => {
  const s = Math.max(0, Math.min(49, Number($("seg-start").value)));
  const e = Math.max(s, Math.min(49, Number($("seg-end").value)));
  const step = Math.max(1, Number($("seg-step").value));
  const c = hexToRgb($("pixel-brush-color").value);
  for (let i = s; i <= e; i += step) state.pixels[i] = [...c];
  drawWreath(); renderLinearStrip(); schedulePushPixels();
});
$("btn-px-gradient").addEventListener("click", async () => {
  try {
    const stops = [hexToRgb($("grad-c1").value), hexToRgb($("grad-c2").value), hexToRgb($("grad-c3").value)];
    const res = await api("/api/pixels", "POST", { action: "gradient", stops, show: $("chk-auto-push").checked });
    state.pixels = res.pixels;
    drawWreath(); renderLinearStrip();
  } catch (e) { showToast(e.message, true); }
});
$("btn-apply-mapping").addEventListener("click", async () => {
  try {
    await api("/api/mapping", "POST", {
      origin: Number($("map-origin").value),
      reverse: $("map-reverse").checked,
      push: true,
    });
    showToast("Updated ring mapping");
  } catch (e) { showToast(e.message, true); }
});

function renderSavedPatterns(patterns) {
  const list = $("patterns-list");
  list.innerHTML = "";
  for (const [name, pxs] of Object.entries(patterns || {})) {
    const chip = document.createElement("div");
    chip.className = "saved-chip";
    const loadBtn = document.createElement("button");
    loadBtn.textContent = name;
    loadBtn.addEventListener("click", () => {
      state.pixels = pxs.map((c) => [...c]);
      drawWreath(); renderLinearStrip(); schedulePushPixels();
      showToast(`Loaded pattern '${name}'`);
    });
    const delBtn = document.createElement("button");
    delBtn.className = "del";
    delBtn.textContent = "×";
    delBtn.addEventListener("click", async () => {
      await api("/api/patterns", "POST", { op: "delete", name });
      refreshState();
    });
    chip.appendChild(loadBtn);
    chip.appendChild(delBtn);
    list.appendChild(chip);
  }
}

$("btn-save-pattern").addEventListener("click", async () => {
  try {
    const name = $("pattern-name").value.trim();
    await api("/api/patterns", "POST", { op: "save", name, pixels: state.pixels });
    $("pattern-name").value = "";
    showToast(`Saved pattern '${name}'`);
    refreshState();
  } catch (e) { showToast(e.message, true); }
});

// --- Timeline / Keyframe Animation Editor ---
function renderTimeline() {
  const strip = $("timeline-strip");
  strip.innerHTML = "";
  state.keyframes.forEach((kf, idx) => {
    const card = document.createElement("div");
    card.className = "kf-card" + (idx === state.selectedKf ? " selected" : "");
    const bar = document.createElement("div");
    bar.className = "kf-bar";
    for (let i = 0; i < kf.pixels.length; i += 2) {
      const sp = document.createElement("span");
      const [r, g, b] = kf.pixels[i];
      sp.style.background = `rgb(${r},${g},${b})`;
      bar.appendChild(sp);
    }
    const meta = document.createElement("div");
    meta.className = "kf-meta";
    meta.textContent = `#${idx + 1} · ${kf.duration_ms}ms · ${kf.transition}`;
    card.appendChild(bar);
    card.appendChild(meta);
    card.addEventListener("click", () => {
      state.selectedKf = idx;
      $("kf-duration").value = kf.duration_ms;
      $("kf-transition").value = kf.transition;
      renderTimeline();
    });
    strip.appendChild(card);
  });
}

$("btn-kf-capture").addEventListener("click", () => {
  state.keyframes.push({
    duration_ms: Number($("kf-duration").value) || 600,
    transition: $("kf-transition").value,
    pixels: state.pixels.map((c) => [...c]),
  });
  state.selectedKf = state.keyframes.length - 1;
  renderTimeline();
});
$("btn-kf-dup").addEventListener("click", () => {
  if (state.selectedKf < 0) return;
  const src = state.keyframes[state.selectedKf];
  state.keyframes.splice(state.selectedKf + 1, 0, {
    duration_ms: src.duration_ms,
    transition: src.transition,
    pixels: src.pixels.map((c) => [...c]),
  });
  state.selectedKf += 1;
  renderTimeline();
});
$("btn-kf-left").addEventListener("click", () => {
  const i = state.selectedKf;
  if (i <= 0) return;
  [state.keyframes[i - 1], state.keyframes[i]] = [state.keyframes[i], state.keyframes[i - 1]];
  state.selectedKf = i - 1;
  renderTimeline();
});
$("btn-kf-right").addEventListener("click", () => {
  const i = state.selectedKf;
  if (i < 0 || i >= state.keyframes.length - 1) return;
  [state.keyframes[i + 1], state.keyframes[i]] = [state.keyframes[i], state.keyframes[i + 1]];
  state.selectedKf = i + 1;
  renderTimeline();
});
$("btn-kf-del").addEventListener("click", () => {
  if (state.selectedKf < 0) return;
  state.keyframes.splice(state.selectedKf, 1);
  state.selectedKf = Math.min(state.selectedKf, state.keyframes.length - 1);
  renderTimeline();
});
$("kf-duration").addEventListener("change", () => {
  if (state.selectedKf >= 0) {
    state.keyframes[state.selectedKf].duration_ms = Math.max(50, Number($("kf-duration").value));
    renderTimeline();
  }
});
$("kf-transition").addEventListener("change", () => {
  if (state.selectedKf >= 0) {
    state.keyframes[state.selectedKf].transition = $("kf-transition").value;
    renderTimeline();
  }
});
$("btn-kf-load-editor").addEventListener("click", () => {
  if (state.selectedKf < 0) return;
  state.pixels = state.keyframes[state.selectedKf].pixels.map((c) => [...c]);
  drawWreath(); renderLinearStrip();
  document.querySelector('[data-tab="pixels"]').click();
});

$("btn-tl-play").addEventListener("click", async () => {
  try {
    if (!state.keyframes.length) throw new Error("Add at least one keyframe first");
    await api("/api/timeline/play", "POST", {
      timeline: {
        name: $("tl-name").value || "Custom",
        loop: $("tl-loop").checked,
        keyframes: state.keyframes,
      },
      speed: Number($("tl-speed").value) / 100,
      fps: Number($("slider-fps").value),
    });
    showToast("Playing timeline");
    refreshState();
  } catch (e) { showToast(e.message, true); }
});
$("btn-tl-stop").addEventListener("click", async () => {
  await api("/api/effect", "POST", { stop: true });
  refreshState();
});
$("btn-tl-save").addEventListener("click", async () => {
  try {
    const tl = { name: $("tl-name").value, loop: $("tl-loop").checked, keyframes: state.keyframes };
    await api("/api/timelines", "POST", { op: "save", timeline: tl });
    showToast(`Saved timeline '${tl.name}'`);
    refreshState();
  } catch (e) { showToast(e.message, true); }
});

function renderSavedTimelines(timelines) {
  const list = $("timelines-list");
  list.innerHTML = "";
  for (const [name, tl] of Object.entries(timelines || {})) {
    const chip = document.createElement("div");
    chip.className = "saved-chip";
    const loadBtn = document.createElement("button");
    loadBtn.textContent = `${name} (${(tl.keyframes || []).length}f)`;
    loadBtn.addEventListener("click", () => {
      $("tl-name").value = tl.name || name;
      $("tl-loop").checked = !!tl.loop;
      state.keyframes = (tl.keyframes || []).map((k) => ({
        duration_ms: k.duration_ms,
        transition: k.transition,
        pixels: k.pixels.map((c) => [...c]),
      }));
      state.selectedKf = state.keyframes.length ? 0 : -1;
      renderTimeline();
    });
    const delBtn = document.createElement("button");
    delBtn.className = "del";
    delBtn.textContent = "×";
    delBtn.addEventListener("click", async () => {
      await api("/api/timelines", "POST", { op: "delete", name });
      refreshState();
    });
    chip.appendChild(loadBtn);
    chip.appendChild(delBtn);
    list.appendChild(chip);
  }
}

// --- Developer Console ---
function updateWirePreview() {
  const clean = $("dev-raw-hex").value.replace(/\s+/g, "");
  if (clean.length % 2 !== 0 || !/^[0-9a-fA-F]*$/.test(clean) || !clean.length) {
    $("dev-wire-preview").textContent = "Invalid even-length hex string";
    return;
  }
  const inner = [];
  for (let i = 0; i < clean.length; i += 2) inner.push(parseInt(clean.slice(i, i + 2), 16));
  const frame = [0xb0, 0xb1, 0xb2, 0xb3, 0x00, 0x01, 0x02, 0x00, (inner.length >> 8) & 0xff, inner.length & 0xff, ...inner];
  const cs = frame.reduce((a, b) => (a + b) & 0xff, 0);
  frame.push(cs);
  $("dev-wire-preview").textContent = frame.map((b) => b.toString(16).padStart(2, "0")).join(" ");
}

$("dev-raw-hex").addEventListener("input", updateWirePreview);
document.querySelectorAll("[data-preset-hex]").forEach((btn) => {
  btn.addEventListener("click", () => {
    $("dev-raw-hex").value = btn.dataset.presetHex;
    updateWirePreview();
  });
});

$("btn-dev-send").addEventListener("click", async () => {
  try {
    const res = await api("/api/dev/raw", "POST", {
      hex: $("dev-raw-hex").value,
      expect_response: $("dev-expect-resp").checked,
      confirmed: $("dev-confirm-write").checked,
    });
    $("dev-raw-resp").textContent = `TX inner: ${res.tx_inner_hex}\nRX inner: ${res.rx_inner_hex || "<none>"}`;
    refreshPackets();
  } catch (e) { showToast(e.message, true); }
});

async function refreshPackets() {
  try {
    const res = await api("/api/dev/packets?limit=80");
    const tbody = $("dev-packets-body");
    tbody.innerHTML = "";
    for (const p of res.packets) {
      const tr = document.createElement("tr");
      const dt = new Date(p.timestamp * 1000).toLocaleTimeString();
      tr.innerHTML = `
        <td class="mono">${dt}</td>
        <td class="${p.direction === "TX" ? "dir-tx" : "dir-rx"}">${p.direction}</td>
        <td>${p.transport}</td>
        <td class="mono">${p.seq ?? "—"}</td>
        <td class="mono">${p.opcode}</td>
        <td>${p.error ? `<span style="color:#fca5a5">${p.error}</span>` : p.summary}</td>
        <td class="mono">${p.latency_ms != null ? p.latency_ms + "ms" : "—"}</td>
        <td class="mono" title="${p.wire_hex}">${p.inner_hex.slice(0, 64)}${p.inner_hex.length > 64 ? "…" : ""}</td>
      `;
      tbody.appendChild(tr);
    }
  } catch (_) {}
}

$("btn-dev-refresh").addEventListener("click", refreshPackets);
$("btn-dev-clear").addEventListener("click", async () => {
  await api("/api/dev/clear", "POST", {});
  refreshPackets();
});

setInterval(() => {
  if ($("tab-developer").classList.contains("active") && $("dev-autopoll").checked) {
    refreshPackets();
  }
}, 2000);

updateWirePreview();
refreshState();
