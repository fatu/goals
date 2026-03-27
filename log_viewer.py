"""Web-based log viewer for completed goals."""

import json
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

LOG_FILE = Path(__file__).parent / "completed_log.json"
FOCUS_LOG_FILE = Path(__file__).parent / "focus_log.json"
PORT = 5051


def load_log() -> list:
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            return json.load(f)
    return []


def load_focus_log() -> list:
    if FOCUS_LOG_FILE.exists():
        with open(FOCUS_LOG_FILE) as f:
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
  <h1>📊 <span>Activity Log</span></h1>

  <div class="section" style="background:#16213e;border-radius:16px;padding:24px;margin-bottom:24px;border:1px solid #0f3460;">
    <div style="font-size:18px;font-weight:600;margin-bottom:16px;">⏱ Daily Focus Time</div>
    <div class="stats" id="focus-stats"></div>
    <div id="focus-list"></div>
  </div>

  <div class="section" style="background:#16213e;border-radius:16px;padding:24px;margin-bottom:24px;border:1px solid #0f3460;">
    <div style="font-size:18px;font-weight:600;margin-bottom:16px;">✅ Completed Goals</div>
    <div class="stats" id="stats"></div>
    <div id="log-list"></div>
  </div>
</div>
<script>
function formatDuration(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (h > 0) return h + 'h ' + String(m).padStart(2,'0') + 'm';
  return m + 'm';
}

async function load() {
  const [logRes, focusRes] = await Promise.all([
    fetch('/api/log'),
    fetch('/api/focus_log'),
  ]);
  const log = await logRes.json();
  const focusLog = await focusRes.json();

  // Focus time
  const focusStats = document.getElementById('focus-stats');
  const focusList = document.getElementById('focus-list');
  if (focusLog.length === 0) {
    focusStats.textContent = 'No focus time recorded yet';
  } else {
    const totalSec = focusLog.reduce((s, e) => s + e.seconds, 0);
    const avgSec = Math.round(totalSec / focusLog.length);
    // Weekly average with comparison
    const weeks = {};
    const now = new Date();
    const jan1Now = new Date(now.getFullYear(), 0, 1);
    const currentWk = Math.ceil(((now - jan1Now) / 86400000 + jan1Now.getDay() + 1) / 7);
    const currentWeekKey = now.getFullYear() + '-W' + currentWk;
    focusLog.forEach(e => {
      const d = new Date(e.date + 'T00:00:00');
      const jan1 = new Date(d.getFullYear(), 0, 1);
      const wk = Math.ceil(((d - jan1) / 86400000 + jan1.getDay() + 1) / 7);
      const key = d.getFullYear() + '-W' + wk;
      weeks[key] = (weeks[key] || 0) + e.seconds;
    });
    const weekKeys = Object.keys(weeks);
    const pastWeekKeys = weekKeys.filter(k => k !== currentWeekKey);
    const weeklyAvgSec = pastWeekKeys.length > 0 ? Math.round(pastWeekKeys.reduce((s, k) => s + weeks[k], 0) / pastWeekKeys.length) : 0;
    const currentWeekSec = weeks[currentWeekKey] || 0;
    let statsText = focusLog.length + ' days tracked | total ' + formatDuration(totalSec) + ' | avg ' + formatDuration(avgSec) + '/day | weekly avg ' + formatDuration(weeklyAvgSec);
    if (currentWeekSec > 0 && pastWeekKeys.length > 0) {
      const diff = currentWeekSec - weeklyAvgSec;
      const arrow = diff >= 0 ? '▲' : '▼';
      const color = diff >= 0 ? '#2ecc71' : '#e74c3c';
      statsText += ' | this week ' + formatDuration(currentWeekSec) + ' <span style="color:' + color + '">' + arrow + ' ' + formatDuration(Math.abs(diff)) + '</span>';
    } else if (currentWeekSec > 0) {
      statsText += ' | this week ' + formatDuration(currentWeekSec);
    }
    focusStats.innerHTML = statsText;
    const reversed = [...focusLog].reverse();
    focusList.innerHTML = reversed.map(entry => {
      const dur = formatDuration(entry.seconds);
      const barLen = Math.min(Math.round(entry.seconds / 3600 * 10), 20);
      const bar = '▓'.repeat(barLen) + '░'.repeat(Math.max(10 - barLen, 0));
      return '<div class="log-item">' +
        '<div class="log-task">📅 ' + entry.date + '</div>' +
        '<div class="log-dates">' +
          '<span style="font-family:monospace;color:#667eea;">' + bar + '</span>' +
          '<span class="badge">' + dur + '</span>' +
        '</div>' +
      '</div>';
    }).join('');
  }

  // Completed goals
  const stats = document.getElementById('stats');
  const list = document.getElementById('log-list');
  if (log.length === 0) {
    stats.textContent = 'No completed tasks yet';
  } else {
    const totalDays = log.reduce((s, e) => s + e.days, 0);
    const avgDays = (totalDays / log.length).toFixed(1);
    stats.textContent = log.length + ' tasks completed | avg ' + avgDays + ' days per task';
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
        elif self.path == "/api/focus_log":
            data = load_focus_log()
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
