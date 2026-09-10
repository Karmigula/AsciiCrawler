// Draw the frames the server sends. The page has no game in it: it paints
// what arrives and does nothing else, which is why it stays small.

const canvas = document.getElementById("view");
const ctx = canvas.getContext("2d", { alpha: false });
const statusLine = document.getElementById("status");
const hudBox = document.getElementById("hud");
const logBox = document.getElementById("log");
const viewerBox = document.getElementById("viewers");

let latest = null;
let socket = null;
let retryIn = 1000;

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
  // Fit the grid to the canvas, keeping cells on whole pixels so the glyphs
  // stay crisp; a half-pixel cell turns a monospace grid into porridge.
  const scale = window.devicePixelRatio || 1;
  const box = canvas.parentElement.getBoundingClientRect();
  const cellW = Math.max(4, Math.floor((box.width * scale) / frame.cols));
  const cellH = Math.floor(cellW * 1.6);
  canvas.width = cellW * frame.cols;
  canvas.height = cellH * frame.rows;
  canvas.style.width = canvas.width / scale + "px";
  canvas.style.height = canvas.height / scale + "px";
  return { cellW, cellH };
}

function draw(frame) {
  const { cellW, cellH } = layout(frame);
  const palette = frame.palette;

  ctx.fillStyle = "#07070a";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.font = `${cellH - 2}px "IBM Plex Mono", ui-monospace, Menlo, Consolas, monospace`;
  ctx.textBaseline = "top";

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
    for (let x = 0; x < frame.cols; x++) {
      const glyph = row[x];
      if (glyph === " " || fg[x] < 0) continue;
      ctx.fillStyle = palette[fg[x]];
      ctx.fillText(glyph, x * cellW, y * cellH);
    }
  }

  const [ax, ay, acolor] = frame.agent;
  ctx.fillStyle = acolor;
  ctx.fillText("@", ax * cellW, ay * cellH);

  hudBox.replaceChildren(...frame.hud.map(([text, color]) => tinted(text, color)));
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
    setInterval(() => {
      if (socket && socket.readyState === WebSocket.OPEN) socket.send("watching");
    }, 25000);
  });

  socket.addEventListener("message", (event) => {
    latest = JSON.parse(event.data);
    draw(latest);
  });

  socket.addEventListener("close", () => {
    statusLine.textContent = "reconnecting…";
    setTimeout(connect, retryIn);
    retryIn = Math.min(retryIn * 2, 15000);  // back off; a sleeping free instance takes a moment
  });
}

window.addEventListener("resize", () => {
  if (latest) draw(latest);
});

connect();
