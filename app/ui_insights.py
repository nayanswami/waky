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


class HourChart(QWidget):
    """Words by hour of the day: 24 slim columns with the busiest ones in the accent colour."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.hours = [0] * 24
        self.setFixedHeight(92)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set(self, hours: list[int]) -> None:
        self.hours = hours
        self.update()

    def paintEvent(self, _event) -> None:  # noqa: N802
        pal = ios_theme.current()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        busiest = max(self.hours) or 1
        gap = 5.0
        col_w = (self.width() - gap * 23) / 24
        top, label_h = 4.0, 16.0
        track = self.height() - label_h - top
        empty, strong = QColor(pal.sep), QColor(pal.accent)
        font = QFont(self.font())
        font.setPointSizeF(8)
        p.setFont(font)
        for h, count in enumerate(self.hours):
            x = h * (col_w + gap)
            height = max(5.0, track * count / busiest) if count else 5.0
            color = empty if not count else mix(empty, strong, 0.4 + 0.6 * count / busiest)
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, top + track - height, col_w, height), min(4.0, col_w / 2), min(4.0, col_w / 2))
            if h % 6 == 0:
                p.setPen(QColor(pal.text2))
                label = "12a" if h == 0 else "6a" if h == 6 else "12p" if h == 12 else "6p"
                p.drawText(QRectF(x - 6, self.height() - label_h + 2, col_w + 12, label_h), Qt.AlignHCenter | Qt.AlignTop, label)
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
        self.saved_tile = Tile("Typing time saved")
        self.words_tile = Tile("Total words dictated")
        for t in (self.wpm_tile, self.saved_tile, self.words_tile):
            row.addWidget(t, 1)
        lay.addLayout(row)
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        self.week_tile = Tile("This week")
        self.avg_tile = Tile("Average dictation")
        self.fix_tile = Tile("Fixes made by Waky")
        for t in (self.week_tile, self.avg_tile, self.fix_tile):
            row2.addWidget(t, 1)
        lay.addLayout(row2)

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

        lay.addWidget(section_label("When you dictate"))
        self.hours_card = QFrame()
        self.hours_card.setObjectName("group")
        hl = QVBoxLayout(self.hours_card)
        hl.setContentsMargins(16, 14, 16, 12)
        self.hours_title = QLabel("")
        self.hours_title.setStyleSheet("font-size:15px;font-weight:700;background:transparent;")
        self.hours_chart = HourChart()
        hl.addWidget(self.hours_title)
        hl.addWidget(self.hours_chart)
        lay.addWidget(self.hours_card)

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
        facts = QHBoxLayout()
        facts.setSpacing(10)
        self.longest_card = VoiceCard("Longest dictation")
        self.unique_card = VoiceCard("Different words you use")
        facts.addWidget(self.longest_card, 1)
        facts.addWidget(self.unique_card, 1)
        lay.addLayout(facts)

        lay.addWidget(section_label("What Waky does for you"))
        self.summary_card = QFrame()
        self.summary_card.setObjectName("group")
        sm = QVBoxLayout(self.summary_card)
        sm.setContentsMargins(18, 14, 18, 14)
        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("font-size:13.5px;background:transparent;")
        sm.addWidget(self.summary)
        lay.addWidget(self.summary_card)

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

    WEEKDAYS = ("Mondays", "Tuesdays", "Wednesdays", "Thursdays", "Fridays", "Saturdays", "Sundays")

    @staticmethod
    def _hour_name(h: int) -> str:
        return f"{h % 12 or 12} {'AM' if h < 12 else 'PM'}"

    @staticmethod
    def _duration(minutes: float) -> str:
        if minutes < 1:
            return "under a minute"
        if minutes < 60:
            return f"{minutes:.0f} min"
        return f"{int(minutes // 60)} h {int(minutes % 60)} min"

    def refresh(self, stats: Stats) -> None:
        d = stats.data
        wpm = stats.wpm()
        self.wpm_tile.set(str(wpm) if wpm else "-", "Dictate a bit more to measure your speed." if not wpm else (f"Personal best {d['best_wpm']} in one go" if d["best_wpm"] else ""))
        self.dial.set(wpm)
        saved = stats.minutes_saved()
        self.saved_tile.set(self._duration(saved) if d["total_words"] else "-", "Compared with typing at 40 words a minute" if d["total_words"] else "")
        books = stats.books_written()
        self.words_tile.set(_fmt(d["total_words"]), f"{_fmt(d['dictations'])} dictations" + (f"  ·  {books:.1f} books" if books >= 0.1 else ""))
        self.week_tile.set(_fmt(stats.words_this_week()), f"{_fmt(stats.words_on(date.today()))} words today")
        self.avg_tile.set(f"{stats.avg_words()} words" if d["dictations"] else "-", "per dictation")
        self.fix_tile.set(_fmt(d["fixes"]), f"{_fmt(d['taught'])} words you taught it" if d["taught"] else "Fillers and wrong words cleaned up")

        current, longest = stats.streak()
        self.streak_title.setText(f"{current} day streak" if current else "No streak yet")
        self.streak_best.setText(f"Longest {longest}" if longest else "Dictate today to start one")
        self.heatmap.set(stats.heatmap(30))

        hour, weekday = stats.busiest_hour(), stats.busiest_weekday()
        if hour is None:
            self.hours_title.setText("Your busiest hours will show up here")
        else:
            self.hours_title.setText(f"Most active around {self._hour_name(hour)}" + (f", mostly on {self.WEEKDAYS[weekday]}" if weekday is not None else ""))
        self.hours_chart.set(stats.hour_totals())

        while self.apps_lay.count():
            item = self.apps_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rows = stats.named_apps()
        for name, count, pct in rows:
            self.apps_lay.addWidget(Bar(name, count, pct))
        if not rows:
            old = stats.app_share()
            for name, count, pct in old:
                self.apps_lay.addWidget(Bar(name, count, pct))
            note = QLabel("App names show up from your next dictation." if old else "Your apps will show up here after a few dictations.")
            note.setObjectName("caption")
            self.apps_lay.addWidget(note)

        phrase, word, fix = stats.top_phrase(), stats.top_word(), stats.top_corrected()
        self.catchphrase.set(f"\u201c{phrase[0].capitalize()}\u201d" if phrase else "Still listening\u2026")
        self.top_word.set(f"\u201c{word[0]}\u201d" if word else "-")
        self.top_fix.set(f"\u201c{fix[0]}\u201d" if fix else "-")
        self.longest_card.set(f"{_fmt(d.get('longest', 0))} words" if d.get("longest") else "-")
        self.unique_card.set(_fmt(stats.unique_words()) if stats.unique_words() else "-")
        ranked = stats.top_phrases(5)
        self.phrases_note.setText("Also on repeat:  " + "   \u00b7   ".join(f"{p} \u00d7{n}" for p, n in ranked[1:]) if len(ranked) > 1 else "")

        if d["dictations"]:
            top = rows[0][0] if rows else None
            bits = [f"You have dictated {_fmt(d['total_words'])} words across {_fmt(d['dictations'])} dictations, about {self._duration(saved)} of typing saved."]
            if d["fixes"]:
                bits.append(f"Waky cleaned up {_fmt(d['fixes'])} fillers and wrong words so you did not have to.")
            if d["taught"]:
                bits.append(f"It has learned {_fmt(d['taught'])} of your own words.")
            if top:
                bits.append(f"You use it most in {top}.")
            self.summary.setText("  ".join(bits))
        else:
            self.summary.setText("Dictate a few times and Waky will show what it saves you here.")
