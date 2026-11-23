"""Run with `py dowfile_web.py`, then visit http://localhost:8000."""

from collections import Counter
from datetime import datetime, timedelta, timezone
from hmac import compare_digest
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from secrets import token_urlsafe
from threading import Lock, Timer, current_thread
from urllib.parse import parse_qs

from dowfile_org import DEFAULT_FOLDER, organize_all


PORT = 8000
LOCAL_HOSTS = {f"localhost:{PORT}", f"127.0.0.1:{PORT}"}
FORM_TOKEN = token_urlsafe(32)
ORGANIZE_LOCK = Lock()
INTERVAL_HOURS = (0, 1, 2, 4, 6, 12, 24)
STATUS_LABELS = {"moved": "Moved", "skipped": "Skipped", "failed": "Error"}
ASSET_DIR = Path(__file__).resolve().parent / "web"
ASSETS = {
    "/frappe.css": ("frappe.css", "text/css; charset=utf-8"),
    "/folder-picker.js": ("folder-picker.js", "text/javascript; charset=utf-8"),
    "/PixelifySans.ttf": ("PixelifySans.ttf", "font/ttf"),
}


def run_organizer(folder):
    try:
        results = organize_all(folder)
    except (OSError, RuntimeError, ValueError) as error:
        return f"Could not organize this folder: {error}", (), False
    moved = sum(result.status == "moved" for result in results)
    message = f"Finished. Moved {moved} of {len(results)} files." if results else "No files to organize."
    return message, results, True


class AutomationSchedule:
    def __init__(self):
        self.folder = None
        self.hours = 0
        self.next_run = None
        self.report = None
        self._timer = None

    def snapshot(self):
        with ORGANIZE_LOCK:
            return self.folder, self.hours, self.next_run, self.report

    def configure(self, folder=None, hours=0):
        with ORGANIZE_LOCK:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            self.folder, self.hours = folder, hours
            self.next_run = self.report = None
            if hours:
                self._queue_run()

    def _queue_run(self):
        self.next_run = datetime.now(timezone.utc) + timedelta(hours=self.hours)
        self._timer = Timer(self.hours * 3600, self._run)
        self._timer.daemon = True
        self._timer.start()

    def _run(self):
        with ORGANIZE_LOCK:
            if current_thread() is not self._timer:
                return
            self.report = run_organizer(self.folder)
            self._queue_run()


SCHEDULE = AutomationSchedule()


def interval_label(hours):
    if not hours:
        return "Manual only"
    return f"Every {hours} {'hour' if hours == 1 else 'hours'}"


def list_folders(folder_path):
    home = Path.home()
    selected = Path(folder_path).expanduser() if folder_path else DEFAULT_FOLDER
    if not folder_path and not selected.is_dir():
        selected = home
    if not selected.is_absolute():
        raise ValueError("Enter the full path to a folder.")
    selected = selected.resolve(strict=True)

    children = []
    with os.scandir(selected) as entries:
        for entry in entries:
            try:
                if entry.is_dir():
                    children.append({"name": entry.name, "path": entry.path})
            except OSError:
                continue
    children.sort(key=lambda child: child["name"].casefold())

    locations = [{"name": "Home", "path": str(home)}]
    if DEFAULT_FOLDER.is_dir():
        locations.append({"name": "Downloads", "path": str(DEFAULT_FOLDER)})
    list_drives = getattr(os, "listdrives", None)
    try:
        roots = list_drives() if list_drives else [home.anchor]
    except OSError:
        roots = [home.anchor]
    locations.extend({"name": root, "path": root} for root in roots)
    return {
        "path": str(selected),
        "parent": str(selected.parent) if selected.parent != selected else None,
        "children": children,
        "locations": locations,
    }


def render_file_details(folder_path, results):
    if not results:
        return ""

    rows = []
    selected_folder = Path(folder_path).expanduser()
    for result in results:
        detail = f'<small class="file-note">{escape(result.detail)}</small>' if result.detail else ""
        subfolder = escape(result.category)
        destination = escape(str(selected_folder / result.category))
        rows.append(f"""
          <tr>
            <td><span class="file-name">{escape(result.name)}</span>{detail}</td>
            <td><code class="subfolder-path" title="{destination}">{subfolder}/</code></td>
            <td><span class="status-tag {result.status}">{STATUS_LABELS[result.status]}</span></td>
          </tr>""")

    return f"""
      <h3 class="activity-title" id="file-details-heading">File details</h3>
      <div class="table-scroll" role="region" aria-labelledby="file-details-heading" tabindex="0">
        <table>
          <colgroup><col class="file-column"><col class="subfolder-column"><col></colgroup>
          <thead><tr>
            <th scope="col">File</th><th scope="col">Subfolder</th><th scope="col">Status</th>
          </tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
      </div>"""


