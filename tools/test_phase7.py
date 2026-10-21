"""Checks for v1.1: update checker, mouse-button hotkeys, pill visibility modes, paste-last hotkey."""
from __future__ import annotations

import hashlib
import http.server
import json
import logging
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from app import hotkeys, updater
from app.config_manager import ConfigManager

app = QApplication([])

# ---------- version logic ----------
assert updater.parse_version("v1.2.10") == (1, 2, 10)
assert updater.is_newer("1.1.1", "1.1.0") and updater.is_newer("1.10.0", "1.9.9") and updater.is_newer("2.0", "1.9.9")
assert not updater.is_newer("1.1.0", "1.1.0") and not updater.is_newer("1.0.9", "1.1.0")
assert not updater.is_newer("1.1", "1.1.0")

# ---------- release parsing ----------
digest = "a" * 64
release = {
    "tag_name": "v9.9.9", "draft": False, "prerelease": False, "html_url": "https://example.test/r",
    "body": f"Notes here\nSHA-256: {digest}",
    "assets": [{"name": "Other.zip", "browser_download_url": "x", "size": 1}, {"name": updater.ASSET_NAME, "browser_download_url": "http://x/y.exe", "size": 5}],
}
info = updater.info_from_release(release)
assert info and info.version == "9.9.9" and info.sha256 == digest and info.asset_url == "http://x/y.exe"
assert updater.info_from_release({**release, "draft": True}) is None
assert updater.info_from_release({**release, "assets": []}) is None

# ---------- download + checksum, against a local server ----------
payload = os.urandom(300_000)
good = hashlib.sha256(payload).hexdigest()


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path.endswith("release"):
            body = json.dumps({**release, "tag_name": "v9.9.9", "assets": [{"name": updater.ASSET_NAME, "browser_download_url": f"http://127.0.0.1:{self.server.server_port}/file", "size": len(payload)}], "body": f"sha {good}"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    def log_message(self, *args):
        pass


server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{server.server_port}"

progress = []
path = updater.download(updater.UpdateInfo("9.9.9", "", f"{base}/file", good, "", len(payload)), progress.append)
assert path.read_bytes() == payload and progress and progress[-1] == 100
try:
    updater.download(updater.UpdateInfo("9.9.9", "", f"{base}/file", "b" * 64, "", len(payload)))
    raise AssertionError("a wrong checksum must be rejected")
except updater.UpdateError:
    pass

# ---------- UpdateChecker end to end ----------
updater.API_URL = f"{base}/release"
cfg = ConfigManager(Path(tempfile.mkdtemp()))
checker = updater.UpdateChecker(cfg)
found, ready, failed = [], [], []
checker.update_found.connect(found.append)
checker.installer_ready.connect(ready.append)
checker.install_failed.connect(failed.append)


def pump(cond, seconds=6.0):
    end = time.time() + seconds
    while time.time() < end and not cond():
        loop = QEventLoop()
        QTimer.singleShot(30, loop.quit)
        loop.exec()
    assert cond(), "timed out"


checker.check(manual=True)
pump(lambda: found)
assert found[0].version == "9.9.9" and checker.latest is found[0]
assert cfg.settings["updates"]["last_check"] > 0
checker.install()
pump(lambda: ready or failed)
assert ready and not failed and ready[0].read_bytes() == payload

# auto check respects the once-a-day gate and the skip list
found.clear()
checker.auto_check()
time.sleep(0.3)
app.processEvents()
assert not found, "auto_check must not run twice within a day"
cfg.settings["updates"]["last_check"] = 0
checker.skip("9.9.9")
checker.auto_check()
pump(lambda: not checker._busy)
app.processEvents()
assert not found, "a skipped version must not pop up on automatic checks"
checker.check(manual=True)
pump(lambda: found)

# ---------- hotkeys: mouse buttons ----------
assert hotkeys.pretty_combo("<mouse_x1>") == "Mouse Back"
assert hotkeys.pretty_combo("<ctrl>+<mouse_middle>") == "Ctrl + Middle Click"
assert hotkeys.is_safe_combo({"mouse_x2"}) and hotkeys.combo_from_tokens({"mouse_x1"}) == "<mouse_x1>"


class FakeButton:
    def __init__(self, name):
        self.name = name


assert hotkeys.mouse_token(FakeButton("x1")) == "mouse_x1" and hotkeys.mouse_token(FakeButton("left")) is None

events = []
settings = {"hotkeys": {"push_to_talk": "<mouse_x1>", "push_to_talk_backup": "<f8>", "toggle_recording": "<mouse_middle>", "cancel": "<esc>", "paste_last": "<ctrl>+<alt>+<v>"}}
mgr = hotkeys.HotkeyManager(
    settings, logging.getLogger("t"), lambda: events.append("start") or True, lambda: events.append("stop"),
    lambda: events.append("toggle"), lambda: events.append("cancel"), lambda m: events.append("err:" + m),
    on_paste_last=lambda: events.append("paste"),
)
assert mgr._uses_mouse() and mgr._configured_tokens() >= {"mouse_x1", "mouse_middle", "ctrl", "alt", "v"}
mgr._press("mouse_x1")
time.sleep(0.2)
assert events == ["start"], events
mgr._release("mouse_x1")
assert events == ["start", "stop"], events
mgr._press("mouse_middle")
mgr._release("mouse_middle")
assert events[-1] == "toggle"
for tok in ("ctrl", "alt", "v"):
    mgr._press(tok)
assert events[-1] == "paste"
n = len(events)
mgr._press("v")  # held key repeating must not paste twice
assert len(events) == n
for tok in ("ctrl", "alt", "v"):
    mgr._release(tok)

# ---------- pill visibility modes ----------
from app.ui_floating_bar import FloatingBar

bar_settings = {"floating_bar": {"visibility": "always", "style": "island", "accent": "#2E62FF", "size": 100}}
bar = FloatingBar(bar_settings)
bar.present()
assert bar.isVisible() and bar._visibility_target() == 1.0
bar_settings["floating_bar"]["visibility"] = "hidden"
assert bar._visibility_target() == 0.0
for _ in range(60):
    bar._tick()
assert not bar.isVisible(), "hidden mode fades the pill out and hides the window"
bar_settings["floating_bar"]["visibility"] = "active"
bar._linger_until = 0.0
bar.set_status("Idle")
assert bar._visibility_target() == 0.0
bar.set_status("Listening")
assert bar._visibility_target() == 1.0
for _ in range(60):
    bar._tick()
assert bar.isVisible(), "active mode shows the pill while dictating"
bar.set_status("Idle")
bar._linger_until = 0.0
for _ in range(90):
    bar._tick()
assert not bar.isVisible(), "active mode hides again when idle"
bar_settings["floating_bar"].pop("visibility")
bar_settings["floating_bar"]["hidden"] = True
assert bar.visibility_mode() == "hidden", "old 'hidden' flag is honoured"

print("phase 7 checks passed")
