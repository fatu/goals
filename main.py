"""Goals Sticker — a macOS menu bar app to track daily + yearly goals."""

import json
import os
import re
import subprocess
import sys
import textwrap
import threading
import uuid
import webbrowser
from datetime import date, datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import AppKit
import rumps

MENU_WIDTH = 30  # characters per line

# iCloud Drive shared container (syncs with iOS app)
ICLOUD_DIR = Path.home() / "Library/Mobile Documents/iCloud~com~fangbotu~goalsapp/Documents"
ICLOUD_DIR.mkdir(parents=True, exist_ok=True)

DATA_FILE = ICLOUD_DIR / "goals.json"
STATE_FILE = ICLOUD_DIR / ".daily_state.json"
YEAR_STATE_FILE = ICLOUD_DIR / ".year_state.json"
LOG_FILE = ICLOUD_DIR / "completed_log.json"
FOCUS_LOG_FILE = ICLOUD_DIR / "focus_log.json"
FOCUS_FILE = ICLOUD_DIR / ".focus_state.json"
ATTACHMENTS_DIR = ICLOUD_DIR / "attachments"

# One-time migration from local directory to iCloud
_LOCAL_DIR = Path(__file__).parent
_MIGRATE_FILES = [
    "goals.json", ".daily_state.json", ".year_state.json",
    "completed_log.json", "focus_log.json", ".focus_state.json",
]
for _fname in _MIGRATE_FILES:
    _src = _LOCAL_DIR / _fname
    _dst = ICLOUD_DIR / _fname
    if _src.exists() and not _dst.exists():
        import shutil
        shutil.copy2(_src, _dst)
_local_attach = _LOCAL_DIR / "attachments"
if _local_attach.exists() and not ATTACHMENTS_DIR.exists():
    import shutil
    shutil.copytree(_local_attach, ATTACHMENTS_DIR)

EDITOR_PORT = 5050
LOG_PORT = 5051


def load_goals() -> dict:
    with open(DATA_FILE) as f:
        return json.load(f)


def save_goals(data: dict) -> None:
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_daily_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            state = json.load(f)
        if state.get("date") == str(date.today()):
            state.setdefault("fired_alarms", [])
            return state
    return {"date": str(date.today()), "checked": {}, "fired_alarms": []}


def save_daily_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_year_state() -> dict:
    current_year = str(date.today().year)
    if YEAR_STATE_FILE.exists():
        with open(YEAR_STATE_FILE) as f:
            state = json.load(f)
        if state.get("year") == current_year:
            return state
    return {"year": current_year, "checked": {}}


def save_year_state(state: dict) -> None:
    with open(YEAR_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_log() -> list:
    if LOG_FILE.exists():
        with open(LOG_FILE) as f:
            return json.load(f)
    return []


def save_log(log: list) -> None:
    with open(LOG_FILE, "w") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)


def load_focus_log() -> list:
    if FOCUS_LOG_FILE.exists():
        with open(FOCUS_LOG_FILE) as f:
            return json.load(f)
    return []


