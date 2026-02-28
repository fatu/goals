"""Web-based log viewer for completed goals."""

import json
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

LOG_FILE = Path(__file__).parent / "completed_log.json"
PORT = 5051


def load_log() -> list:
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            return json.load(f)
    return []


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Completed Goals Log</title>
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
    margin-bottom: 8px;
  }
  h1 span {
    background: linear-gradient(135deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .stats {
    text-align: center;
    color: #888;
    font-size: 14px;
    margin-bottom: 30px;
  }
  .empty {
    text-align: center;
    color: #555;
    font-size: 16px;
    margin-top: 60px;
  }
  .log-item {
    background: #16213e;
    border-radius: 12px;
    padding: 16px 20px;
    margin-bottom: 12px;
    border: 1px solid #0f3460;
    transition: background 0.15s;
  }
  .log-item:hover { background: #1a2744; }
  .log-task {
    font-size: 16px;
    font-weight: 500;
    margin-bottom: 8px;
  }
  .log-dates {
    font-size: 13px;
    color: #888;
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }
  .log-dates .badge {
    background: #0f3460;
    padding: 2px 8px;
    border-radius: 6px;
    color: #667eea;
    font-weight: 500;
  }
  .log-dates .days-1 { color: #2ecc71; background: rgba(46,204,113,0.1); }
  .log-dates .days-long { color: #e67e22; background: rgba(230,126,34,0.1); }
</style>
</head>
<body>
<div class="container">
  <h1>📊 <span>Completed Goals</span></h1>
  <div class="stats" id="stats"></div>
  <div id="log-list"></div>
</div>
<script>
async function load() {
  const res = await fetch('/api/log');
  const log = await res.json();

  const stats = document.getElementById('stats');
  const list = document.getElementById('log-list');

  if (log.length === 0) {
    stats.textContent = 'No completed tasks yet';
    list.innerHTML = '<div class="empty">Complete daily goals and they will appear here the next day.</div>';
    return;
  }

  const totalDays = log.reduce((s, e) => s + e.days, 0);
  const avgDays = (totalDays / log.length).toFixed(1);
  stats.textContent = log.length + ' tasks completed | avg ' + avgDays + ' days per task';

  // Show newest first
  const reversed = [...log].reverse();
  list.innerHTML = reversed.map(entry => {
    const daysClass = entry.days === 1 ? 'days-1' : entry.days >= 7 ? 'days-long' : '';
    return '<div class="log-item">' +
      '<div class="log-task">✅ ' + escHtml(entry.text) + '</div>' +
      '<div class="log-dates">' +
        '<span>📥 ' + entry.added_date + '</span>' +
        '<span>✔️ ' + entry.completed_date + '</span>' +
        '<span class="badge ' + daysClass + '">' + entry.days + ' day' + (entry.days !== 1 ? 's' : '') + '</span>' +
      '</div>' +
    '</div>';
  }).join('');
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

load();
</script>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/log":
            data = load_log()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode())

    def log_message(self, format, *args):
        pass


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
