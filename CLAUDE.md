# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Goals Sticker is a macOS menu bar app for tracking daily and yearly goals. It uses `rumps` (Ridiculously Uncomplicated macOS Python Statusbar apps) to create a native menu bar interface, with embedded HTTP servers for a web-based editor and log viewer. There is also a companion iOS SwiftUI app in `ios/`.

## Running

```bash
# Install dependencies (uses uv with Python 3.12.2)
uv sync

# Run the menu bar app
uv run python main.py

# Run the standalone editor (port 5050)
uv run python editor.py

# Run the standalone log viewer (port 5051)
uv run python log_viewer.py
```

## Architecture

### Data Flow and Storage

All data lives in iCloud Drive at `~/Library/Mobile Documents/iCloud~com~fangbotu~goalsapp/Documents/` for sync with the iOS app. On first run, local files are migrated to iCloud. Key files:

- `goals.json` — master data: daily goals, year goals (with sub-goals), backlog, bulbs, focus video URLs
- `.daily_state.json` — today's check states (todo/working/done) for daily goals, resets each day
- `.year_state.json` — check states for year goals, resets each year
- `completed_log.json` — history of completed daily goals with duration tracking
- `focus_log.json` — daily focus time in seconds
- `.focus_state.json` — current day's accumulated focus time
- `attachments/` — uploaded files referenced by goals

### main.py (core app, ~1680 lines)

The `GoalsStickerApp(rumps.App)` class is the entry point. It contains:

- **Menu bar UI**: Shows goals with tri-state toggles (todo → working → done), progress bars, focus timer, bulbs submenu. When a task is "working", the menu bar title scrolls the task name.
- **Embedded editor server** (port 5050): A full web editor served from inline HTML with tabs for daily goals, backlog, bulbs, focus videos, and year goals with sub-goals. Supports file attachments, markdown notes, categories, and drag-and-drop reordering.
- **Focus tracking**: Polls Chrome every 10 seconds via AppleScript to detect if configured YouTube videos are playing, accumulates focus time.
- **Daily rollover**: At midnight (checked every 60s), completed tasks are logged to `completed_log.json`, uncompleted tasks carry over, and scheduled backlog items are promoted to daily goals.

### editor.py (standalone editor)

Simpler standalone version of the goals editor (port 5050). Serves a single-page web app for editing daily and year goals. The main app has its own more full-featured editor built in.

### log_viewer.py (activity log)

Web viewer (port 5051) showing focus time stats (daily bars, weekly averages with trend arrows) and completed goals history.

### ios/ (iOS companion app)

SwiftUI app (`GoalsApp`) that reads/writes the same iCloud container. Key structure:
- `Services/iCloudFileManager.swift` — handles iCloud document sync
- `Models/` — `GoalsData`, `DailyState`, `YearState`, `LogModels`, `CheckStatus`
- `Views/` — `ContentView`, daily/year goal views, shared components (CategoryTag, StatusBadge, etc.)

### Goal Status Model

Goals use a tri-state cycle: `todo` → `working` → `done` → `todo`. Legacy boolean states are normalized via `_normalize_status()`. States are stored by index position (string keys like `"0"`, `"1"`) in state files.