def save_focus_log(log: list) -> None:
    with open(FOCUS_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def log_focus_day(focus_state: dict) -> None:
    """Save today's focus time to the daily log."""
    if focus_state.get("total_seconds", 0) == 0:
        return
    log = load_focus_log()
    d = focus_state["date"]
    # Update existing entry for today or append
    for entry in log:
        if entry["date"] == d:
            entry["seconds"] = focus_state["total_seconds"]
            save_focus_log(log)
            return
    log.append({"date": d, "seconds": focus_state["total_seconds"]})
    save_focus_log(log)


def load_focus_state() -> dict:
    if FOCUS_FILE.exists():
        with open(FOCUS_FILE) as f:
            state = json.load(f)
        if state.get("date") == str(date.today()):
            return state
    return {"date": str(date.today()), "total_seconds": 0}


def save_focus_state(state: dict) -> None:
    with open(FOCUS_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _extract_video_id(url: str) -> str | None:
    """Extract YouTube video ID from a URL."""
    import re
    m = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url)
    return m.group(1) if m else None


def is_youtube_playing() -> bool:
    """Check if a tracked YouTube video is actively playing in Chrome via JS."""
    goals = json.loads(DATA_FILE.read_text()) if DATA_FILE.exists() else {}
    video_urls = goals.get("focus_videos", [])
    video_ids = [_extract_video_id(u) for u in video_urls if u.strip()]
    video_ids = [v for v in video_ids if v]

    # Build URL filter conditions for AppleScript
    if video_ids:
        conditions = " or ".join(f'URL of t contains "{vid}"' for vid in video_ids)
    else:
        # No videos configured, track any YouTube video
        conditions = 'URL of t contains "youtube.com/watch"'

    script = f'''
    tell application "System Events"
        if exists (process "Google Chrome") then
            tell application "Google Chrome"
                repeat with w in windows
                    repeat with t in tabs of w
                        if {conditions} then
                            set jsResult to execute t javascript "document.querySelector('video') && !document.querySelector('video').paused ? 'playing' : 'paused'"
                            if jsResult is "playing" then
                                return true
                            end if
                        end if
                    end repeat
                end repeat
            end tell
        end if
    end tell
    return false
    '''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip() == "true":
            return True
    except Exception:
        pass
    return False


def format_duration(seconds: int) -> str:
    h, m = divmod(seconds // 60, 60)
    if h > 0:
        return f"{h}h {m:02d}m"
    return f"{m}m"


# ── Editor HTML ──────────────────────────────────────────────────────────────

EDITOR_HTML = """<!DOCTYPE html>
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
  .container { max-width: 1100px; margin: 0 auto; }
  .columns { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
  @media (max-width: 768px) { .columns { grid-template-columns: 1fr; } }
  h1 { text-align: center; font-size: 28px; margin-bottom: 20px; }
  h1 span {
    background: linear-gradient(135deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .page-tabs {
    display: flex; justify-content: center; gap: 4px; margin-bottom: 24px;
    background: #16213e; border-radius: 12px; padding: 4px; max-width: 400px; margin-left: auto; margin-right: auto;
  }
  .page-tab {
    flex: 1; padding: 10px 20px; border: none; border-radius: 10px;
    background: transparent; color: #888; font-size: 14px; font-weight: 500;
    cursor: pointer; transition: all 0.2s;
  }
  .page-tab:hover { color: #ccc; }
  .page-tab.active { background: #667eea; color: white; }
  .tab-content { display: none; }
  .tab-content.active { display: block; }
  .section {
    background: #16213e; border-radius: 16px; padding: 24px;
    margin-bottom: 24px; border: 1px solid #0f3460;
  }
  .section-header { font-size: 18px; font-weight: 600; margin-bottom: 16px; }
  .goal-item {
    display: flex; align-items: center; gap: 10px;
    padding: 10px 12px; background: #1a1a2e; border-radius: 10px;
    margin-bottom: 8px; transition: background 0.15s;
  }
  .goal-item:hover { background: #1f2945; }
  .goal-item.dragging { opacity: 0.4; }
  .goal-item.drag-over { border-top: 2px solid #667eea; }
  .drag-handle { cursor: grab; color: #555; font-size: 16px; user-select: none; }
  .drag-handle:active { cursor: grabbing; }
  .goal-item input[type="text"] {
    flex: 1; background: transparent; border: none; color: #eee;
    font-size: 15px; outline: none; padding: 4px 0;
    border-bottom: 1px solid transparent;
  }
  .goal-item input[type="text"]:focus { border-bottom-color: #667eea; }
  .btn-remove {
    background: none; border: none; color: #e74c3c; cursor: pointer;
    font-size: 18px; padding: 4px 8px; border-radius: 6px;
    opacity: 0; transition: opacity 0.15s, background 0.15s;
  }
  .goal-item:hover .btn-remove { opacity: 1; }
  .btn-remove:hover { background: rgba(231, 76, 60, 0.15); }
  .btn-today {
    background: none; border: none; color: #2ecc71; cursor: pointer;
    font-size: 13px; padding: 4px 8px; border-radius: 6px;
    transition: background 0.15s; white-space: nowrap;
  }
  .btn-today:hover { background: rgba(46, 204, 113, 0.15); }
  .btn-add {
    display: flex; align-items: center; gap: 6px; background: none;
    border: 1px dashed #0f3460; color: #667eea; cursor: pointer;
    font-size: 14px; padding: 10px 16px; border-radius: 10px;
    width: 100%; margin-top: 8px; transition: all 0.15s;
  }
  .btn-add:hover { background: rgba(102,126,234,0.1); border-color: #667eea; }
  .btn-save {
    width: 100%; padding: 14px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white; border: none; border-radius: 12px;
    font-size: 16px; font-weight: 600; cursor: pointer;
    transition: opacity 0.15s;
  }
  .btn-save:hover { opacity: 0.9; }
  .btn-save:active { transform: scale(0.98); }
  .toast {
    position: fixed; bottom: 30px; left: 50%;
    transform: translateX(-50%) translateY(100px);
    background: #2ecc71; color: white; padding: 12px 24px;
    border-radius: 10px; font-weight: 500;
    transition: transform 0.3s ease; z-index: 100;
  }
  .toast.show { transform: translateX(-50%) translateY(0); }
  .undo-toast {
    position: fixed; bottom: 30px; left: 50%;
    transform: translateX(-50%) translateY(100px);
    background: #e67e22; color: white; padding: 12px 24px;
    border-radius: 10px; font-weight: 500; cursor: pointer;
    transition: transform 0.3s ease, opacity 0.5s ease;
    z-index: 101; opacity: 0;
  }
  .undo-toast.show { transform: translateX(-50%) translateY(0); opacity: 1; }
  .undo-toast.fade-out { opacity: 0; }
  .hint { text-align: center; color: #555; font-size: 13px; margin-top: 16px; }
  .item-text {
    flex: 1; cursor: pointer; overflow: hidden;
    text-overflow: ellipsis; white-space: nowrap;
    font-size: 15px; padding: 4px 0; min-width: 0;
  }
  .item-text.has-attach { color: #b8c4ff; }
  .date-tag {
    color: #888; font-size: 12px; white-space: nowrap;
    background: rgba(102,126,234,0.1); padding: 2px 8px; border-radius: 6px;
    flex-shrink: 0;
  }
  .btn-delete {
    background: rgba(231,76,60,0.15); border: 1px solid #e74c3c; color: #e74c3c;
    cursor: pointer; font-size: 14px; padding: 10px 20px; border-radius: 10px;
    width: 100%; margin-top: 8px; transition: background 0.15s;
  }
  .btn-delete:hover { background: rgba(231,76,60,0.3); }
  .btn-upload {
    display: inline-flex; align-items: center; gap: 6px; cursor: pointer;
    background: rgba(102,126,234,0.15); border: 1px solid #667eea; color: #667eea;
    font-size: 13px; padding: 6px 14px; border-radius: 8px; transition: background 0.15s;
  }
  .btn-upload:hover { background: rgba(102,126,234,0.3); }
  .file-row {
    display: flex; align-items: center; gap: 8px; padding: 6px 10px;
    background: rgba(255,255,255,0.04); border-radius: 8px; font-size: 13px;
  }
  .file-row .file-name { flex: 1; color: #ccc; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .file-row a { color: #667eea; text-decoration: none; font-size: 16px; }
  .file-row a:hover { color: #8fa4ff; }
  .file-row .file-remove {
    background: none; border: none; color: #e74c3c; cursor: pointer;
    font-size: 14px; padding: 2px 4px; opacity: 0.7;
  }
  .file-row .file-remove:hover { opacity: 1; }
  #detail-files { display: flex; flex-direction: column; gap: 6px; }
  .detail-field {
    display: flex; align-items: center; gap: 12px; font-size: 14px;
  }
  .detail-field label { color: #888; white-space: nowrap; min-width: 50px; }
  .detail-field input[type="text"], .detail-field input[type="date"] {
    flex: 1; background: #1a1a2e; border: 1px solid #0f3460; color: #eee;
    border-radius: 8px; padding: 8px 12px; font-size: 14px; outline: none;
  }
  .detail-field input[type="text"]:focus, .detail-field input[type="date"]:focus {
    border-color: #667eea;
  }
  .detail-field input[type="date"] { width: 180px; flex: unset; }
  .detail-field input[type="date"]::-webkit-calendar-picker-indicator { filter: invert(0.5); }
  .modal-overlay {
    position: fixed; inset: 0; background: rgba(0,0,0,0.6);
    display: flex; align-items: center; justify-content: center;
    z-index: 200; opacity: 0; pointer-events: none;
    transition: opacity 0.2s ease;
  }
  .modal-overlay.open { opacity: 1; pointer-events: auto; }
  .modal {
    background: #16213e; border: 1px solid #0f3460; border-radius: 16px;
    padding: 24px; width: 700px; max-width: 90vw; max-height: 80vh;
    display: flex; flex-direction: column; gap: 12px;
  }
  .modal-header {
    display: flex; justify-content: space-between; align-items: center;
    font-size: 16px; font-weight: 600;
  }
  .modal-close {
    background: none; border: none; color: #e74c3c; font-size: 20px;
    cursor: pointer; padding: 4px 8px;
  }
  .modal-tabs { display: flex; gap: 8px; }
  .modal-tab {
    background: none; border: 1px solid #0f3460; color: #888;
    padding: 6px 16px; border-radius: 8px; cursor: pointer; font-size: 13px;
  }
  .modal-tab.active { background: #667eea; color: white; border-color: #667eea; }
  .modal textarea {
    flex: 1; background: #1a1a2e; border: 1px solid #0f3460; color: #eee;
    border-radius: 10px; padding: 12px; font-family: 'SF Mono', monospace;
    font-size: 14px; resize: none; outline: none; min-height: 300px;
  }
  .modal textarea:focus { border-color: #667eea; }
  .modal-preview {
    flex: 1; background: #1a1a2e; border: 1px solid #0f3460;
    border-radius: 10px; padding: 16px; overflow-y: auto;
    min-height: 300px; line-height: 1.6; font-size: 14px;
  }
  .modal-preview h1,.modal-preview h2,.modal-preview h3 { margin: 12px 0 6px; color: #667eea; }
  .modal-preview h1 { font-size: 20px; } .modal-preview h2 { font-size: 17px; } .modal-preview h3 { font-size: 15px; }
  .modal-preview p { margin: 6px 0; }
  .modal-preview code { background: #0f3460; padding: 2px 6px; border-radius: 4px; font-size: 13px; }
  .modal-preview pre { background: #0f3460; padding: 12px; border-radius: 8px; overflow-x: auto; margin: 8px 0; }
  .modal-preview pre code { background: none; padding: 0; }
  .modal-preview ul,.modal-preview ol { padding-left: 20px; margin: 6px 0; }
  .modal-preview blockquote { border-left: 3px solid #667eea; padding-left: 12px; color: #aaa; margin: 8px 0; }
  .modal-preview a { color: #667eea; }
  .year-card {
    background: #1a1a2e; border-radius: 12px; margin-bottom: 10px;
    border-left: 4px solid #667eea; overflow: hidden;
  }
  .year-card-header {
    display: flex; align-items: center; gap: 10px; padding: 10px 12px;
    cursor: pointer; user-select: none;
  }
  .year-card-header:hover { background: #1f2945; }
  .year-card .color-dot {
    width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
  }
  .year-card-header input[type="text"] {
    flex: 1; background: transparent; border: none; color: #eee;
    font-size: 15px; outline: none; padding: 4px 0;
    border-bottom: 1px solid transparent;
  }
  .year-card-header input[type="text"]:focus { border-bottom-color: #667eea; }
  .year-card-header .task-count {
    background: rgba(102,126,234,0.2); color: #8fa4ff; font-size: 11px;
    padding: 2px 8px; border-radius: 10px; white-space: nowrap;
  }
  .year-card-header .toggle-arrow {
    color: #888; font-size: 14px; padding: 2px 6px; flex-shrink: 0;
  }
  .year-card-body {
    padding: 0 12px 10px 26px; display: none;
  }
  .year-card-body.open { display: block; }
  .sub-goal-row {
    display: flex; align-items: center; gap: 8px; padding: 6px 0;
    border-bottom: 1px solid rgba(255,255,255,0.04);
  }
  .sub-goal-row:last-child { border-bottom: none; }
  .sub-goal-row input[type="text"] {
    flex: 1; background: transparent; border: none; color: #ccc;
    font-size: 14px; outline: none; padding: 4px 0;
    border-bottom: 1px solid transparent;
  }
  .sub-goal-row input[type="text"]:focus { border-bottom-color: #667eea; }
  .sub-goal-row .btn-remove { font-size: 14px; }
  .btn-add-sub {
    background: none; border: none; color: #667eea; cursor: pointer;
    font-size: 13px; padding: 6px 0; opacity: 0.7;
  }
  .btn-add-sub:hover { opacity: 1; }
  .cat-tag {
    display: inline-block; font-size: 11px; padding: 1px 8px;
    border-radius: 8px; color: white; white-space: nowrap;
    margin-left: 6px; flex-shrink: 0; line-height: 18px;
  }
  .detail-field select {
    flex: 1; background: #1a1a2e; border: 1px solid #0f3460; color: #eee;
    border-radius: 8px; padding: 8px 12px; font-size: 14px; outline: none;
  }
  .detail-field select:focus { border-color: #667eea; }
  .detail-field select option { background: #1a1a2e; color: #eee; }
  .detail-field select optgroup { color: #888; font-style: normal; }
  .alarm-item {
    display: flex; align-items: center; gap: 12px;
    padding: 12px 14px; background: #1a1a2e; border-radius: 12px;
    margin-bottom: 8px; transition: background 0.15s; border: 1px solid transparent;
  }
  .alarm-item:hover { background: #1f2945; border-color: #0f3460; }
  .alarm-time-badge {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white; font-weight: 700; font-size: 15px;
    padding: 6px 12px; border-radius: 8px; font-variant-numeric: tabular-nums;
    min-width: 60px; text-align: center; letter-spacing: 0.5px;
  }
  .alarm-name { flex: 1; color: #eee; font-size: 15px; }
  .alarm-add-row {
    display: flex; gap: 8px; margin-top: 12px; align-items: center;
    padding: 8px; background: #1a1a2e; border-radius: 12px; border: 1px dashed #0f3460;
  }
  .alarm-time-wrap { flex-shrink: 0; }
  .alarm-time-input {
    background: #16213e; border: 1px solid #0f3460; color: #eee;
    border-radius: 8px; padding: 10px 12px; font-size: 14px; outline: none;
    color-scheme: dark;
  }
  .alarm-time-input:focus { border-color: #667eea; }
  .alarm-text-input {
    flex: 1; background: #16213e; border: 1px solid #0f3460; color: #eee;
    border-radius: 8px; padding: 10px 12px; font-size: 14px; outline: none;
  }
  .alarm-text-input:focus { border-color: #667eea; }
  .alarm-add-btn {
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white; border: none; border-radius: 8px; padding: 10px 16px;
    font-size: 14px; font-weight: 600; cursor: pointer;
    transition: opacity 0.15s; white-space: nowrap;
  }
  .alarm-add-btn:hover { opacity: 0.85; }
</style>
</head>
<body>
<div class="container">
  <h1>🎯 <span>Goals Editor</span></h1>
  <div class="page-tabs">
    <button class="page-tab active" onclick="switchPage('editor')">📋 Editor</button>
    <button class="page-tab" onclick="switchPage('year')">🏆 Year Goals</button>
  </div>
  <div class="tab-content active" id="page-editor">
    <div class="columns">
      <div class="col">
        <div class="section">
          <div class="section-header">📅 Daily Goals</div>
          <div id="daily-list"></div>
          <button class="btn-add" onclick="addGoal('daily')">➕ Add Daily Goal</button>
        </div>
        <div class="section">
          <div class="section-header">💡 Bulbs</div>
          <div id="bulbs-list"></div>
          <button class="btn-add" onclick="addBulb()">➕ Add Bulb</button>
        </div>
        <div class="section">
          <div class="section-header">⏰ Alarms</div>
          <div id="alarms-list"></div>
          <div class="alarm-add-row">
            <input type="date" id="alarm-date" class="alarm-time-input">
            <input type="time" id="alarm-time" class="alarm-time-input">
            <input type="text" id="alarm-text" class="alarm-text-input" placeholder="Alarm name..." onkeydown="if(event.key==='Enter'){event.preventDefault();addAlarm();}">
            <button class="alarm-add-btn" onclick="addAlarm()">+ Add</button>
          </div>
        </div>
        <div class="section">
          <div class="section-header">🎧 Focus Videos</div>
          <p style="color:#888;font-size:13px;margin-bottom:12px;">YouTube video URLs to track focus time. Leave empty to track all.</p>
          <div id="video-list"></div>
          <button class="btn-add" onclick="addVideo()">➕ Add Video</button>
        </div>
      </div>
      <div class="col">
        <div class="section">
          <div class="section-header">📦 Backlog</div>
          <div id="backlog-list"></div>
          <button class="btn-add" onclick="addBacklog()">➕ Add Backlog Item</button>
        </div>
      </div>
    </div>
    <button class="btn-save" onclick="save()">💾 Save Changes</button>
    <p class="hint">Menu bar updates automatically after saving.</p>
  </div>
  <div class="tab-content" id="page-year">
    <div class="section">
      <div id="year-progress"></div>
      <button class="btn-add" onclick="addYearGoal()">➕ Add Year Goal</button>
    </div>
    <button class="btn-save" onclick="save()">💾 Save Changes</button>
  </div>
</div>
<div class="toast" id="toast">Saved! Menu bar updated.</div>
<div class="undo-toast" id="undo-toast" onclick="doUndo()">↩ Undo</div>
<div class="modal-overlay" id="detail-modal" onclick="if(event.target===this)closeDetail()">
  <div class="modal">
    <div class="modal-header">
      <span>📝 Edit Item</span>
      <button class="modal-close" onclick="closeDetail()">✕</button>
    </div>
    <div class="detail-field">
      <label>Title</label>
      <input type="text" id="detail-title" placeholder="Item text...">
    </div>
    <div class="detail-field" id="detail-date-row" style="display:none">
      <label>Date</label>
      <input type="date" id="detail-date">
    </div>
    <div class="detail-field" id="detail-cat-row" style="display:none">
      <label>Category</label>
      <select id="detail-category"><option value="">— None —</option></select>
    </div>
    <div class="modal-tabs">
      <button class="modal-tab active" id="tab-edit" onclick="switchTab('edit')">Edit</button>
      <button class="modal-tab" id="tab-preview" onclick="switchTab('preview')">Preview</button>
    </div>
    <textarea id="attach-editor" placeholder="Write markdown notes..."></textarea>
    <div class="modal-preview" id="attach-preview" style="display:none"></div>
    <div id="detail-files"></div>
    <label class="btn-upload">📎 Attach PDF<input type="file" accept=".pdf" id="detail-file-input" hidden></label>
    <button class="btn-save" onclick="closeDetail()">💾 Save</button>
  </div>
</div>
<script>
let goals = {};
let undoStack = null;
let undoTimer = null;
const CAT_COLORS = ['#667eea','#f39c12','#2ecc71','#e74c3c','#9b59b6','#1abc9c'];
function genId() { return Math.random().toString(16).slice(2,6); }
function getCategoryInfo(catId) {
  if (!catId) return null;
  const yg = goals.year_goals || [];
  for (let gi = 0; gi < yg.length; gi++) {
    const subs = yg[gi].sub_goals || [];
    for (const s of subs) {
      if (s.id === catId) return { text: s.text, color: CAT_COLORS[gi % CAT_COLORS.length] };
    }
  }
  return null;
}
function deleteItem(key, idx) {
  const arr = goals[key];
  if (!arr || idx < 0 || idx >= arr.length) return;
  const removed = arr.splice(idx, 1)[0];
  undoStack = { key, idx, item: removed };
  render();
  showUndo();
}
function showUndo() {
  const el = document.getElementById('undo-toast');
  const label = typeof undoStack.item === 'string' ? undoStack.item : undoStack.item.text || '';
  el.textContent = '↩ Undo "' + (label.length > 25 ? label.slice(0, 25) + '…' : label) + '"';
  el.classList.remove('fade-out');
  el.classList.add('show');
  clearTimeout(undoTimer);
  undoTimer = setTimeout(() => {
    el.classList.add('fade-out');
    setTimeout(() => { el.classList.remove('show', 'fade-out'); }, 500);
  }, 15000);
}
function doUndo() {
  if (!undoStack) return;
  const { key, idx, item } = undoStack;
  if (!goals[key]) goals[key] = [];
  goals[key].splice(idx, 0, item);
  undoStack = null;
  clearTimeout(undoTimer);
  const el = document.getElementById('undo-toast');
  el.classList.remove('show', 'fade-out');
  render();
}
let detailCtx = null;
function getDetailItem() {
  if (!detailCtx) return null;
  if (detailCtx.key === 'year_sub') {
    const yg = (goals.year_goals || [])[detailCtx.goalIdx];
    return yg ? (yg.sub_goals || [])[detailCtx.subIdx] : null;
  }
  return goals[detailCtx.key][detailCtx.idx];
}
function openDetail(key, idx, extra) {
  if (key === 'year_sub') {
    detailCtx = { key: 'year_sub', goalIdx: idx, subIdx: extra };
  } else {
    detailCtx = { key, idx };
  }
  const item = getDetailItem();
  if (!item) return;
  document.getElementById('detail-title').value = item.text || '';
  document.getElementById('attach-editor').value = item.attachment || '';
  const dateRow = document.getElementById('detail-date-row');
  if (key === 'backlog') {
    dateRow.style.display = '';
    document.getElementById('detail-date').value = item.scheduled_date || '';
  } else {
    dateRow.style.display = 'none';
  }
  const catRow = document.getElementById('detail-cat-row');
  if (key === 'daily_goals' || key === 'backlog' || key === 'bulbs') {
    catRow.style.display = '';
    buildCategorySelect();
    document.getElementById('detail-category').value = item.category || '';
  } else {
    catRow.style.display = 'none';
  }
  renderFileList(item.files || []);
  switchTab('edit');
  document.getElementById('detail-modal').classList.add('open');
}
function renderFileList(files) {
  const container = document.getElementById('detail-files');
  container.innerHTML = '';
  files.forEach((f, i) => {
    const row = document.createElement('div');
    row.className = 'file-row';
    row.innerHTML = '<span class="file-name">' + f.name.replace(/</g,'&lt;') + '</span>'
      + '<a href="/api/file/' + encodeURIComponent(f.path) + '" target="_blank" title="Open PDF">📄</a>'
      + '<button class="file-remove" title="Remove file">✕</button>';
    row.querySelector('.file-remove').addEventListener('click', () => removeFile(i));
    container.appendChild(row);
  });
}
async function removeFile(i) {
  const item = getDetailItem();
  if (!item) return;
  const file = item.files[i];
  await fetch('/api/delete-file', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({filename:file.path})});
  item.files.splice(i, 1);
  if (!item.files.length) delete item.files;
  renderFileList(item.files || []);
}
document.getElementById('detail-file-input').addEventListener('change', async function() {
  if (!this.files.length || !detailCtx) return;
  const fd = new FormData();
  fd.append('file', this.files[0]);
  const res = await fetch('/api/upload', {method:'POST', body:fd});
  const info = await res.json();
  const item = getDetailItem();
  if (!item) return;
  if (!item.files) item.files = [];
  item.files.push({name:info.name, path:info.path});
  renderFileList(item.files);
  this.value = '';
});
function closeDetail() {
  if (detailCtx) {
    const item = getDetailItem();
    const { key } = detailCtx;
    if (item) {
      const text = document.getElementById('detail-title').value.trim();
      if (!text) {
        if (key === 'year_sub') {
          goals.year_goals[detailCtx.goalIdx].sub_goals.splice(detailCtx.subIdx, 1);
        } else {
          goals[key].splice(detailCtx.idx, 1);
        }
      } else {
        item.text = text;
        const val = document.getElementById('attach-editor').value;
        item.attachment = val || undefined;
        if (key === 'backlog') {
          item.scheduled_date = document.getElementById('detail-date').value || null;
        }
        if (key === 'daily_goals' || key === 'backlog' || key === 'bulbs') {
          const cat = document.getElementById('detail-category').value;
          if (cat) item.category = cat; else delete item.category;
        }
      }
    }
    render();
    save();
  }
  detailCtx = null;
  document.getElementById('detail-modal').classList.remove('open');
}
function switchTab(tab) {
  const editor = document.getElementById('attach-editor');
  const preview = document.getElementById('attach-preview');
  document.getElementById('tab-edit').classList.toggle('active', tab === 'edit');
  document.getElementById('tab-preview').classList.toggle('active', tab === 'preview');
  if (tab === 'edit') { editor.style.display = ''; preview.style.display = 'none'; }
  else { editor.style.display = 'none'; preview.style.display = ''; preview.innerHTML = renderMd(editor.value); }
}
function renderMd(md) {
  let h = md.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  h = h.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  h = h.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  h = h.replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>');
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  h = h.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/\*(.+?)\*/g, '<em>$1</em>');
  h = h.replace(/^\> (.+)$/gm, '<blockquote>$1</blockquote>');
  h = h.replace(/^\- (.+)$/gm, '<li>$1</li>');
  h = h.replace(/(<li>.*<\/li>)/gs, '<ul>$1</ul>');
  h = h.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>');
  h = h.split(String.fromCharCode(10)+String.fromCharCode(10)).join('</p><p>');
  h = '<p>' + h + '</p>';
  h = h.replace(/<p>\s*(<h[123]>)/g, '$1').replace(/(<\/h[123]>)\s*<\/p>/g, '$1');
  h = h.replace(/<p>\s*(<pre>)/g, '$1').replace(/(<\/pre>)\s*<\/p>/g, '$1');
  h = h.replace(/<p>\s*(<ul>)/g, '$1').replace(/(<\/ul>)\s*<\/p>/g, '$1');
  h = h.replace(/<p>\s*(<blockquote>)/g, '$1').replace(/(<\/blockquote>)\s*<\/p>/g, '$1');
  return h;
}
async function load() {
  const res = await fetch('/api/goals');
  goals = await res.json();
  render();
}
function render() {
  renderList('daily-list', goals.daily_goals || [], 'daily');
  renderYearProgress();
  renderBacklog();
  renderBulbs();
  renderAlarms();
  renderVideos();
}
function renderVideos() {
  const el = document.getElementById('video-list');
  const videos = goals.focus_videos || [];
  el.innerHTML = '';
  videos.forEach((v, i) => {
    const div = document.createElement('div');
    div.className = 'goal-item';
    const input = document.createElement('input');
    input.type = 'text';
    input.value = v;
    input.placeholder = 'YouTube video URL';
    input.addEventListener('input', () => { goals.focus_videos[i] = input.value; });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); input.blur(); save(); } });
    const btn = document.createElement('button');
    btn.className = 'btn-remove';
    btn.textContent = '✕';
    btn.addEventListener('click', () => deleteItem('focus_videos', i));
    div.appendChild(input);
    div.appendChild(btn);
    el.appendChild(div);
  });
}
function renderBacklog() {
  const el = document.getElementById('backlog-list');
  const items = goals.backlog || [];
  el.innerHTML = '';
  items.forEach((item, i) => {
    const div = document.createElement('div');
    div.className = 'goal-item';
    const span = document.createElement('span');
    span.className = 'item-text' + (item.attachment ? ' has-attach' : '');
    span.textContent = item.text || '(empty)';
    span.addEventListener('click', () => openDetail('backlog', i));
    div.appendChild(span);
    if (item.category) {
      const ci = getCategoryInfo(item.category);
      if (ci) { const tag = document.createElement('span'); tag.className = 'cat-tag'; tag.textContent = ci.text; tag.style.background = ci.color; div.appendChild(tag); }
    }
    if (item.scheduled_date) {
      const dateTag = document.createElement('span');
      dateTag.className = 'date-tag';
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      const tStr = tomorrow.getFullYear() + '-' + String(tomorrow.getMonth()+1).padStart(2,'0') + '-' + String(tomorrow.getDate()).padStart(2,'0');
      const isTomorrow = item.scheduled_date === tStr;
      dateTag.textContent = (isTomorrow ? '⏰ ' : '') + item.scheduled_date;
      div.appendChild(dateTag);
    }
    const btnToday = document.createElement('button');
    btnToday.className = 'btn-today';
    btnToday.textContent = '📅 Today';
    btnToday.addEventListener('click', () => addToToday(i));
    const btnRemove = document.createElement('button');
    btnRemove.className = 'btn-remove';
    btnRemove.textContent = '✕';
    btnRemove.addEventListener('click', () => deleteItem('backlog', i));
    div.appendChild(btnToday);
    div.appendChild(btnRemove);
    el.appendChild(div);
  });
}
function addBacklog() {
  if (!goals.backlog) goals.backlog = [];
  const today = new Date().toISOString().slice(0, 10);
  goals.backlog.push({ text: '', added_date: today });
  render();
  openDetail('backlog', goals.backlog.length - 1);
}
async function addToToday(idx) {
  const res = await fetch('/api/add-to-today', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ index: idx })
  });
  if (res.ok) {
    const fresh = await fetch('/api/goals');
    goals = await fresh.json();
    render();
  }
}
function renderAlarms() {
  const el = document.getElementById('alarms-list');
  const alarms = goals.alarms || [];
  el.innerHTML = '';
  if (alarms.length === 0) {
    el.innerHTML = '<p style="color:#555;font-size:13px;text-align:center;padding:12px 0;">No alarms set. Add one below.</p>';
    return;
  }
  alarms.forEach((a, i) => {
    const div = document.createElement('div');
    div.className = 'alarm-item';
    const timeBadge = document.createElement('span');
    timeBadge.className = 'alarm-time-badge';
    const dateLabel = a.date ? a.date + '  ' : '';
    timeBadge.textContent = dateLabel + a.time;
    const nameSpan = document.createElement('span');
    nameSpan.className = 'alarm-name';
    nameSpan.textContent = a.text;
    const btn = document.createElement('button');
    btn.className = 'btn-remove';
    btn.textContent = '✕';
    btn.addEventListener('click', () => { goals.alarms.splice(i, 1); save(); });
    div.appendChild(timeBadge);
    div.appendChild(nameSpan);
    div.appendChild(btn);
    el.appendChild(div);
  });
}
function addAlarm() {
  const alarmDate = document.getElementById('alarm-date').value;
  const time = document.getElementById('alarm-time').value;
  const text = document.getElementById('alarm-text').value.trim();
  if (!alarmDate || !time || !text) return;
  if (!goals.alarms) goals.alarms = [];
  goals.alarms.push({ text: text, time: time, date: alarmDate });
  goals.alarms.sort((a, b) => ((a.date||'')+(a.time)).localeCompare((b.date||'')+(b.time)));
  document.getElementById('alarm-date').value = new Date().toISOString().slice(0,10);
  document.getElementById('alarm-time').value = nowHHMM();
  document.getElementById('alarm-text').value = '';
  save();
}
function renderBulbs() {
  const el = document.getElementById('bulbs-list');
  const items = goals.bulbs || [];
  el.innerHTML = '';
  items.forEach((item, i) => {
    const div = document.createElement('div');
    div.className = 'goal-item';
    const span = document.createElement('span');
    span.className = 'item-text' + (item.attachment ? ' has-attach' : '');
    span.textContent = item.text || '(empty)';
    span.addEventListener('click', () => openDetail('bulbs', i));
    if (item.category) {
      const ci = getCategoryInfo(item.category);
      if (ci) { const tag = document.createElement('span'); tag.className = 'cat-tag'; tag.textContent = ci.text; tag.style.background = ci.color; div.appendChild(tag); }
    }
    const btnDaily = document.createElement('button');
    btnDaily.className = 'btn-today';
    btnDaily.textContent = '📅';
    btnDaily.title = 'Add to Daily Goals';
    btnDaily.addEventListener('click', () => bulbTo('daily', i));
    const btnBacklog = document.createElement('button');
    btnBacklog.className = 'btn-today';
    btnBacklog.style.color = '#f39c12';
    btnBacklog.textContent = '📦';
    btnBacklog.title = 'Add to Backlog';
    btnBacklog.addEventListener('click', () => bulbTo('backlog', i));
    const btnRemove = document.createElement('button');
    btnRemove.className = 'btn-remove';
    btnRemove.textContent = '✕';
    btnRemove.addEventListener('click', () => deleteItem('bulbs', i));
    div.appendChild(span);
    div.appendChild(btnDaily);
    div.appendChild(btnBacklog);
    div.appendChild(btnRemove);
    el.appendChild(div);
  });
}
async function bulbTo(target, idx) {
  const res = await fetch('/api/bulb-to', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ index: idx, target: target })
  });
  if (res.ok) {
    const fresh = await fetch('/api/goals');
    goals = await fresh.json();
    render();
  }
}
function addBulb() {
  if (!goals.bulbs) goals.bulbs = [];
  const today = new Date().toISOString().slice(0, 10);
  goals.bulbs.unshift({ text: '', created: today });
  render();
  openDetail('bulbs', 0);
}
async function moveToBacklog(idx) {
  const res = await fetch('/api/move-to-backlog', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ index: idx })
  });
  if (res.ok) {
    const fresh = await fetch('/api/goals');
    goals = await fresh.json();
    render();
  }
}
function addVideo() {
  if (!goals.focus_videos) goals.focus_videos = [];
  goals.focus_videos.push('');
  render();
  const inputs = document.getElementById('video-list').querySelectorAll('input');
  if (inputs.length > 0) inputs[inputs.length - 1].focus();
}
function renderYearProgress() {
  const el = document.getElementById('year-progress');
  const yg = goals.year_goals || [];
  el.innerHTML = '';
  yg.forEach((goal, gi) => {
    const color = CAT_COLORS[gi % CAT_COLORS.length];
    const card = document.createElement('div');
    card.className = 'year-card';
    card.draggable = true;
    card.dataset.yidx = gi;
    card.style.borderLeftColor = color;
    card.addEventListener('dragstart', e => { e.dataTransfer.setData('text/plain', gi); card.classList.add('dragging'); });
    card.addEventListener('dragend', () => card.classList.remove('dragging'));
    card.addEventListener('dragover', e => { e.preventDefault(); card.style.borderTop = '2px solid #667eea'; });
    card.addEventListener('dragleave', () => { card.style.borderTop = ''; });
    card.addEventListener('drop', e => {
      e.preventDefault(); card.style.borderTop = '';
      const from = parseInt(e.dataTransfer.getData('text/plain'));
      const to = parseInt(card.dataset.yidx);
      if (from !== to && !isNaN(from)) {
        const [moved] = goals.year_goals.splice(from, 1);
        goals.year_goals.splice(to, 0, moved);
        renderYearProgress();
      }
    });
    // count tasks tagged with any of this goal's sub-goals
    const subIds = new Set((goal.sub_goals || []).map(s => s.id));
    let tagCount = 0;
    ['daily_goals','backlog','bulbs'].forEach(k => {
      (goals[k] || []).forEach(it => { if (it.category && subIds.has(it.category)) tagCount++; });
    });
    // header
    const header = document.createElement('div');
    header.className = 'year-card-header';
    const dot = document.createElement('span');
    dot.className = 'color-dot';
    dot.style.background = color;
    const titleInput = document.createElement('input');
    titleInput.type = 'text';
    titleInput.value = goal.text || '';
    titleInput.placeholder = 'Year goal...';
    titleInput.addEventListener('input', () => { goals.year_goals[gi].text = titleInput.value; });
    titleInput.addEventListener('click', e => e.stopPropagation());
    const badge = document.createElement('span');
    badge.className = 'task-count';
    const subCount = (goal.sub_goals || []).length;
    badge.textContent = subCount + ' sub-goal' + (subCount !== 1 ? 's' : '') + (tagCount > 0 ? ' · ' + tagCount + ' task' + (tagCount !== 1 ? 's' : '') : '');
    const arrow = document.createElement('span');
    arrow.className = 'toggle-arrow';
    arrow.textContent = '▸';
    const btnRm = document.createElement('button');
    btnRm.className = 'btn-remove';
    btnRm.textContent = '✕';
    btnRm.addEventListener('click', e => { e.stopPropagation(); deleteItem('year_goals', gi); });
    const handle = document.createElement('span');
    handle.className = 'drag-handle';
    handle.textContent = '⠿';
    header.appendChild(handle);
    header.appendChild(dot);
    header.appendChild(titleInput);
    header.appendChild(badge);
    header.appendChild(arrow);
    header.appendChild(btnRm);
    // body
    const body = document.createElement('div');
    body.className = 'year-card-body';
    (goal.sub_goals || []).forEach((sg, si) => {
      const row = document.createElement('div');
      row.className = 'sub-goal-row';
      const sgSpan = document.createElement('span');
      sgSpan.className = 'item-text' + (sg.attachment ? ' has-attach' : '');
      sgSpan.textContent = sg.text || '(empty)';
      sgSpan.addEventListener('click', () => openDetail('year_sub', gi, si));
      const sgRm = document.createElement('button');
      sgRm.className = 'btn-remove';
      sgRm.textContent = '✕';
      sgRm.addEventListener('click', () => {
        goals.year_goals[gi].sub_goals.splice(si, 1);
        renderYearProgress();
      });
      row.appendChild(sgSpan);
      row.appendChild(sgRm);
      body.appendChild(row);
    });
    const addSub = document.createElement('button');
    addSub.className = 'btn-add-sub';
    addSub.textContent = '+ Add sub-goal';
    addSub.addEventListener('click', () => addSubGoal(gi));
    body.appendChild(addSub);
    header.addEventListener('click', () => {
      body.classList.toggle('open');
      arrow.textContent = body.classList.contains('open') ? '▾' : '▸';
    });
    card.appendChild(header);
    card.appendChild(body);
    el.appendChild(card);
  });
}
function addYearGoal() {
  if (!goals.year_goals) goals.year_goals = [];
  goals.year_goals.push({ text: '', sub_goals: [] });
  renderYearProgress();
  // auto-expand the new card and focus its title
  const cards = document.querySelectorAll('#year-progress .year-card');
  const last = cards[cards.length - 1];
  if (last) {
    last.querySelector('.year-card-body').classList.add('open');
    last.querySelector('.toggle-arrow').textContent = '▾';
    last.querySelector('input').focus();
  }
}
function addSubGoal(gi) {
  const goal = goals.year_goals[gi];
  if (!goal.sub_goals) goal.sub_goals = [];
  goal.sub_goals.push({ id: genId(), text: '' });
  renderYearProgress();
  // re-expand that card and focus the new sub-goal input
  const cards = document.querySelectorAll('#year-progress .year-card');
  const card = cards[gi];
  if (card) {
    card.querySelector('.year-card-body').classList.add('open');
    card.querySelector('.toggle-arrow').textContent = '▾';
    const inputs = card.querySelectorAll('.sub-goal-row input');
    if (inputs.length) inputs[inputs.length - 1].focus();
  }
}
function buildCategorySelect() {
  const sel = document.getElementById('detail-category');
  sel.innerHTML = '<option value="">— None —</option>';
  (goals.year_goals || []).forEach((yg, gi) => {
    const subs = yg.sub_goals || [];
    if (!subs.length) return;
    const grp = document.createElement('optgroup');
    grp.label = yg.text || '(untitled)';
    subs.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = s.text || '(untitled)';
      grp.appendChild(opt);
    });
    sel.appendChild(grp);
  });
}
function renderList(containerId, items, type) {
  const el = document.getElementById(containerId);
  const key = type === 'daily' ? 'daily_goals' : 'year_goals';
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
    const span = document.createElement('span');
    span.className = 'item-text' + (item.attachment ? ' has-attach' : '');
    span.textContent = item.text || '(empty)';
    span.addEventListener('click', () => openDetail(key, i));
    div.appendChild(handle);
    div.appendChild(span);
    if (item.category) {
      const ci = getCategoryInfo(item.category);
      if (ci) { const tag = document.createElement('span'); tag.className = 'cat-tag'; tag.textContent = ci.text; tag.style.background = ci.color; div.appendChild(tag); }
    }
    if (type === 'daily') {
      const btnBacklog = document.createElement('button');
      btnBacklog.className = 'btn-today';
      btnBacklog.style.color = '#f39c12';
      btnBacklog.textContent = '📦';
      btnBacklog.addEventListener('click', () => moveToBacklog(i));
      div.appendChild(btnBacklog);
    }
    const btn = document.createElement('button');
    btn.className = 'btn-remove';
    btn.textContent = '✕';
    btn.addEventListener('click', () => deleteItem(key, i));
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
  if (!goals.daily_goals) goals.daily_goals = [];
  const today = new Date().toISOString().slice(0, 10);
  goals.daily_goals.push({ text: '', added_date: today });
  render();
  openDetail('daily_goals', goals.daily_goals.length - 1);
}
let dragItem = null;
function onDragStart(e) {
  dragItem = { type: e.currentTarget.dataset.type, index: parseInt(e.currentTarget.dataset.index) };
  e.currentTarget.classList.add('dragging');
}
function onDragOver(e) {
  e.preventDefault();
  if (e.currentTarget.dataset.type === dragItem?.type) e.currentTarget.classList.add('drag-over');
}
function onDragLeave(e) { e.currentTarget.classList.remove('drag-over'); }
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
function onDragEnd(e) { e.currentTarget.classList.remove('dragging'); dragItem = null; }
async function save() {
  goals.daily_goals = (goals.daily_goals || []).filter(g => g.text.trim());
  goals.year_goals = (goals.year_goals || []).filter(g => g.text.trim());
  goals.year_goals.forEach(g => {
    if (g.sub_goals) g.sub_goals = g.sub_goals.filter(s => s.text.trim());
  });
  goals.backlog = (goals.backlog || []).filter(g => g.text.trim());
  goals.bulbs = (goals.bulbs || []).filter(g => g.text.trim());
  goals.focus_videos = (goals.focus_videos || []).filter(v => v.trim());
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
function switchPage(page) {
  document.querySelectorAll('.page-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  if (page === 'year') {
    document.querySelectorAll('.page-tab')[1].classList.add('active');
    document.getElementById('page-year').classList.add('active');
  } else {
    document.querySelectorAll('.page-tab')[0].classList.add('active');
    document.getElementById('page-editor').classList.add('active');
  }
  localStorage.setItem('goals-active-tab', page);
}
function nowHHMM() { const n = new Date(); return String(n.getHours()).padStart(2,'0') + ':' + String(n.getMinutes()).padStart(2,'0'); }
load();
// Default alarm inputs to today + now
document.getElementById('alarm-date').value = new Date().toISOString().slice(0,10);
document.getElementById('alarm-time').value = nowHHMM();
const savedTab = localStorage.getItem('goals-active-tab');
if (savedTab) switchPage(savedTab);
// Auto-reload when page gains focus (picks up iCloud sync from iOS)
document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
</script>
</body>
</html>"""

ADD_ALARM_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>New Alarm</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #1a1a2e;
    color: #eee;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .card {
    background: #16213e;
    border-radius: 20px;
    padding: 36px 32px;
    width: 380px;
    border: 1px solid #0f3460;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
  }
  .title {
    text-align: center;
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 28px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  .field { margin-bottom: 20px; }
  .field label {
    display: block;
    font-size: 13px;
    color: #888;
    margin-bottom: 6px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .field input[type="text"],
  .field input[type="date"],
  .field input[type="time"] {
    width: 100%;
    background: #1a1a2e;
    border: 1px solid #0f3460;
    color: #eee;
    border-radius: 10px;
    padding: 12px 14px;
    font-size: 16px;
    outline: none;
    transition: border-color 0.2s;
    color-scheme: dark;
  }
  .field input:focus { border-color: #667eea; }
  .row { display: flex; gap: 12px; }
  .row .field { flex: 1; }
  .btn-save {
    width: 100%;
    padding: 14px;
    background: linear-gradient(135deg, #667eea, #764ba2);
    color: white;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.15s, transform 0.1s;
    margin-top: 8px;
  }
  .btn-save:hover { opacity: 0.9; }
  .btn-save:active { transform: scale(0.98); }
  .btn-save:disabled { opacity: 0.4; cursor: not-allowed; }
  .toast {
    position: fixed; top: 20px; left: 50%;
    transform: translateX(-50%) translateY(-80px);
    background: #2ecc71; color: white; padding: 12px 24px;
    border-radius: 10px; font-weight: 500;
    transition: transform 0.3s ease; z-index: 100;
  }
  .toast.show { transform: translateX(-50%) translateY(0); }
  .quick-btns {
    display: flex; gap: 6px; flex-wrap: wrap; margin-top: 8px;
  }
  .quick-btn {
    background: #1a1a2e; border: 1px solid #0f3460; color: #aaa;
    border-radius: 8px; padding: 6px 12px; font-size: 12px;
    cursor: pointer; transition: all 0.15s;
  }
  .quick-btn:hover { border-color: #667eea; color: #eee; }
</style>
</head>
<body>
<div class="card">
  <div class="title">&#9200; New Alarm</div>
  <div class="field">
    <label>What's this alarm for?</label>
    <input type="text" id="alarm-name" placeholder="e.g. Stand up meeting" autofocus>
  </div>
  <div class="row">
    <div class="field">
      <label>Date</label>
      <input type="date" id="alarm-date">
      <div class="quick-btns">
        <button class="quick-btn" onclick="setDate(0)">Today</button>
        <button class="quick-btn" onclick="setDate(1)">Tomorrow</button>
        <button class="quick-btn" onclick="setDate(7)">+1 Week</button>
      </div>
    </div>
    <div class="field">
      <label>Time</label>
      <input type="time" id="alarm-time">
      <div class="quick-btns">
        <button class="quick-btn" onclick="setTime('09:00')">9am</button>
        <button class="quick-btn" onclick="setTime('12:00')">12pm</button>
        <button class="quick-btn" onclick="setTime('14:00')">2pm</button>
        <button class="quick-btn" onclick="setTime('18:00')">6pm</button>
      </div>
    </div>
  </div>
  <button class="btn-save" id="save-btn" onclick="saveAlarm()">Save Alarm</button>
</div>
<div class="toast" id="toast">Alarm saved!</div>
<script>
// Default date to today
const today = new Date();
const todayStr = today.getFullYear() + '-' + String(today.getMonth()+1).padStart(2,'0') + '-' + String(today.getDate()).padStart(2,'0');
function nowHHMM() { const n = new Date(); return String(n.getHours()).padStart(2,'0') + ':' + String(n.getMinutes()).padStart(2,'0'); }
document.getElementById('alarm-date').value = todayStr;
document.getElementById('alarm-time').value = nowHHMM();

function setDate(offset) {
  const d = new Date();
  d.setDate(d.getDate() + offset);
  document.getElementById('alarm-date').value = d.getFullYear() + '-' + String(d.getMonth()+1).padStart(2,'0') + '-' + String(d.getDate()).padStart(2,'0');
}
function setTime(t) {
  document.getElementById('alarm-time').value = t;
}

document.getElementById('alarm-name').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') { e.preventDefault(); saveAlarm(); }
});

async function saveAlarm() {
  const name = document.getElementById('alarm-name').value.trim();
  const alarmDate = document.getElementById('alarm-date').value;
  const time = document.getElementById('alarm-time').value;
  if (!name || !alarmDate || !time) return;

  const res = await fetch('/api/goals');
  const goals = await res.json();
  if (!goals.alarms) goals.alarms = [];
  goals.alarms.push({ text: name, time: time, date: alarmDate });
  goals.alarms.sort((a, b) => ((a.date||'')+(a.time)).localeCompare((b.date||'')+(b.time)));

  await fetch('/api/goals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(goals)
  });

  const toast = document.getElementById('toast');
  toast.classList.add('show');
  document.getElementById('alarm-name').value = '';
  document.getElementById('alarm-date').value = todayStr;
  document.getElementById('alarm-time').value = nowHHMM();
  document.getElementById('alarm-name').focus();
  setTimeout(() => toast.classList.remove('show'), 2000);
}
</script>
</body>
</html>"""


# ── App ──────────────────────────────────────────────────────────────────────

class GoalsStickerApp(rumps.App):
    def __init__(self):
        super().__init__("🎯", quit_button=None)
        self._subprocesses = []
        self._needs_rebuild = False
        self._focus_active = False
        self._rolling_text = None
        self._rolling_pos = 0
        self._focus_state = load_focus_state()
        self.daily_state = load_daily_state()
        self.year_state = load_year_state()
        self.goals_data = load_goals()
        self._goals_mtime = DATA_FILE.stat().st_mtime if DATA_FILE.exists() else 0
        if self.daily_state.get("date") != str(date.today()):
            self._roll_over_daily()
        else:
            self._promote_scheduled_backlog()
        ATTACHMENTS_DIR.mkdir(exist_ok=True)
        self._start_editor_server()
        self._build_menu()

    # ── Editor server (runs in background thread) ──

    def _start_editor_server(self):
        app_ref = self

        class EditorHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/api/goals":
                    # Re-read from disk to pick up changes from iOS app
                    app_ref.goals_data = load_goals()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps(app_ref.goals_data).encode())
                elif self.path.startswith("/api/file/"):
                    from urllib.parse import unquote
                    filename = os.path.basename(unquote(self.path[len("/api/file/"):]))
                    filepath = ATTACHMENTS_DIR / filename
                    if filepath.exists() and filepath.resolve().parent == ATTACHMENTS_DIR.resolve():
                        self.send_response(200)
                        self.send_header("Content-Type", "application/pdf")
                        self.send_header("Content-Disposition", f'inline; filename="{filename}"')
                        self.end_headers()
                        self.wfile.write(filepath.read_bytes())
                    else:
                        self.send_response(404)
                        self.end_headers()
                elif self.path == "/add-alarm":
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(ADD_ALARM_HTML.encode())
                else:
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html")
                    self.end_headers()
                    self.wfile.write(EDITOR_HTML.encode())

            def do_POST(self):
                if self.path == "/api/upload":
                    content_type = self.headers.get("Content-Type", "")
                    if "multipart/form-data" not in content_type:
                        self.send_response(400)
                        self.end_headers()
                        return
                    length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(length)
                    boundary = content_type.split("boundary=")[1].encode()
                    parts = body.split(b"--" + boundary)
                    file_data = None
                    original_name = "upload.pdf"
                    for part in parts:
                        if b'name="file"' in part:
                            header_end = part.find(b"\r\n\r\n")
                            if header_end < 0:
                                continue
                            header_section = part[:header_end].decode(errors="replace")
                            m = re.search(r'filename="([^"]+)"', header_section)
                            if m:
                                original_name = os.path.basename(m.group(1))
                            file_data = part[header_end + 4:]
                            if file_data.endswith(b"\r\n"):
                                file_data = file_data[:-2]
                            break
                    if file_data is None:
                        self.send_response(400)
                        self.end_headers()
                        return
                    safe_name = f"{uuid.uuid4().hex[:8]}_{original_name}"
                    dest = ATTACHMENTS_DIR / safe_name
                    dest.write_bytes(file_data)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"name": original_name, "path": safe_name}).encode())
                elif self.path == "/api/delete-file":
                    length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(length)
                    data = json.loads(body)
                    filename = os.path.basename(data.get("filename", ""))
                    filepath = ATTACHMENTS_DIR / filename
                    if filepath.exists() and filepath.resolve().parent == ATTACHMENTS_DIR.resolve():
                        filepath.unlink()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                elif self.path == "/api/bulb-to":
                    length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(length)
                    data = json.loads(body)
                    idx = data.get("index", 0)
                    target = data.get("target", "daily")
                    bulbs = app_ref.goals_data.get("bulbs", [])
                    if 0 <= idx < len(bulbs):
                        item = bulbs.pop(idx)
                        today = str(date.today())
                        new_item = {"text": item["text"], "added_date": today}
                        if item.get("category"):
                            new_item["category"] = item["category"]
                        if target == "backlog":
                            dest = app_ref.goals_data.setdefault("backlog", [])
                            dest.append(new_item)
                        else:
                            dest = app_ref.goals_data.setdefault("daily_goals", [])
                            dest.append(new_item)
                        app_ref.goals_data["bulbs"] = bulbs
                        save_goals(app_ref.goals_data)
                        app_ref._needs_rebuild = True
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                elif self.path == "/api/move-to-backlog":
                    length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(length)
                    data = json.loads(body)
                    idx = data.get("index", 0)
                    daily = app_ref.goals_data.get("daily_goals", [])
                    if 0 <= idx < len(daily):
                        item = daily.pop(idx)
                        today = str(date.today())
                        new_item = {"text": item["text"], "added_date": today}
                        if item.get("category"):
                            new_item["category"] = item["category"]
                        backlog = app_ref.goals_data.setdefault("backlog", [])
                        backlog.append(new_item)
                        app_ref.goals_data["daily_goals"] = daily
                        save_goals(app_ref.goals_data)
                        app_ref._needs_rebuild = True
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                elif self.path == "/api/add-to-today":
                    length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(length)
                    data = json.loads(body)
                    idx = data.get("index", 0)
                    backlog = app_ref.goals_data.get("backlog", [])
                    if 0 <= idx < len(backlog):
                        item = backlog.pop(idx)
                        today = str(date.today())
                        new_item = {"text": item["text"], "added_date": today}
                        if item.get("category"):
                            new_item["category"] = item["category"]
                        daily = app_ref.goals_data.setdefault("daily_goals", [])
                        daily.append(new_item)
                        app_ref.goals_data["backlog"] = backlog
                        save_goals(app_ref.goals_data)
                        app_ref._needs_rebuild = True
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                elif self.path == "/api/goals":
                    length = int(self.headers.get("Content-Length", 0))
                    body = self.rfile.read(length)
                    data = json.loads(body)
                    save_goals(data)
                    app_ref.goals_data = data
                    app_ref.daily_state = load_daily_state()
                    app_ref.year_state = load_year_state()
                    app_ref._needs_rebuild = True
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')

            def log_message(self, format, *args):
                pass

        # Kill any stale server on the port
        os.system(f"lsof -ti:{EDITOR_PORT} | xargs kill -9 2>/dev/null")

        import time as _time
        import socket
        for attempt in range(5):
            try:
                server = HTTPServer(("127.0.0.1", EDITOR_PORT), EditorHandler)
                server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                self._editor_server = server
                break
            except OSError:
                _time.sleep(1)
        else:
            # Last resort: try a different port
            self._editor_server = HTTPServer(("127.0.0.1", EDITOR_PORT + 1), EditorHandler)
        t = threading.Thread(target=self._editor_server.serve_forever, daemon=True)
        t.start()

    @rumps.timer(1)
    def _check_rebuild(self, _):
        if self._needs_rebuild:
            self._needs_rebuild = False
            self._build_menu()

    @rumps.timer(0.5)
    def _roll_title(self, _):
        if self._rolling_text is None:
            return
        text = self._rolling_text
        sep = "   ·   "
        padded = text + sep
        cycle_len = len(padded)
        max_display = 20
        # Double the padded text so slicing always has enough chars
        doubled = padded + padded
        start = self._rolling_pos % cycle_len
        self.title = "🔨 " + doubled[start:start + max_display]
        self._rolling_pos += 1

    # ── Menu ──

    @staticmethod
    def _normalize_status(value) -> str:
        """Backward compat: convert old bool states to new string states."""
        if value is True:
            return "done"
        if value is False or value is None:
            return "todo"
        if value in ("todo", "working", "done"):
            return value
        return "todo"

    @staticmethod
    def _next_status(current: str) -> str:
        """Cycle: todo → working → done → todo."""
        return {"todo": "working", "working": "done", "done": "todo"}.get(current, "working")

    def _count(self, section: str, state: dict) -> tuple[int, int]:
        tasks = self.goals_data.get(section, [])
        total = len(tasks)
        done = sum(1 for i in range(total) if self._normalize_status(state["checked"].get(str(i))) == "done")
        return done, total

    def _wrapped_menu_item(self, text: str, callback=None) -> rumps.MenuItem:
        """Create a menu item with text wrapping, continuation lines indented."""
        # "✅  " is 4 chars — indent continuation lines to align with text
        indent = "      "  # align with text after checkbox
        wrapped = textwrap.fill(
            text, width=MENU_WIDTH,
            subsequent_indent=indent,
        )
        item = rumps.MenuItem(wrapped)
        if callback:
            item.set_callback(callback)
        else:
            item.set_callback(self._noop)
        # Use attributed string so newlines render properly
        font = AppKit.NSFont.menuFontOfSize_(13)
        para = AppKit.NSMutableParagraphStyle.alloc().init()
        para.setLineBreakMode_(0)  # word wrap
        attrs = {
            AppKit.NSFontAttributeName: font,
            AppKit.NSParagraphStyleAttributeName: para,
        }
        attr_str = AppKit.NSAttributedString.alloc().initWithString_attributes_(
            wrapped, attrs
        )
        item._menuitem.setAttributedTitle_(attr_str)
        return item

    def _progress_bar(self, done: int, total: int) -> str:
        if total == 0:
            return ""
        return "▓" * done + "░" * (total - done) + f"  {round(done / total * 100)}%"

    def _build_menu(self):
        self.menu.clear()
        daily_done, daily_total = self._count("daily_goals", self.daily_state)
        year_done, year_total = self._count("year_goals", self.year_state)

        # === Daily Goals ===
        daily_header = f"📅 Today  {self._progress_bar(daily_done, daily_total)}"
        header = rumps.MenuItem(daily_header)
        header.set_callback(self._reload_goals)
        self.menu.add(header)

        self.menu.add(rumps.separator)

        for i, task in enumerate(self.goals_data.get("daily_goals", [])):
            status = self._normalize_status(self.daily_state["checked"].get(str(i)))
            mark = {"todo": "⬜", "working": "🔨", "done": "✅"}[status]
            added = task.get("added_date")
            if added:
                days = (date.today() - date.fromisoformat(added)).days + 1
                day_label = f"  (day {days})"
            else:
                day_label = ""
            label = f"{mark}  {task['text']}{day_label}"
            item = self._wrapped_menu_item(label, self._make_daily_toggle(i))
            self.menu.add(item)

        self.menu.add(rumps.separator)

        # === Year Goals ===
        year_header = f"🏆 {date.today().year} Goals  {self._progress_bar(year_done, year_total)}"
        yheader = rumps.MenuItem(year_header)
        yheader.set_callback(self._reload_goals)
        self.menu.add(yheader)

        self.menu.add(rumps.separator)

        for i, task in enumerate(self.goals_data.get("year_goals", [])):
            status = self._normalize_status(self.year_state["checked"].get(str(i)))
            mark = {"todo": "⬜", "working": "🔨", "done": "✅"}[status]
            label = f"{mark}  {task['text']}"
            item = self._wrapped_menu_item(label, self._make_year_toggle(i))
            self.menu.add(item)

        self.menu.add(rumps.separator)

        # === Focus Timer ===
        total = format_duration(self._focus_state.get("total_seconds", 0))
        if self._focus_active:
            focus_label = f"⏱ Focus: {total}  ▶️ tracking..."
        else:
            focus_label = f"⏱ Focus: {total}"
        focus_item = rumps.MenuItem(focus_label)
        focus_item.set_callback(self._noop)
        self.menu.add(focus_item)

        self.menu.add(rumps.separator)

        # === Alarms ===
        alarms_menu = rumps.MenuItem("⏰ Alarms")
        for i, alarm in enumerate(self.goals_data.get("alarms", [])):
            alarm_date = alarm.get("date", "")
            if alarm_date:
                alabel = f"{alarm_date}  {alarm['time']} — {alarm['text']}"
            else:
                alabel = f"{alarm['time']} — {alarm['text']}"
            aitem = rumps.MenuItem(alabel)
            aitem.set_callback(self._make_delete_alarm(i))
            alarms_menu.add(aitem)
        if self.goals_data.get("alarms"):
            alarms_menu.add(rumps.separator)
        new_alarm = rumps.MenuItem("➕ New Alarm...")
        new_alarm.set_callback(self._add_alarm)
        alarms_menu.add(new_alarm)
        self.menu.add(alarms_menu)

        self.menu.add(rumps.separator)

        # === Bulbs (submenu) ===
        bulbs_menu = rumps.MenuItem("💡 Bulbs")
        for i, bulb in enumerate(self.goals_data.get("bulbs", [])):
            blabel = bulb["text"][:40] + ("…" if len(bulb["text"]) > 40 else "")
            bitem = rumps.MenuItem(blabel)
            bitem.set_callback(self._noop)
            bulbs_menu.add(bitem)
        if self.goals_data.get("bulbs"):
            bulbs_menu.add(rumps.separator)
        new_bulb = rumps.MenuItem("➕ New Bulb...")
        new_bulb.set_callback(self._add_bulb)
        bulbs_menu.add(new_bulb)
        self.menu.add(bulbs_menu)

        self.menu.add(rumps.separator)

        # === Actions ===
        edit = rumps.MenuItem("📝 Edit Goals...")
        edit.set_callback(self._open_editor)
        self.menu.add(edit)

        log_item = rumps.MenuItem("📊 View Log")
        log_item.set_callback(self._view_log)
        self.menu.add(log_item)

        self.menu.add(rumps.separator)
        quit_item = rumps.MenuItem("Quit")
        quit_item.set_callback(self._quit)
        self.menu.add(quit_item)

        # Menu bar icon — rolling text if any task is "working"
        working_text = None
        for i, task in enumerate(self.goals_data.get("daily_goals", [])):
            if self._normalize_status(self.daily_state["checked"].get(str(i))) == "working":
                working_text = task["text"]
                break

        if working_text:
            new_rolling = f"focus on: {working_text}"
            if self._rolling_text != new_rolling:
                self._rolling_text = new_rolling
                self._rolling_pos = 0
        else:
            self._rolling_text = None
            self._rolling_pos = 0
            if daily_done == daily_total and daily_total > 0:
                self.title = "🎯✨"
            elif daily_done > 0:
                self.title = f"🎯 {daily_done}/{daily_total}"
            else:
                self.title = "🎯"

    # ── Callbacks ──

    def _reload_goals(self, _):
        """Re-read goals from disk (picks up iCloud sync changes) and rebuild menu."""
        self.goals_data = load_goals()
        self.daily_state = load_daily_state()
        self.year_state = load_year_state()
        self._build_menu()

    def _noop(self, _):
        pass

    def _quit(self, _):
        self._editor_server.shutdown()
        for p in self._subprocesses:
            try:
                p.terminate()
            except Exception:
                pass
        rumps.quit_application(_)

    def _add_bulb(self, _):
        def _do():
            script = 'display dialog "What\'s on your mind?" default answer "" with title "💡 New Bulb" buttons {"Cancel", "Save"} default button "Save"'
            try:
                result = subprocess.run(
                    ["osascript", "-e", script],
                    capture_output=True, text=True, timeout=300,
                )
                if result.returncode == 0 and "text returned:" in result.stdout:
                    text = result.stdout.split("text returned:", 1)[1].strip()
                    if text:
                        bulbs = self.goals_data.setdefault("bulbs", [])
                        bulbs.insert(0, {"text": text, "created": str(date.today())})
                        save_goals(self.goals_data)
                        self._needs_rebuild = True
            except Exception:
                pass
        threading.Thread(target=_do, daemon=True).start()

    def _add_alarm(self, _):
        webbrowser.open(f"http://127.0.0.1:{EDITOR_PORT}/add-alarm")

    def _make_delete_alarm(self, idx: int):
        def delete(_):
            alarms = self.goals_data.get("alarms", [])
            if 0 <= idx < len(alarms):
                alarms.pop(idx)
                save_goals(self.goals_data)
                self._build_menu()
        return delete

    def _show_alarm_popup(self, text, time_str):
        def _do():
            # Play alert sound 3 times for attention
            try:
                subprocess.Popen(
                    ["afplay", "/System/Library/Sounds/Glass.aiff"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
            # Also send a macOS notification
            notif_script = (
                f'display notification "{text}" with title "⏰ Alarm — {time_str}" sound name "Glass"'
            )
            try:
                subprocess.run(
                    ["osascript", "-e", notif_script],
                    capture_output=True, text=True, timeout=10,
                )
            except Exception:
                pass
            # Show a prominent dialog that stays on top
            safe_text = text.replace('"', '\\"').replace("'", "'")
            dialog_script = f'''
                tell application "System Events"
                    activate
                    display dialog "⏰  {time_str}" & return & return & "{safe_text}" with title "Goals Alarm" buttons {{"Snooze 5m", "Dismiss"}} default button "Dismiss" with icon caution
                end tell
            '''
            try:
                result = subprocess.run(
                    ["osascript", "-e", dialog_script],
                    capture_output=True, text=True, timeout=600,
                )
                if result.returncode == 0 and "Snooze 5m" in result.stdout:
                    self._snooze_alarm(text, time_str)
            except Exception:
                pass
        threading.Thread(target=_do, daemon=True).start()

    def _snooze_alarm(self, text, time_str):
        """Re-fire an alarm after 5 minutes."""
        import time as _time
        def _do():
            _time.sleep(300)
            self._show_alarm_popup(text, time_str)
        threading.Thread(target=_do, daemon=True).start()

    @rumps.timer(30)
    def _check_alarms(self, _):
        now_time = datetime.now().strftime("%H:%M")
        today_str = str(date.today())
        alarms = self.goals_data.get("alarms", [])
        if not alarms:
            return
        fired = self.daily_state.get("fired_alarms", [])
        changed = False
        for alarm in alarms:
            alarm_date = alarm.get("date", today_str)
            if alarm_date != today_str:
                continue
            key = f"{alarm_date}-{alarm['time']}-{alarm['text']}"
            if alarm["time"] <= now_time and key not in fired:
                fired.append(key)
                changed = True
                self._show_alarm_popup(alarm["text"], alarm["time"])
        if changed:
            self.daily_state["fired_alarms"] = fired
            save_daily_state(self.daily_state)

    def _make_daily_toggle(self, idx: int):
        def toggle(_):
            key = str(idx)
            current = self._normalize_status(self.daily_state["checked"].get(key))
            self.daily_state["checked"][key] = self._next_status(current)
            save_daily_state(self.daily_state)
            self._build_menu()
        return toggle

    def _make_year_toggle(self, idx: int):
        def toggle(_):
            key = str(idx)
            current = self._normalize_status(self.year_state["checked"].get(key))
            self.year_state["checked"][key] = self._next_status(current)
            save_year_state(self.year_state)
            self._build_menu()
        return toggle

    def _view_log(self, _):
        log_viewer = Path(__file__).parent / "log_viewer.py"
        p = subprocess.Popen(
            [sys.executable, str(log_viewer)],
            cwd=Path(__file__).parent,
        )
        self._subprocesses.append(p)

    def _open_editor(self, _):
        webbrowser.open(f"http://127.0.0.1:{EDITOR_PORT}")

    # ── Daily rollover ──

    def _promote_scheduled_backlog(self):
        """Move backlog items whose scheduled_date has arrived to daily goals."""
        today = str(date.today())
        backlog = self.goals_data.get("backlog", [])
        remaining = []
        for item in backlog:
            sd = item.get("scheduled_date")
            if sd and sd <= today:
                daily = self.goals_data.setdefault("daily_goals", [])
                daily.append({"text": item["text"], "added_date": today})
            else:
                remaining.append(item)
        if len(remaining) != len(backlog):
            self.goals_data["backlog"] = remaining
            save_goals(self.goals_data)

    def _roll_over_daily(self):
        """Remove completed daily tasks, log them, keep uncompleted ones."""
        old_tasks = self.goals_data.get("daily_goals", [])
        completed_date = self.daily_state.get("date", str(date.today()))
        log = load_log()
        kept = []
        for i, task in enumerate(old_tasks):
            if self._normalize_status(self.daily_state["checked"].get(str(i))) == "done":
                added = task.get("added_date", completed_date)
                d_added = date.fromisoformat(added)
                d_done = date.fromisoformat(completed_date)
                days = (d_done - d_added).days + 1
                log.append({
                    "text": task["text"],
                    "added_date": added,
                    "completed_date": completed_date,
                    "days": days,
                })
            else:
                kept.append(task)
        save_log(log)
        self.goals_data["daily_goals"] = kept
        save_goals(self.goals_data)
        self.daily_state = {"date": str(date.today()), "checked": {}, "fired_alarms": []}
        save_daily_state(self.daily_state)
        self._promote_scheduled_backlog()

    @rumps.timer(10)
    def _track_focus(self, _):
        """Check YouTube every 10 seconds, track focus time."""
        yt_open = is_youtube_playing()
        if yt_open and not self._focus_active:
            self._focus_active = True
            self._build_menu()
        elif not yt_open and self._focus_active:
            self._focus_active = False
            log_focus_day(self._focus_state)
            save_focus_state(self._focus_state)
            self._build_menu()

        if self._focus_active:
            # New day while tracking — log previous day, reset
            if self._focus_state.get("date") != str(date.today()):
                log_focus_day(self._focus_state)
                self._focus_state = {"date": str(date.today()), "total_seconds": 0}
            self._focus_state["total_seconds"] += 10
            save_focus_state(self._focus_state)
            log_focus_day(self._focus_state)
            self._build_menu()

    @rumps.timer(5)
    def _check_file_changes(self, _):
        """Reload goals from disk if the file was modified externally (e.g. iCloud sync from iOS)."""
        try:
            mtime = DATA_FILE.stat().st_mtime if DATA_FILE.exists() else 0
        except OSError:
            return
        if mtime != self._goals_mtime:
            self._goals_mtime = mtime
            self.goals_data = load_goals()
            self.daily_state = load_daily_state()
            self.year_state = load_year_state()
            self._build_menu()

    @rumps.timer(60)
    def _check_new_day(self, _):
        if self.daily_state.get("date") != str(date.today()):
            # Log focus for the ending day before rollover
            log_focus_day(self._focus_state)
            self._focus_state = {"date": str(date.today()), "total_seconds": 0}
            save_focus_state(self._focus_state)
            self._roll_over_daily()
            self._build_menu()
        if self.year_state.get("year") != str(date.today().year):
            self.year_state = {"year": str(date.today().year), "checked": {}}
            save_year_state(self.year_state)
            self._build_menu()


if __name__ == "__main__":
    GoalsStickerApp().run()
