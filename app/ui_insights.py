"""Insights page widgets: stat tiles, streak heatmap, app usage bars and the voice profile."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from . import ios_theme
from .ios_widgets import mix, section_label
from .stats import Stats


def _fmt(n: int) -> str:
    return f"{int(n):,}"


class Tile(QFrame):
    """A rounded card with a small caption, a big value and an optional sub line."""

    def __init__(self, caption: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("group")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(2)
        self.caption = QLabel(caption.upper())
        self.caption.setObjectName("caption")
        self.value = QLabel("0")
        self.value.setStyleSheet("font-size:26px;font-weight:700;background:transparent;")
        self.sub = QLabel("")
        self.sub.setObjectName("caption")
        self.sub.setWordWrap(True)
        self.row = QHBoxLayout()
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.addWidget(self.value)
        self.row.addStretch()
        lay.addWidget(self.caption)
        lay.addLayout(self.row)
        lay.addWidget(self.sub)
        lay.addStretch()
        self.setMinimumHeight(128)

    def set(self, value: str, sub: str = "") -> None:
        self.value.setText(value)
        self.sub.setText(sub)
        self.sub.setVisible(bool(sub))


class SpeedDial(QWidget):
    """Half-ring gauge for words per minute."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.wpm = 0
        self.setFixedSize(96, 56)

    def set(self, wpm: int) -> None:
        self.wpm = wpm
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = ios_theme.current()
        rect = QRectF(8, 8, 80, 80)
        pen = QPen(QColor(pal.sep), 8, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 180 * 16, -180 * 16)
        pen.setColor(QColor(pal.accent))
        p.setPen(pen)
        frac = max(0.0, min(1.0, self.wpm / 200))
        if frac > 0:
            p.drawArc(rect, 180 * 16, int(-180 * 16 * frac))
        p.end()


class Heatmap(QWidget):
    """Weeks as columns, Monday at the top. Brighter squares are busier days."""

    CELL, GAP = 16, 4

    def __init__(self, weeks: int = 30, parent=None) -> None:
        super().__init__(parent)
        self.weeks = weeks
        self.grid: list[list[tuple[date, int]]] = []
        self.setFixedHeight(7 * (self.CELL + self.GAP) + 4)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set(self, grid: list[list[tuple[date, int]]]) -> None:
        self.grid = grid
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        pal = ios_theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        busiest = max((n for col in self.grid for _d, n in col), default=0) or 1
        empty, strong = QColor(pal.sep), QColor(pal.accent)
        step = self.CELL + self.GAP
        offset = 0
        p.setPen(Qt.NoPen)
        for x, col in enumerate(self.grid):
            for y, (_day, count) in enumerate(col):
                if count < 0:
                    continue
                color = empty if count == 0 else mix(empty, strong, 0.35 + 0.65 * min(1.0, count / busiest))
                p.setBrush(color)
                p.drawRoundedRect(QRectF(offset + x * step, y * step + 2, self.CELL, self.CELL), 4, 4)
        p.end()


class Bar(QWidget):
    """One horizontal usage bar: label, filled track and a percent."""

    def __init__(self, label: str, count: int, percent: float, parent=None) -> None:
        super().__init__(parent)
        self.label, self.count, self.percent = label, count, percent
        self.setFixedHeight(26)

    def paintEvent(self, _event) -> None:  # noqa: N802
        pal = ios_theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        font = QFont(self.font())
        font.setPointSizeF(9.5)
        p.setFont(font)
        p.setPen(QColor(pal.text))
        p.drawText(QRectF(0, 0, 96, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self.label)
        right = 118
        track = QRectF(100, 8, self.width() - 100 - right, 10)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(pal.sep))
        p.drawRoundedRect(track, 5, 5)
        p.setBrush(QColor(pal.accent))
        fill = QRectF(track.x(), track.y(), max(10.0, track.width() * self.percent / 100), track.height())
        p.drawRoundedRect(fill, 5, 5)
        p.setPen(QColor(pal.text2))
        p.drawText(QRectF(self.width() - right + 8, 0, right - 8, self.height()), Qt.AlignVCenter | Qt.AlignRight, f"{self.percent:.0f}%  ·  {_fmt(self.count)}")
        p.end()


