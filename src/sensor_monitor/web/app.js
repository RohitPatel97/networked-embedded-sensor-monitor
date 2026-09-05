"use strict";

const state = { temperatures: [], alerts: [] };
const $ = (selector) => document.querySelector(selector);
const connection = $("#connection");

function setConnection(label, className) {
  connection.className = `connection ${className}`;
  connection.lastChild.textContent = ` ${label}`;
}

function renderReading(reading) {
  $("#temperature").textContent = reading.temperature_c.toFixed(1);
  $("#pressure").textContent = reading.pressure_hpa.toFixed(1);
  $("#device-id").textContent = reading.device_id;
  state.temperatures.push(reading.temperature_c);
  if (state.temperatures.length > 60) state.temperatures.shift();
  drawChart();
}

function renderAlerts(alerts) {
  if (!alerts?.length) return;
  const known = new Set(state.alerts.map((alert) => alert.id));
  state.alerts.unshift(...alerts.filter((alert) => !known.has(alert.id)));
  state.alerts = state.alerts.slice(0, 12);
  $("#alert-count").textContent = `${state.alerts.length} events`;
  $("#alerts").innerHTML = state.alerts.map((alert) => `
    <li>
      <span class="severity ${alert.severity}">${alert.severity}</span>
      <span class="device">${escapeHtml(alert.device_id)}</span>
      <span class="message">${escapeHtml(alert.message)}</span>
      <time>${new Date(alert.created_at).toLocaleTimeString()}</time>
    </li>`).join("");
}

function escapeHtml(value) {
  const node = document.createElement("span");
  node.textContent = value;
  return node.innerHTML;
}

function drawChart() {
  const canvas = $("#chart");
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.scale(ratio, ratio);
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = "#263b36";
  ctx.lineWidth = 1;
  for (let row = 1; row < 5; row += 1) {
    ctx.beginPath(); ctx.moveTo(0, (height / 5) * row); ctx.lineTo(width, (height / 5) * row); ctx.stroke();
  }
  if (state.temperatures.length < 2) return;
  const min = Math.min(...state.temperatures) - 1;
  const max = Math.max(...state.temperatures) + 1;
  ctx.strokeStyle = "#6ee7b7";
  ctx.lineWidth = 2;
  ctx.beginPath();
  state.temperatures.forEach((value, index) => {
    const x = (index / 59) * width;
    const y = height - ((value - min) / (max - min || 1)) * height;
    index ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
  });
  ctx.stroke();
}

async function refreshSnapshot() {
  const response = await fetch("/api/v1/snapshot");
  if (!response.ok) throw new Error("snapshot unavailable");
  const snapshot = await response.json();
  $("#samples").textContent = snapshot.stats.frames_accepted;
  if (snapshot.devices.length) {
    $("#device-state").textContent = snapshot.devices[0].state;
    $("#device-id").textContent = snapshot.devices[0].device_id;
    const readingsResponse = await fetch(`/api/v1/devices/${encodeURIComponent(snapshot.devices[0].device_id)}/readings?limit=60`);
    if (readingsResponse.ok) {
      const readings = await readingsResponse.json();
      state.temperatures = readings.slice(0, -1).map((reading) => reading.temperature_c);
      if (readings.length) renderReading(readings.at(-1));
    }
  }
  renderAlerts([...snapshot.alerts].reverse());
}

function connect() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const socket = new WebSocket(`${protocol}://${location.host}/ws/telemetry`);
  socket.addEventListener("open", () => setConnection("Live", "online"));
  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);
    if (payload.type === "telemetry") {
      renderReading(payload.reading);
      renderAlerts(payload.alerts);
      const samples = Number($("#samples").textContent || 0) + 1;
      $("#samples").textContent = samples;
      if (payload.health) $("#device-state").textContent = payload.health.state;
    } else if (payload.type === "snapshot") {
      $("#samples").textContent = payload.stats.frames_accepted;
      renderAlerts([...payload.alerts].reverse());
    } else if (payload.type === "heartbeat") {
      $("#samples").textContent = payload.stats.frames_accepted;
      if (payload.devices?.length) $("#device-state").textContent = payload.devices[0].state;
    }
  });
  socket.addEventListener("close", () => { setConnection("Reconnecting", "offline"); setTimeout(connect, 1500); });
}

$("#fault-controls").addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-mode]");
  if (!button) return;
  const response = await fetch("/api/v1/simulator/fault", {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ mode: button.dataset.mode }),
  });
  if (response.ok) {
    document.querySelectorAll("#fault-controls button").forEach((item) => item.classList.toggle("active", item === button));
  } else {
    button.textContent = "Unavailable for serial source";
  }
});

window.addEventListener("resize", drawChart);
refreshSnapshot().catch(() => {}).finally(connect);
