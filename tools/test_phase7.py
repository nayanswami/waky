"""Checks for v1.1: update checker, mouse-button hotkeys, pill visibility modes, paste-last hotkey."""
from __future__ import annotations

import hashlib
import http.server
import json
import logging
import os
import sys
import tempfile

os.environ["WAKY_DATA_DIR"] = tempfile.mkdtemp()   # never touch the real AppData settings or memory
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

# ---------- tap detection + double-tap hands-free lock ----------
ev = []
lock_settings = {"hotkeys": {"push_to_talk": "<f8>", "push_to_talk_backup": "", "toggle_recording": "<f9>", "cancel": "<esc>", "double_tap_lock": True}}
lm = hotkeys.HotkeyManager(
    lock_settings, logging.getLogger("t"), lambda: ev.append("start") or True, lambda: ev.append("stop"),
    lambda: ev.append("toggle"), lambda: ev.append("cancel"), lambda m: ev.append("err"),
    on_push_tap=lambda: ev.append("tap"), on_lock_changed=lambda on: ev.append("lock" if on else "unlock"),
)
# normal hold still works: start, then stop on release
lm._press("f8"); time.sleep(0.5); lm._release("f8")
assert ev == ["start", "stop"], ev
# one quick tap = silent tap (no 'stop'), not dictation
ev.clear(); time.sleep(0.6)
lm._press("f8"); time.sleep(0.12); lm._release("f8")
assert ev == ["start", "tap"], ev
# second quick tap within the gap locks recording on and keeps it running
ev.clear()
time.sleep(0.15)
lm._press("f8"); time.sleep(0.12); lm._release("f8")
assert ev == ["start", "lock"] and lm.locked, ev
# releasing other keys while locked changes nothing
lm._press("shift"); lm._release("shift")
assert "stop" not in ev
# pressing the key again stops; key repeat must not restart it; release is a no-op
ev.clear()
lm._press("f8"); lm._press("f8"); lm._release("f8")
assert ev == ["unlock", "stop"] and not lm.locked, ev
# a tap followed much later by another tap does not lock
ev.clear(); time.sleep(0.7)
lm._press("f8"); time.sleep(0.1); lm._release("f8")
time.sleep(0.8)
lm._press("f8"); time.sleep(0.1); lm._release("f8")
assert "lock" not in ev, ev
# a tap then a long hold is normal dictation
ev.clear(); time.sleep(0.7)
lm._press("f8"); time.sleep(0.1); lm._release("f8")
time.sleep(0.1)
lm._press("f8"); time.sleep(0.6); lm._release("f8")
assert ev[-1] == "stop" and "lock" not in ev, ev
# feature can be switched off
lock_settings["hotkeys"]["double_tap_lock"] = False
ev.clear(); time.sleep(0.7)
for _ in range(2):
    lm._press("f8"); time.sleep(0.1); lm._release("f8"); time.sleep(0.1)
assert "lock" not in ev and not lm.locked, ev
lock_settings["hotkeys"]["double_tap_lock"] = True
# a stale lock is dropped when the pipeline resets, and Esc also drops it
ev.clear(); time.sleep(0.7)
lm._press("f8"); time.sleep(0.1); lm._release("f8"); time.sleep(0.1)
lm._press("f8"); time.sleep(0.1); lm._release("f8")
assert lm.locked
lm.clear_lock()
assert not lm.locked

# ---------- per-app profiles ----------
from app import app_profiles

settings_p = {
    "command_processing": {"custom_instructions": "I am Nayan."},
    "app_profiles": {"enabled": True, "items": [
        {"name": "Chat", "match": "slack.exe, discord", "instruction": "Be casual.", "light": False, "enabled": True},
        {"name": "Mail", "match": "Gmail", "instruction": "Be polite.", "enabled": True},
        {"name": "Code", "match": "code.exe", "instruction": "Keep identifiers.", "light": True, "enabled": True},
        {"name": "Off", "match": "notepad.exe", "instruction": "x", "enabled": False},
    ]},
}
slack = app_profiles.AppInfo("slack.exe", "general - Slack")
assert app_profiles.match_profile(settings_p, slack)["name"] == "Chat"
assert app_profiles.match_profile(settings_p, app_profiles.AppInfo("chrome.exe", "Inbox (3) - Gmail - Brave"))["name"] == "Mail"
assert app_profiles.match_profile(settings_p, app_profiles.AppInfo("notepad.exe", "a.txt")) is None, "disabled profiles are ignored"
assert app_profiles.match_profile(settings_p, app_profiles.AppInfo("calc.exe", "Calculator")) is None
assert app_profiles.match_profile(settings_p, None) is None
settings_p["app_profiles"]["enabled"] = False
assert app_profiles.match_profile(settings_p, slack) is None
settings_p["app_profiles"]["enabled"] = True
run = app_profiles.apply_profile(settings_p, settings_p["app_profiles"]["items"][0])
assert "I am Nayan." in run["command_processing"]["custom_instructions"] and "Be casual." in run["command_processing"]["custom_instructions"]
assert settings_p["command_processing"]["custom_instructions"] == "I am Nayan.", "stored settings must not change"
light = app_profiles.apply_profile(settings_p, settings_p["app_profiles"]["items"][2])
assert light["command_processing"]["command_rewrite_engine"] == "rule_based_only"
assert app_profiles.apply_profile(settings_p, None) is settings_p
assert app_profiles.foreground_app() is None or app_profiles.foreground_app().exe  # never raises