class VoiceCard(QFrame):
    """A quote-style line with a small caption underneath, like a trading card."""

    def __init__(self, caption: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("group")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(4)
        self.quote = QLabel("")
        self.quote.setWordWrap(True)
        self.quote.setStyleSheet("font-size:20px;font-style:italic;font-weight:500;background:transparent;")
        self.caption = QLabel(caption.upper())
        self.caption.setObjectName("caption")
        lay.addWidget(self.quote)
        lay.addWidget(self.caption)

    def set(self, text: str) -> None:
        self.quote.setText(text)


class InsightsPage(QWidget):
    reset_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.wpm_tile = Tile("Words per minute")
        self.dial = SpeedDial()
        self.wpm_tile.row.addWidget(self.dial)
        self.fix_tile = Tile("Fixes made by Waky")
        self.words_tile = Tile("Total words dictated")
        for t in (self.wpm_tile, self.fix_tile, self.words_tile):
            row.addWidget(t, 1)
        lay.addLayout(row)

        lay.addWidget(section_label("Streak"))
        self.streak_card = QFrame()
        self.streak_card.setObjectName("group")
        sl = QVBoxLayout(self.streak_card)
        sl.setContentsMargins(16, 14, 16, 14)
        head = QHBoxLayout()
        self.streak_title = QLabel("")
        self.streak_title.setStyleSheet("font-size:17px;font-weight:700;background:transparent;")
        self.streak_best = QLabel("")
        self.streak_best.setObjectName("caption")
        head.addWidget(self.streak_title)
        head.addStretch()
        head.addWidget(self.streak_best)
        sl.addLayout(head)
        self.heatmap = Heatmap()
        sl.addWidget(self.heatmap)
        lay.addWidget(self.streak_card)

        lay.addWidget(section_label("Where you dictate"))
        self.apps_card = QFrame()
        self.apps_card.setObjectName("group")
        self.apps_lay = QVBoxLayout(self.apps_card)
        self.apps_lay.setContentsMargins(16, 12, 16, 12)
        self.apps_lay.setSpacing(0)
        lay.addWidget(self.apps_card)

        lay.addWidget(section_label("Your voice"))
        self.catchphrase = VoiceCard("Catchphrase")
        voice = QHBoxLayout()
        voice.setSpacing(10)
        self.top_word = VoiceCard("Most used word")
        self.top_fix = VoiceCard("Most corrected word")
        voice.addWidget(self.top_word, 1)
        voice.addWidget(self.top_fix, 1)
        lay.addWidget(self.catchphrase)
        lay.addLayout(voice)

        self.phrases_note = QLabel("")
        self.phrases_note.setObjectName("caption")
        self.phrases_note.setWordWrap(True)
        lay.addWidget(self.phrases_note)

        foot = QHBoxLayout()
        self.privacy_note = QLabel("Counts only, stored on this PC. No audio and no full text.")
        self.privacy_note.setObjectName("caption")
        self.reset_btn = QPushButton("Reset insights")
        self.reset_btn.setObjectName("danger")
        self.reset_btn.clicked.connect(self.reset_requested.emit)
        foot.addWidget(self.privacy_note, 1)
        foot.addWidget(self.reset_btn)
        lay.addLayout(foot)

    def refresh(self, stats: Stats) -> None:
        d = stats.data
        wpm = stats.wpm()
        self.wpm_tile.set(str(wpm) if wpm else "-", "Dictate a bit more to measure your speed." if not wpm else (f"Personal best {d['best_wpm']} in one go" if d["best_wpm"] else ""))
        self.dial.set(wpm)
        self.fix_tile.set(_fmt(d["fixes"]), f"{_fmt(d['taught'])} taught from History" if d["taught"] else "Fillers and wrong words cleaned up")
        books = stats.books_written()
        self.words_tile.set(_fmt(d["total_words"]), f"{_fmt(d['dictations'])} dictations" + (f"  ·  {books:.1f} books" if books >= 0.1 else ""))

        current, longest = stats.streak()
        self.streak_title.setText(f"{current} day streak" if current else "No streak yet")
        self.streak_best.setText(f"Longest {longest}" if longest else "Dictate today to start one")
        self.heatmap.set(stats.heatmap(30))

        while self.apps_lay.count():
            item = self.apps_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rows = stats.app_share()
        for name, count, pct in rows:
            self.apps_lay.addWidget(Bar(name, count, pct))
        if not rows:
            empty = QLabel("Your apps will show up here after a few dictations.")
            empty.setObjectName("caption")
            self.apps_lay.addWidget(empty)

        phrase, word, fix = stats.top_phrase(), stats.top_word(), stats.top_corrected()
        self.catchphrase.set(f"“{phrase[0].capitalize()}”" if phrase else "Still listening…")
        self.top_word.set(f"“{word[0]}”" if word else "-")
        self.top_fix.set(f"“{fix[0]}”" if fix else "-")
        ranked = stats.top_phrases(5)
        self.phrases_note.setText("Also on repeat:  " + "   ·   ".join(f"{p} ×{n}" for p, n in ranked[1:]) if len(ranked) > 1 else "")