def render_analysis(folder_path, message, results):
    counts = Counter(result.status for result in results)
    outcomes = (
        ("moved", "Moved", counts["moved"]),
        ("skipped", "Skipped", counts["skipped"]),
        ("failed", "Errors", counts["failed"]),
    )
    chart_segments = "".join(
        f'<span class="{kind}" style="flex-grow: {count}"></span>'
        for kind, _, count in outcomes
        if count
    )
    stat_cards = "".join(
        f'<div><dt><span class="dot {kind}"></span>{label}</dt><dd>{count}</dd></div>'
        for kind, label, count in outcomes
    )
    return f"""
      <section class="panel" aria-labelledby="activity-heading">
        <h2 id="activity-heading"><span class="section-prompt" aria-hidden="true">02 /</span> File Movement Analysis</h2>
        <div class="chart" aria-hidden="true">{chart_segments}</div>
        <dl class="stats">{stat_cards}</dl>
        <p class="hint completion-notice" role="status">{escape(message)}</p>
        {render_file_details(folder_path, results)}
      </section>"""


def render_page(folder_path, message="", results=(), *, completed=False, hours=0, schedule_note=""):
    analysis = render_analysis(folder_path, message, results) if completed else ""
    error_notice = f'<p class="hint form-error" role="alert">{escape(message)}</p>' if message and not completed else ""
    interval_options = "".join(
        f'<option value="{option}"{" selected" if option == hours else ""}>{interval_label(option)}</option>'
        for option in INTERVAL_HOURS
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Python File Automation</title>
  <link rel="stylesheet" href="/frappe.css">
  <script src="/folder-picker.js" defer></script>
</head>
<body>
  <main class="terminal">
    <div class="terminal-bar">
      <span>file-automation</span>
      <span class="terminal-address">localhost:{PORT}</span>
    </div>
    <div class="terminal-content">
      <header class="hero">
        <div class="hero-icon" aria-hidden="true">📄</div>
        <h1>Python File Automation</h1>
        <p class="hero-description">Organize files by type without scanning existing subfolders.</p>
      </header>
      <form class="panel" method="post" action="/organize" aria-labelledby="workspace-heading">
        <input type="hidden" id="form-token" name="token" value="{FORM_TOKEN}">
        <h2 id="workspace-heading"><span class="section-prompt" aria-hidden="true">01 /</span> Workspace</h2>
        <label for="folder">Folder path</label>
        <div class="form-row">
          <input id="folder" name="folder" value="{escape(folder_path)}"
                 aria-describedby="folder-help" required>
          <button type="button" id="browse" class="secondary" aria-haspopup="dialog"
                  aria-controls="folder-picker" hidden>Browse</button>
        </div>
        <small id="folder-help">Choose a folder or paste its full path. Downloads is selected by default.</small>
        <p id="folder-selection" class="folder-selection" role="status"></p>
        <div class="interval-settings">
          <label for="interval">Run interval (hours)</label>
          <select id="interval" name="hours" aria-describedby="interval-help">{interval_options}</select>
          <small id="interval-help">Apply Schedule to set or stop automatic runs. The first run waits
            for the selected interval. Keep the server running.</small>
        </div>
        <div class="workspace-actions">
          <button type="submit" class="secondary">Organize Files</button>
          <button type="submit" class="secondary" formaction="/schedule" formnovalidate>Apply Schedule</button>
        </div>
        <p class="hint schedule-status" role="status">{escape(schedule_note)}</p>
        {error_notice}
      </form>
      {analysis}
    </div>
  </main>
  <dialog id="folder-picker" aria-labelledby="picker-heading">
    <h2 id="picker-heading">Choose a folder</h2>
    <p class="picker-path" id="picker-path" tabindex="-1">Choose where to organize files.</p>
    <div class="picker-nav">
      <button type="button" class="secondary" id="parent-folder" disabled>Parent folder</button>
      <div class="folder-locations" id="folder-locations"></div>
    </div>
    <ul class="folder-list" id="folder-list" aria-label="Subfolders"></ul>
    <p class="hint" id="picker-message" role="status"></p>
    <form method="dialog" class="picker-actions">
      <button type="submit" class="secondary" autofocus>Cancel</button>
      <button type="button" class="primary" id="select-folder" disabled>Select this folder</button>
    </form>
  </dialog>
</body>
</html>"""


class OrganizerHandler(BaseHTTPRequestHandler):
    def valid_host(self):
        if self.headers.get("Host") not in LOCAL_HOSTS:
            self.send_error(403)
            return False
        return True

    def send_content(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(body)

    def send_page(self, folder_path=None, message="", results=(), status=200, *, completed=False, hours=None):
        scheduled_folder, scheduled_hours, next_run, report = SCHEDULE.snapshot()
        schedule_note = "No automatic schedule is active."
        if next_run is not None:
            next_local = next_run.astimezone().strftime("%b %d, %I:%M %p")
            schedule_note = f"{interval_label(scheduled_hours)} for {scheduled_folder}. Next run: {next_local}."
        if folder_path is None:
            folder_path = str(scheduled_folder or DEFAULT_FOLDER)
            if report is not None:
                message, results, completed = report
                message = f"Last automatic run: {message}"
        body = render_page(
            folder_path, message, results, completed=completed,
            hours=scheduled_hours if hours is None else hours, schedule_note=schedule_note,
        ).encode("utf-8")
        self.send_content(body, "text/html; charset=utf-8", status)

    def send_json(self, data, status=200):
        self.send_content(json.dumps(data).encode("utf-8"), "application/json", status)

    def do_GET(self):
        if not self.valid_host():
            return
        if self.path == "/":
            self.send_page()
        elif self.path in ASSETS:
            filename, content_type = ASSETS[self.path]
            self.send_content((ASSET_DIR / filename).read_bytes(), content_type)
        else:
            self.send_error(404)

    def do_POST(self):
        if not self.valid_host():
            return
        if self.path not in {"/organize", "/browse", "/schedule"}:
            self.send_error(404)
            return
        if self.headers.get_content_type() != "application/x-www-form-urlencoded":
            self.send_error(415)
            return
        try:
            length = int(self.headers["Content-Length"])
            if not 0 < length <= 32768:
                raise ValueError
            field_limit = 2 if self.path == "/browse" else 3
            values = parse_qs(self.rfile.read(length).decode("utf-8"), max_num_fields=field_limit)
        except (TypeError, ValueError):
            self.send_error(400)
            return
        token = values.get("token", [""])[0]
        if not compare_digest(token.encode("utf-8"), FORM_TOKEN.encode("ascii")):
            self.send_error(403)
            return

        folder_path = values.get("folder", [""])[0].strip().strip('"')
        if self.path == "/browse":
            try:
                listing = list_folders(folder_path)
            except (OSError, RuntimeError, ValueError):
                self.send_json({"error": "This folder could not be opened."}, status=400)
            else:
                self.send_json(listing)
            return

        interval = values.get("hours", ["" if self.path == "/schedule" else "0"])[0]
        hours = next((option for option in INTERVAL_HOURS if str(option) == interval), None)
        if hours is None:
            self.send_page(folder_path, "Choose a valid run interval.", status=400)
            return
        selected = None
        if self.path == "/organize" or hours:
            try:
                selected = Path(folder_path).expanduser()
                if not selected.is_absolute() or not selected.is_dir():
                    raise ValueError
                selected = selected.resolve(strict=True)
            except (OSError, RuntimeError, ValueError):
                self.send_page(folder_path, "Enter the full path to an existing folder.", status=400, hours=hours)
                return

        if self.path == "/schedule":
            SCHEDULE.configure(selected, hours)
            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()
            return

        with ORGANIZE_LOCK:
            message, results, completed = run_organizer(selected)
        self.send_page(folder_path, message, results, 200 if completed else 400, completed=completed, hours=hours)


if __name__ == "__main__":
    with ThreadingHTTPServer(("127.0.0.1", PORT), OrganizerHandler) as server:
        print(f"Open http://localhost:{PORT} in your browser. Press Ctrl+C to stop.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