# ---------- retired Groq models are replaced automatically ----------
from app import llm_engine

ids = ["whisper-large-v3", "openai/gpt-oss-120b", "openai/gpt-oss-20b", "meta-llama/llama-prompt-guard-2-22m", "qwen/qwen3.8-27b"]
assert llm_engine.pick_model("llama-3.3-70b-versatile", False, ids) == "openai/gpt-oss-120b"
assert llm_engine.pick_model("llama-3.1-8b-instant", True, ids) == "openai/gpt-oss-20b"
assert llm_engine.pick_model("openai/gpt-oss-20b", False, ids) == "openai/gpt-oss-20b", "a model that exists is kept"
assert llm_engine.pick_model("anything", True, []) == "anything", "unknown availability keeps the setting"
assert llm_engine.pick_model("old", False, ["whisper-large-v3", "foo/guard-1", "acme/chat-1"]) == "acme/chat-1"
assert llm_engine._strip_wrapping("<think>hmm</think>Hello there") == "Hello there"

# ---------- history, word changes and teaching ----------
import tempfile as _tf
from app import history as history_mod

assert history_mod.word_changes("hey rahool can you send it", "Hey Rahul, can you send it.") == [("rahool", "Rahul")] or ("rahool", "Rahul") in history_mod.word_changes("hey rahool can you send it", "Hey Rahul, can you send it.")
assert ("rahul", "Rahul") in history_mod.word_changes("tell rahul now", "tell Rahul now"), "casing-only fixes are noticed"
assert history_mod.word_changes("a b c", "a b c d") == []
hist = history_mod.History(Path(_tf.mkdtemp()) / "h.json")
hist.add("um send it to rahool", "Send it to Rahool.", "slack.exe")
hist.add("ok thanks", "OK, thanks.", "chrome.exe")
assert hist.recent_context("slack.exe") == "Send it to Rahool."
assert "OK, thanks." in hist.recent_context("")
assert history_mod.History(hist.path).newest_first()[0]["written"] == "OK, thanks.", "history persists"
hist.add("secret", "secret", "x.exe", persist=False)
assert "secret" not in hist.path.read_text(encoding="utf-8"), "persist=False keeps text out of the file"
from app import local_memory, speech_hints

local_memory.ensure_memory_files()
assert history_mod.learn([("rahool", "Rahul"), ("rahul", "Rahul")]) == 2
assert ("rahool", "Rahul") in speech_hints.corrections() and "Rahul" in speech_hints.vocabulary()
assert "Rahul" in speech_hints.stt_prompt({"transcription": {"language_mode": "hinglish"}}) and "Kal main" in speech_hints.stt_prompt({"transcription": {"language_mode": "hinglish"}})

# ---------- dictation stays your own words ----------
from app import command_processor as cp

plain = {"output": {"writing_style": "exact"}, "command_processing": {"voice_commands_enabled": True, "local_memory_enabled": True}, "providers": {"groq": {"api_key": ""}}}
assert cp.process_text("I like pizza and the main page is broken", plain) == "I like pizza and the main page is broken"
assert cp.process_text("he is very professional and I extended the deadline casually", plain) == "He is very professional and I extended the deadline casually"
assert cp.process_text("um I think uh the the plan works", plain) == "I think the plan works"
assert cp.process_text("this is fine — really", plain) == "This is fine, really"
assert cp.process_text("my email is on the slide", plain) == "My email is on the slide", "empty placeholder snippets never swallow a sentence"
assert cp._plausible_cleanup("send the report tomorrow please", "Send the report tomorrow, please.")
assert not cp._plausible_cleanup("what time is the meeting", "The meeting is at 3 PM. Let me know if you need anything else about it today.")
assert cp._sanitize_output("a – b -- c") == "a, b, c"

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
