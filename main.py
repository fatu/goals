"""Goals Sticker — a macOS menu bar app to track daily + yearly goals."""

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import rumps

DATA_FILE = Path(__file__).parent / "goals.json"
STATE_FILE = Path(__file__).parent / ".daily_state.json"
YEAR_STATE_FILE = Path(__file__).parent / ".year_state.json"
LOG_FILE = Path(__file__).parent / "completed_log.json"
EDITOR_SCRIPT = Path(__file__).parent / "editor.py"


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
            return state
    return {"date": str(date.today()), "checked": {}}


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


class GoalsStickerApp(rumps.App):
    def __init__(self):
        super().__init__("🎯", quit_button=None)
        self._subprocesses = []
        self.daily_state = load_daily_state()
        self.year_state = load_year_state()
        self.goals_data = load_goals()
        # On startup, roll over if it's a new day
        if self.daily_state.get("date") != str(date.today()):
            self._roll_over_daily()
        self._build_menu()

    def _count(self, section: str, state: dict) -> tuple[int, int]:
        tasks = self.goals_data.get(section, [])
        total = len(tasks)
        done = sum(1 for i in range(total) if state["checked"].get(str(i), False))
        return done, total

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
        header.set_callback(self._noop)
        self.menu.add(header)

        self.menu.add(rumps.separator)

        for i, task in enumerate(self.goals_data.get("daily_goals", [])):
            is_done = self.daily_state["checked"].get(str(i), False)
            mark = "✅" if is_done else "⬜"
            added = task.get("added_date")
            if added:
                days = (date.today() - date.fromisoformat(added)).days + 1
                day_label = f"  (day {days})"
            else:
                day_label = ""
            item = rumps.MenuItem(f"  {mark}  {task['text']}{day_label}")
            item.set_callback(self._make_daily_toggle(i))
            self.menu.add(item)

        self.menu.add(rumps.separator)

        # === Year Goals ===
        year_header = f"🏆 {date.today().year} Goals  {self._progress_bar(year_done, year_total)}"
        yheader = rumps.MenuItem(year_header)
        yheader.set_callback(self._noop)
        self.menu.add(yheader)

        self.menu.add(rumps.separator)

        for i, task in enumerate(self.goals_data.get("year_goals", [])):
            is_done = self.year_state["checked"].get(str(i), False)
            mark = "✅" if is_done else "⬜"
            item = rumps.MenuItem(f"  {mark}  {task['text']}")
            item.set_callback(self._make_year_toggle(i))
            self.menu.add(item)

        self.menu.add(rumps.separator)

        # === Actions ===
        edit = rumps.MenuItem("📝 Edit Goals...")
        edit.set_callback(self._open_editor)
        self.menu.add(edit)

        reload_item = rumps.MenuItem("🔃 Reload Goals")
        reload_item.set_callback(self._reload_goals)
        self.menu.add(reload_item)

        log_item = rumps.MenuItem("📊 View Log")
        log_item.set_callback(self._view_log)
        self.menu.add(log_item)

        self.menu.add(rumps.separator)
        quit_item = rumps.MenuItem("Quit")
        quit_item.set_callback(self._quit)
        self.menu.add(quit_item)

        # Menu bar icon
        if daily_done == daily_total and daily_total > 0:
            self.title = "🎯✨"
        elif daily_done > 0:
            self.title = f"🎯 {daily_done}/{daily_total}"
        else:
            self.title = "🎯"

    def _noop(self, _):
        pass

    def _quit(self, _):
        for p in self._subprocesses:
            try:
                p.terminate()
            except Exception:
                pass
        rumps.quit_application(_)

    def _make_daily_toggle(self, idx: int):
        def toggle(_):
            key = str(idx)
            self.daily_state["checked"][key] = not self.daily_state["checked"].get(key, False)
            save_daily_state(self.daily_state)
            self._build_menu()
        return toggle

    def _make_year_toggle(self, idx: int):
        def toggle(_):
            key = str(idx)
            self.year_state["checked"][key] = not self.year_state["checked"].get(key, False)
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
        p = subprocess.Popen(
            [sys.executable, str(EDITOR_SCRIPT)],
            cwd=Path(__file__).parent,
        )
        self._subprocesses.append(p)

    def _reload_goals(self, _):
        self.goals_data = load_goals()
        self.daily_state = load_daily_state()
        self.year_state = load_year_state()
        self._build_menu()

    def _roll_over_daily(self):
        """Remove completed daily tasks, log them, keep uncompleted ones."""
        old_tasks = self.goals_data.get("daily_goals", [])
        completed_date = self.daily_state.get("date", str(date.today()))
        log = load_log()
        kept = []
        for i, task in enumerate(old_tasks):
            if self.daily_state["checked"].get(str(i), False):
                added = task.get("added_date", completed_date)
                d_added = date.fromisoformat(added)
                d_done = date.fromisoformat(completed_date)
                days = (d_done - d_added).days + 1  # inclusive
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
        self.daily_state = {"date": str(date.today()), "checked": {}}
        save_daily_state(self.daily_state)

    @rumps.timer(60)
    def _check_new_day(self, _):
        if self.daily_state.get("date") != str(date.today()):
            self._roll_over_daily()
            self._build_menu()
        if self.year_state.get("year") != str(date.today().year):
            self.year_state = {"year": str(date.today().year), "checked": {}}
            save_year_state(self.year_state)
            self._build_menu()


if __name__ == "__main__":
    GoalsStickerApp().run()
