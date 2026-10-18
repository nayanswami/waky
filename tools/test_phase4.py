"""Offscreen checks for hotkey helpers, pill styles and the onboarding wizard."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from app import hotkeys, pill_styles, secret_store

# Never touch the real Windows Credential Manager from tests.
_fake_store: dict[str, str] = {}
secret_store.get = lambda name: _fake_store.get(name, "")
secret_store.set = lambda name, value: (_fake_store.__setitem__(name, value) if value else _fake_store.pop(name, None)) or True
from app.config_manager import ConfigManager
from app.ui_onboarding import OnboardingWizard

app = QApplication([])

# hotkey helpers
assert hotkeys.combo_from_tokens({"win", "ctrl"}) == "<ctrl>+<win>"
assert hotkeys.combo_from_tokens({"f8"}) == "<f8>"
assert hotkeys.is_safe_combo({"ctrl", "win"}) and hotkeys.is_safe_combo({"f9"})
assert not hotkeys.is_safe_combo({"a"}) and not hotkeys.is_safe_combo({"space"})

# every style renders every status without error; save a contact sheet if asked
statuses = ["Idle", "Paused", "Listening", "Transcribing", "Processing", "Pasted", "Error", "Cancelled"]
img = QImage(len(statuses) * 80, len(pill_styles.STYLES) * 34, QImage.Format_ARGB32)
img.fill(QColor("#7A7A80"))
painter = QPainter(img)
for r, style in enumerate(pill_styles.STYLES.values()):
    for c, status in enumerate(statuses):
        pill_styles.paint(painter, QRectF(c * 80, r * 34, 80, 34), style, status, 0.35, 5.0, bottom_margin=8)
painter.end()
if os.environ.get("WAKY_SHEET"):
    img.save(os.environ["WAKY_SHEET"])

# wizard: cloud path writes key, hotkey, style
cfg = ConfigManager(Path(tempfile.mkdtemp()))
applied = []
finished = []
w = OnboardingWizard(cfg)
w.settings_applied.connect(lambda: applied.append(1))
w.finished_setup.connect(finished.append)
assert w.index == 0
w._next()                      # welcome -> engine
w._next()                      # engine -> key (cloud)
assert w.index == 2 and not w.next_button.isEnabled(), "key page needs a key"
w.key_edit.setText("gsk_unit_test_key")
assert w.next_button.isEnabled()
w._next()                      # key -> hotkey (applies)
assert cfg.settings["providers"]["groq"]["api_key"] == "gsk_unit_test_key"
assert cfg.settings["transcription"]["backend"] == "auto_fallback"
w.hotkey_edit.setText("<ctrl>+<alt>")
w._next()                      # hotkey -> style
w._pick_style("line")
w._next()                      # style -> try
assert cfg.settings["hotkeys"]["push_to_talk"] == "<ctrl>+<alt>"
assert cfg.settings["floating_bar"]["style"] == "line"
w._next()                      # check -> try
w._next()                      # try -> done
assert w.next_button.text() == "Start using Waky"
w._next()
assert cfg.settings["general"]["onboarding_done"] is True and finished == [False] and len(applied) >= 3

# wizard: local path skips the key page
_fake_store.clear()  # fresh machine
cfg2 = ConfigManager(Path(tempfile.mkdtemp()))
w2 = OnboardingWizard(cfg2)
w2._next()
w2._pick_engine(False)
w2._next()
assert w2.index == 3, "local mode must skip the key page"
w2._next(); w2._next(); w2._next(); w2._next(); w2._next()
assert cfg2.settings["transcription"]["backend"] == "local" and cfg2.settings["general"]["onboarding_done"]
assert not cfg2.settings["providers"]["groq"]["api_key"]
print("phase 4 checks passed")
