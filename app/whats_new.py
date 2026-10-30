"""What's new: shown once after an update, and any time from Settings > Updates."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from . import __version__

# Newest first. The first entry is the one the dialog leads with.
RELEASES = (
    ("1.4", "Insights and learning from your fixes", (
        "Insights page in Settings: words per minute, fixes made by Waky, total words dictated, your day streak, where you dictate, and the phrases you say most.",
        "Learn from my fix: correct a dictated sentence, select it and press Ctrl + Alt + L. Waky compares it with what it heard and remembers what you meant, so the same word is right next time.",
        "Hover the pill and a Settings button slides out. Click it to open Settings straight away.",
        "Opening Waky again from the Start menu or a shortcut now opens Settings instead of saying it is already running.",
        "Fixed: YouTube and music no longer drop to call-quality sound when you dictate with Bluetooth earbuds. Waky now uses your laptop or wired microphone instead of the earbuds' microphone, and only opens it while you hold the key.",
        "The Waky logo is back everywhere: taskbar, tray and installer.",
        "Insights keeps counts only on your PC. No audio and no full text, and you can reset it any time.",
    )),
    ("1.3", "Your words stay yours", (
        "Dictation keeps your own words instead of rewriting them.",
        "History tab: see what Waky heard and wrote, fix a word and press Teach Waky.",
        "A snappier start, so the first dictation is ready sooner.",
        "New setup assistant with a calmer look.",
    )),
    ("1.2", "Per-app profiles", (
        "App Profiles: casual in chat, polished in email, literal in code.",
        "Double-tap your dictation key to lock hands-free listening.",
    )),
    ("1.1", "Updates and mouse hotkeys", (
        "Update checker with one-click install and a verified download.",
        "Use your mouse's middle or side buttons as hotkeys.",
        "Choose when the pill shows: always, only while dictating, or hidden.",
    )),
)


def notes_for_current() -> tuple[str, str, tuple[str, ...]]:
    return RELEASES[0]


class WhatsNewDialog(QDialog):
    open_insights = Signal()

    def __init__(self, parent=None, show_insights_button: bool = True) -> None:
        super().__init__(parent)
        self.setWindowTitle("What's new in Waky")
        self.setMinimumSize(560, 520)
        self.resize(600, 640)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 26, 28, 20)
        outer.setSpacing(10)

        small = QLabel(f"UPDATED TO WAKY {__version__}")
        small.setObjectName("caption")
        title = QLabel("What's new")
        title.setObjectName("settingsTitle")
        title.setStyleSheet("font-size:26px;font-weight:700;")
        outer.addWidget(small)
        outer.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        body = QWidget()
        lay = QVBoxLayout(body)
        lay.setContentsMargins(0, 8, 8, 8)
        lay.setSpacing(6)
        for index, (version, headline, items) in enumerate(RELEASES):
            head = QLabel(f"Waky {version}" + ("  ·  new" if index == 0 else ""))
            head.setObjectName("section")
            head.setContentsMargins(0, 12 if index else 0, 0, 0)
            sub = QLabel(headline)
            sub.setStyleSheet("font-size:16px;font-weight:600;")
            lay.addWidget(head)
            lay.addWidget(sub)
            card = QFrame()
            card.setObjectName("group")
            cl = QVBoxLayout(card)
            cl.setContentsMargins(16, 12, 16, 12)
            cl.setSpacing(8)
            for text in items:
                row = QLabel("•  " + text)
                row.setWordWrap(True)
                cl.addWidget(row)
            lay.addWidget(card)
        lay.addStretch()
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        if show_insights_button:
            insights = QPushButton("Open Insights")
            insights.clicked.connect(lambda: (self.open_insights.emit(), self.accept()))
            buttons.addWidget(insights)
        done = QPushButton("Got it")
        done.setObjectName("primary")
        done.setDefault(True)
        done.clicked.connect(self.accept)
        buttons.addWidget(done)
        outer.addLayout(buttons)
