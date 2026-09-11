// Draw the frames the server sends. The page has no game in it: it paints
// what arrives and does nothing else, which is why it stays small.

const CELL_RATIO = 1.6; // a character cell is taller than it is wide

// How big one cell can be and still fit the whole grid in the space given.
// Pure, and separated out, because getting this wrong is not a subtle bug: it
// sized cells off the width alone once, and on a wide window the grid ran off
// the bottom of the screen.
function fitCells(availW, availH, cols, rows, ratio = CELL_RATIO) {
  const byWidth = availW / cols;
  const byHeight = availH / (rows * ratio);
  const cellW = Math.max(3, Math.floor(Math.min(byWidth, byHeight)));
  return { cellW, cellH: Math.round(cellW * ratio) };
}

if (typeof module !== "undefined") module.exports = { fitCells, expand };

const canvas = typeof document !== "undefined" && document.getElementById("view");
const ctx = canvas ? canvas.getContext("2d", { alpha: false }) : null;
const statusLine = canvas && document.getElementById("status");
const hudBox = canvas && document.getElementById("hud");
const wornBox = canvas && document.getElementById("worn");
const logBox = canvas && document.getElementById("log");
const viewerBox = canvas && document.getElementById("viewers");

let latest = null;
let socket = null;
let retryIn = 1000;
let keepAlive = null;

// Colours arrive run-length encoded as [index, count, index, count, ...].
function expand(runs, width) {
  const out = new Array(width);
  let at = 0;
  for (let i = 0; i < runs.length; i += 2) {
    const value = runs[i];
    for (let n = runs[i + 1]; n > 0 && at < width; n--) out[at++] = value;
  }
  while (at < width) out[at++] = -1;
  return out;
}

function layout(frame) {
  const scale = window.devicePixelRatio || 1;
  const stage = canvas.parentElement;
  const status = statusLine.getBoundingClientRect().height;
  const { cellW, cellH } = fitCells(
    stage.clientWidth,
    Math.max(120, stage.clientHeight - status - 12),
    frame.cols,
    frame.rows
  );

  const cssW = cellW * frame.cols;
  const cssH = cellH * frame.rows;
  const wantW = Math.round(cssW * scale);
  const wantH = Math.round(cssH * scale);
  if (canvas.width !== wantW || canvas.height !== wantH) {
    // Resizing the backing store clears it and resets the context, so the
    // device-pixel scaling has to go back on afterwards, not before.
    canvas.width = wantW;
    canvas.height = wantH;
    canvas.style.width = cssW + "px";
    canvas.style.height = cssH + "px";
  }
  ctx.setTransform(scale, 0, 0, scale, 0, 0);
  return { cellW, cellH, cssW, cssH };
}

function draw(frame) {
  const { cellW, cellH, cssW, cssH } = layout(frame);
  const palette = frame.palette;

  ctx.fillStyle = "#07070a";
  ctx.fillRect(0, 0, cssW, cssH);
  ctx.font = `${cellH}px "IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace`;
  ctx.textBaseline = "middle";
  ctx.textAlign = "center";

  for (let y = 0; y < frame.rows; y++) {
    const bg = expand(frame.bg[y], frame.cols);
    for (let x = 0; x < frame.cols; x++) {
      if (bg[x] < 0) continue;
      ctx.fillStyle = palette[bg[x]];
      ctx.fillRect(x * cellW, y * cellH, cellW, cellH);
    }
  }
  for (let y = 0; y < frame.rows; y++) {
    const row = frame.glyphs[y];
    const fg = expand(frame.fg[y], frame.cols);
    const midY = y * cellH + cellH / 2;
    for (let x = 0; x < frame.cols; x++) {
      const glyph = row[x];
      if (glyph === " " || fg[x] < 0) continue;
      ctx.fillStyle = palette[fg[x]];
      ctx.fillText(glyph, x * cellW + cellW / 2, midY);
    }
  }

  const [ax, ay, acolor] = frame.agent;
  ctx.fillStyle = acolor;
  ctx.fillText("@", ax * cellW + cellW / 2, ay * cellH + cellH / 2);

  hudBox.replaceChildren(...frame.hud.map(([text, color]) => tinted(text, color)));
  wornBox.replaceChildren(
    ...(frame.worn || []).map(([text, color]) => tinted(text, color))
  );
  logBox.replaceChildren(...frame.log.map(([text, color]) => tinted(text, color)));
  statusLine.textContent = `${frame.biome} — tick ${frame.tick.toLocaleString()}`;
  viewerBox.textContent =
    frame.viewers === 1 ? "1 watching" : `${frame.viewers} watching`;
}

function tinted(text, color) {
  const line = document.createElement("span");
  line.textContent = text + "\n";
  line.style.color = color;
  return line;
}

function connect() {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  socket = new WebSocket(`${scheme}://${location.host}/ws`);

  socket.addEventListener("open", () => {
    retryIn = 1000;
    // The server ignores what we send; this keeps the socket from being
    // reaped by an idle proxy, which free hosts are fond of doing.
    //
    // Cleared before a new one starts. Every reconnect runs this handler, so
    // an interval left behind by the last connection would stay forever, and
    // a tab left open through a few network hiccups would end up sending its
    // keep-alive several times over.
    clearInterval(keepAlive);
    keepAlive = setInterval(() => {
      if (socket && socket.readyState === WebSocket.OPEN) socket.send("watching");
    }, 25000);
  });

  socket.addEventListener("message", (event) => {
    latest = JSON.parse(event.data);
    draw(latest);
  });

  socket.addEventListener("close", () => {
    clearInterval(keepAlive);
    keepAlive = null;
    statusLine.textContent = "reconnecting…";
    setTimeout(connect, retryIn);
    retryIn = Math.min(retryIn * 2, 15000); // a sleeping free instance takes a moment
  });
}

if (canvas) {
  let pending = null;
  window.addEventListener("resize", () => {
    // Resize fires in bursts while a window is dragged; one redraw at the end
    // of the burst is enough and keeps a big grid from stuttering.
    clearTimeout(pending);
    pending = setTimeout(() => latest && draw(latest), 60);
  });
  connect();
}
