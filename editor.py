"""Lightweight web editor for goals — uses only stdlib, no Flask."""

import json
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ICLOUD_DIR = Path.home() / "Library/Mobile Documents/iCloud~com~fangbotu~goalsapp/Documents"
ICLOUD_DIR.mkdir(parents=True, exist_ok=True)
DATA_FILE = ICLOUD_DIR / "goals.json"
PORT = 5050

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Goals Editor</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #1a1a2e;
    color: #eee;
    min-height: 100vh;
    padding: 40px 20px;
  }
  .container { max-width: 600px; margin: 0 auto; }
  h1 {
    text-align: center;
    font-size: 28px;
    margin-bottom: 30px;
  }
  h1 span {
    background: linear-gradient(135deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .section {
    background: #16213e;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 24px;
    border: 1px solid #0f3460;
  }
  .section-header {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 16px;
  }
  .goal-item {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 12px;
    background: #1a1a2e;
    border-radius: 10px;
    margin-bottom: 8px;
    transition: background 0.15s;
  }
  .goal-item:hover { background: #1f2945; }
  .goal-item.dragging { opacity: 0.4; }
  .goal-item.drag-over { border-top: 2px solid #667eea; }
  .drag-handle {
    cursor: grab;
    color: #555;
    font-size: 16px;
    user-select: none;
  }
  .drag-handle:active { cursor: grabbing; }
  .goal-item input[type="text"] {
    flex: 1;
    background: transparent;
    border: none;
    color: #eee;
    font-size: 15px;
    outline: none;
    padding: 4px 0;
    border-bottom: 1px solid transparent;
  }
  .goal-item input[type="text"]:focus {
    border-bottom-color: #667eea;
  }
  .btn-remove {
    background: none;
    border: none;
    color: #e74c3c;
    cursor: pointer;
    font-size: 18px;
    padding: 4px 8px;
    border-radius: 6px;
    opacity: 0;
    transition: opacity 0.15s, background 0.15s;
  }
  .goal-item:hover .btn-remove { opacity: 1; }
  .btn-remove:hover { background: rgba(231, 76, 60, 0.15); }
  .btn-add {
    display: flex;
    align-items: center;
    gap: 6px;
    background: none;
    border: 1px dashed #0f3460;
    color: #667eea;
    cursor: pointer;
    font-size: 14px;
    padding: 10px 16px;
    border-radius: 10px;
    width: 100%;
    margin-top: 8px;
    transition: all 0.15s;
  }
  .btn-add:hover {
    background: rgba(102, 126, 234, 0.1);
    border-color: #667eea;
  }
  .actions {
    display: flex;
    gap: 12px;
  }
  .btn-save {
    flex: 1;
    padding: 14px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s;
  }
  .btn-save:hover { opacity: 0.9; }
  .btn-save:active { transform: scale(0.98); }
  .toast {
    position: fixed;
    bottom: 30px;
    left: 50%;
    transform: translateX(-50%) translateY(100px);
    background: #2ecc71;
    color: white;
    padding: 12px 24px;
    border-radius: 10px;
    font-weight: 500;
    transition: transform 0.3s ease;
    z-index: 100;
  }
  .toast.show { transform: translateX(-50%) translateY(0); }
  .hint {
    text-align: center;
    color: #555;
    font-size: 13px;
    margin-top: 16px;
  }
</style>
</head>
<body>
<div class="container">
  <h1>🎯 <span>Goals Editor</span></h1>

  <div class="section">
    <div class="section-header">📅 Daily Goals</div>
    <div id="daily-list"></div>
    <button class="btn-add" onclick="addGoal('daily')">➕ Add Daily Goal</button>
  </div>

  <div class="section">
    <div class="section-header">🏆 Year Goals</div>
    <div id="year-list"></div>
    <button class="btn-add" onclick="addGoal('year')">➕ Add Year Goal</button>
  </div>

  <div class="actions">
    <button class="btn-save" onclick="save()">💾 Save Changes</button>
  </div>
  <p class="hint">After saving, click 🔃 Reload Goals in the menu bar.</p>
</div>

<div class="toast" id="toast">Saved!</div>

<script>
let goals = {};

async function load() {
  const res = await fetch('/api/goals');
  goals = await res.json();
  render();
}

function render() {
  renderList('daily-list', goals.daily_goals || [], 'daily');
  renderList('year-list', goals.year_goals || [], 'year');
}

function renderList(containerId, items, type) {
  const el = document.getElementById(containerId);
  el.innerHTML = '';
  items.forEach((item, i) => {
    const div = document.createElement('div');
    div.className = 'goal-item';
    div.draggable = true;
    div.dataset.index = i;
    div.dataset.type = type;

    const handle = document.createElement('span');
    handle.className = 'drag-handle';
    handle.textContent = '⠿';

    const input = document.createElement('input');
    input.type = 'text';
    input.value = item.text;
    input.addEventListener('input', () => {
      const key = type === 'daily' ? 'daily_goals' : 'year_goals';
      goals[key][i].text = input.value;
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        input.blur();
        save();
      }
    });

    const btn = document.createElement('button');
    btn.className = 'btn-remove';
    btn.textContent = '✕';
    btn.addEventListener('click', () => removeGoal(type, i));

    div.appendChild(handle);
    div.appendChild(input);
    div.appendChild(btn);

    div.addEventListener('dragstart', onDragStart);
    div.addEventListener('dragover', onDragOver);
    div.addEventListener('dragleave', onDragLeave);
    div.addEventListener('drop', onDrop);
    div.addEventListener('dragend', onDragEnd);

    el.appendChild(div);
  });
}

function addGoal(type) {
  const key = type === 'daily' ? 'daily_goals' : 'year_goals';
  if (!goals[key]) goals[key] = [];
  const today = new Date().toISOString().slice(0, 10);
  const newGoal = type === 'daily' ? { text: '', added_date: today } : { text: '' };
  goals[key].push(newGoal);
  render();
  const list = document.getElementById(type === 'daily' ? 'daily-list' : 'year-list');
  const inputs = list.querySelectorAll('input[type="text"]');
  if (inputs.length > 0) inputs[inputs.length - 1].focus();
}

function removeGoal(type, idx) {
  const key = type === 'daily' ? 'daily_goals' : 'year_goals';
  goals[key].splice(idx, 1);
  render();
}

let dragItem = null;

function onDragStart(e) {
  dragItem = { type: e.currentTarget.dataset.type, index: parseInt(e.currentTarget.dataset.index) };
  e.currentTarget.classList.add('dragging');
}

function onDragOver(e) {
  e.preventDefault();
  const target = e.currentTarget;
  if (target.dataset.type === dragItem?.type) {
    target.classList.add('drag-over');
  }
}

function onDragLeave(e) {
  e.currentTarget.classList.remove('drag-over');
}

function onDrop(e) {
  e.preventDefault();
  e.currentTarget.classList.remove('drag-over');
  const toType = e.currentTarget.dataset.type;
  const toIndex = parseInt(e.currentTarget.dataset.index);
  if (dragItem && dragItem.type === toType && dragItem.index !== toIndex) {
    const key = toType === 'daily' ? 'daily_goals' : 'year_goals';
    const [moved] = goals[key].splice(dragItem.index, 1);
    goals[key].splice(toIndex, 0, moved);
    render();
  }
}

function onDragEnd(e) {
  e.currentTarget.classList.remove('dragging');
  dragItem = null;
}

async function save() {
  goals.daily_goals = (goals.daily_goals || []).filter(g => g.text.trim());
  goals.year_goals = (goals.year_goals || []).filter(g => g.text.trim());

  await fetch('/api/goals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(goals)
  });
  render();
  const toast = document.getElementById('toast');
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2000);
}

load();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/goals":
            data = json.loads(DATA_FILE.read_text())
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())

    def do_POST(self):
        if self.path == "/api/goals":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

    def log_message(self, format, *args):
        pass  # suppress logs


if __name__ == "__main__":
    # Kill any existing server on this port
    import subprocess as _sp
    _sp.run(f"lsof -ti:{PORT} | xargs kill -9 2>/dev/null", shell=True)

    HTTPServer.allow_reuse_address = True
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    threading.Timer(0.5, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
