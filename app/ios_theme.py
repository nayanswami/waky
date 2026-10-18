"""iOS-style design system for Waky's desktop UI: palettes, stylesheet, fonts.

Every widget colour is set explicitly here, so nothing depends on the Windows light/dark theme
(the old UI had white text on white buttons when Windows was in dark mode).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Template

from PySide6.QtCore import QObject, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QGuiApplication, QImage, QPainter, QPainterPath, QPen

from .utils import DATA_DIR

BLUE = "#2E62FF"  # Waky logo blue


@dataclass(frozen=True)
class Palette:
    name: str
    bg: str
    surface: str
    surface2: str
    sidebar: str
    text: str
    text2: str
    text3: str
    sep: str
    accent: str
    accent_fill: str   # translucent accent for tinted buttons / selected rows
    accent_fill_hover: str
    danger: str
    success: str
    shadow: str
    is_dark: bool


LIGHT = Palette(
    "light", bg="#F2F3F7", surface="#FFFFFF", surface2="#F2F3F7", sidebar="#E9EBF1", text="#0F1115", text2="#5F6470",
    text3="#8D92A0", sep="#DADDE5", accent=BLUE, accent_fill="rgba(46,98,255,0.12)", accent_fill_hover="rgba(46,98,255,0.20)",
    danger="#E5484D", success="#1FA65A", shadow="rgba(15,17,21,0.12)", is_dark=False,
)
DARK = Palette(
    "dark", bg="#0B0C0F", surface="#17181D", surface2="#202127", sidebar="#111216", text="#F4F5F8", text2="#A3A7B3",
    text3="#6F7380", sep="#2A2C34", accent="#4A78FF", accent_fill="rgba(74,120,255,0.20)", accent_fill_hover="rgba(74,120,255,0.32)",
    danger="#FF6369", success="#3DD68C", shadow="rgba(0,0,0,0.5)", is_dark=True,
)

FONT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "Inter", "Arial"]
_current = DARK


def current() -> Palette:
    return _current


def _render_assets(p: Palette, folder: Path) -> dict[str, str]:
    """Small PNGs used by the stylesheet (chevrons, radio buttons), drawn in the palette colours."""
    folder.mkdir(parents=True, exist_ok=True)
    out: dict[str, str] = {}

    def save(name: str, draw) -> None:
        img = QImage(48, 48, QImage.Format_ARGB32)
        img.fill(Qt.transparent)
        qp = QPainter(img)
        qp.setRenderHint(QPainter.Antialiasing)
        draw(qp)
        qp.end()
        path = folder / f"{p.name}_{name}.png"
        img.save(str(path))
        out[name] = path.as_posix()

    def chevron(qp: QPainter) -> None:
        pen = QPen(QColor(p.text3), 4.5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        qp.setPen(pen)
        path = QPainterPath()
        path.moveTo(14, 19)
        path.lineTo(24, 29)
        path.lineTo(34, 19)
        qp.drawPath(path)

    def radio_off(qp: QPainter) -> None:
        qp.setPen(QPen(QColor(p.text3), 3.2))
        qp.setBrush(Qt.NoBrush)
        qp.drawEllipse(QRectF(6, 6, 36, 36))

    def radio_on(qp: QPainter) -> None:
        qp.setPen(Qt.NoPen)
        qp.setBrush(QColor(p.accent))
        qp.drawEllipse(QRectF(5, 5, 38, 38))
        qp.setBrush(QColor("#FFFFFF"))
        qp.drawEllipse(QRectF(17, 17, 14, 14))

    save("chevron", chevron)
    save("radio_off", radio_off)
    save("radio_on", radio_on)
    return out


QSS = Template(r"""
* { font-family: "Segoe UI Variable Text", "Segoe UI", sans-serif; font-size: 13px; outline: 0; }
QDialog, QMessageBox, QInputDialog, QFileDialog { background: $bg; color: $text; }
QLabel { color: $text; background: transparent; }
QLabel#pageTitle { font-size: 28px; font-weight: 700; color: $text; }
QLabel#pageSubtitle, QLabel#sub, QLabel#settingsSubtitle { color: $text2; }
QLabel#settingsTitle { font-size: 20px; font-weight: 700; }
QLabel#title { font-size: 30px; font-weight: 700; color: $text; }
QLabel#caption { color: $text3; font-size: 12px; }
QLabel#ok { color: $success; font-weight: 600; }
QLabel#bad { color: $danger; font-weight: 600; }
QLabel#section { color: $text3; font-size: 12px; font-weight: 600; }

QFrame#card { background: $surface; border: 1px solid $sep; border-radius: 18px; }
QFrame#wizardCard { background: $surface; border: 1px solid $sep; border-radius: 30px; }
QFrame#sideFrame { background: $sidebar; border: none; border-right: 1px solid $sep; }
QFrame#styleCard { background: $surface; border: 1.5px solid $sep; border-radius: 16px; }
QFrame#styleCard[selected="true"] { border: 2px solid $accent; background: $accent_fill; }
QFrame#styleCard:hover { border-color: $text3; }
QFrame#footer { background: $bg; border: none; border-top: 1px solid $sep; }
QFrame#miniScreen { background: $surface2; border: 1px solid $sep; border-radius: 10px; }
QPushButton#anchor { background: $sep; border-radius: 7px; padding: 0; min-height: 0; }
QPushButton#anchor:hover { background: $text3; }
QPushButton#anchor:checked { background: $accent; }
QPushButton#anchor:disabled { background: $surface; }
QFrame#hairline { background: $sep; border: none; max-height: 1px; min-height: 1px; }

QPushButton {
  background: $accent_fill; color: $accent; border: none; border-radius: 11px;
  padding: 9px 18px; font-weight: 600; min-height: 18px;
}
QPushButton:hover { background: $accent_fill_hover; }
QPushButton:pressed { background: $accent; color: #FFFFFF; }
QPushButton:disabled { background: $surface2; color: $text3; }
QPushButton#primary { background: $accent; color: #FFFFFF; }
QPushButton#primary:hover { background: $accent_hover; }
QPushButton#primary:pressed { background: $accent_press; }
QPushButton#primary:disabled { background: $surface2; color: $text3; }
QPushButton#plain { background: transparent; color: $text2; }
QPushButton#plain:hover { color: $text; background: $surface2; }
QPushButton#danger { background: transparent; color: $danger; }
QPushButton#danger:hover { background: rgba(229,72,77,0.14); }
QPushButton#swatch { border: 2px solid transparent; border-radius: 15px; min-width: 30px; max-width: 30px; min-height: 30px; max-height: 30px; padding: 0; }
QPushButton#swatch:checked { border: 3px solid $text; }
QPushButton#gear { background: rgba(20,20,24,0.92); color: #FFFFFF; border: 1px solid #3A3C45; border-radius: 9px; padding: 0; }

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
  background: $surface; color: $text; border: 1px solid $sep; border-radius: 11px; padding: 9px 12px;
  selection-background-color: $accent; selection-color: #FFFFFF;
}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus { border: 1.5px solid $accent; padding: 8.5px 11.5px; }
QLineEdit:read-only { background: $surface2; }
QLineEdit#hotkey { font-size: 18px; font-weight: 600; padding: 14px 16px; border-radius: 14px; qproperty-alignment: AlignCenter; }

QComboBox {
  background: $surface; color: $text; border: 1px solid $sep; border-radius: 11px; padding: 8px 12px; min-height: 18px;
}
QComboBox:hover { border-color: $text3; }
QComboBox:focus, QComboBox:on { border: 1.5px solid $accent; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox::down-arrow { image: url("$chevron"); width: 12px; height: 12px; }
QComboBox QAbstractItemView {
  background: $surface; color: $text; border: 1px solid $sep; border-radius: 12px; padding: 6px;
  selection-background-color: $accent; selection-color: #FFFFFF; outline: 0;
}

QListWidget { background: $surface; color: $text; border: 1px solid $sep; border-radius: 14px; padding: 6px; }
QListWidget::item { padding: 8px 10px; border-radius: 9px; }
QListWidget::item:selected { background: $accent; color: #FFFFFF; }
QListWidget::item:hover:!selected { background: $surface2; }
QListWidget#sidebar { background: transparent; border: none; padding: 0; }
QListWidget#sidebar::item { padding: 8px 10px; margin: 1px 0; border-radius: 10px; color: $text; font-size: 13.5px; }
QListWidget#sidebar::item:selected { background: $accent; color: #FFFFFF; }
QListWidget#sidebar::item:hover:!selected { background: $surface2; }

QRadioButton { color: $text; spacing: 10px; padding: 5px 2px; background: transparent; }
QRadioButton::indicator { width: 22px; height: 22px; }
QRadioButton::indicator:unchecked { image: url("$radio_off"); }
QRadioButton::indicator:checked { image: url("$radio_on"); }

QSlider::groove:horizontal { height: 6px; border-radius: 3px; background: $sep; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 3px; }
QSlider::handle:horizontal { background: #FFFFFF; border: 1px solid rgba(0,0,0,0.18); width: 24px; height: 24px; margin: -9px 0; border-radius: 12px; }

QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 4px 2px; }
QScrollBar::handle:vertical { background: $sep; border-radius: 4px; min-height: 36px; }
QScrollBar::handle:vertical:hover { background: $text3; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 12px; margin: 2px 4px; }
QScrollBar::handle:horizontal { background: $sep; border-radius: 4px; min-width: 36px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QToolTip { background: $surface2; color: $text; border: 1px solid $sep; border-radius: 8px; padding: 6px 9px; }
QMenu { background: $surface; color: $text; border: 1px solid $sep; border-radius: 12px; padding: 6px; }
QMenu::item { padding: 8px 22px 8px 14px; border-radius: 8px; }
QMenu::item:selected { background: $accent; color: #FFFFFF; }
QMenu::separator { height: 1px; background: $sep; margin: 5px 8px; }
QProgressBar { background: $sep; border: none; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: $accent; border-radius: 4px; }
""")


def build_qss(p: Palette) -> str:
    assets = _render_assets(p, DATA_DIR / "cache" / "ui")
    accent = QColor(p.accent)
    return QSS.substitute(
        bg=p.bg, surface=p.surface, surface2=p.surface2, sidebar=p.sidebar, text=p.text, text2=p.text2, text3=p.text3, sep=p.sep,
        accent=p.accent, accent_fill=p.accent_fill, accent_fill_hover=p.accent_fill_hover, danger=p.danger, success=p.success,
        accent_hover=accent.lighter(112).name(), accent_press=accent.darker(115).name(),
        chevron=assets["chevron"], radio_off=assets["radio_off"], radio_on=assets["radio_on"],
    )


class ThemeManager(QObject):
    """Applies the palette app-wide and follows the Windows light/dark setting when appearance == 'system'."""

    changed = Signal()

    def __init__(self, app, appearance: str = "system") -> None:
        super().__init__(app)
        self.app = app
        self.appearance = appearance
        font = QFont()
        for family in FONT_FAMILIES:
            font.setFamily(family)
            if font.exactMatch() or QFont(family).family() == family:
                break
        font.setPixelSize(13)
        app.setFont(font)
        try:
            app.styleHints().colorSchemeChanged.connect(lambda *_: self.apply(self.appearance))
        except Exception:
            pass
        self.apply(appearance)

    def resolve(self, appearance: str) -> Palette:
        if appearance == "light":
            return LIGHT
        if appearance == "dark":
            return DARK
        try:
            scheme = QGuiApplication.styleHints().colorScheme()
            return LIGHT if scheme == Qt.ColorScheme.Light else DARK
        except Exception:
            return DARK

    def apply(self, appearance: str | None = None) -> None:
        global _current
        if appearance:
            self.appearance = appearance
        _current = self.resolve(self.appearance)
        self.app.setStyleSheet(build_qss(_current))
        self.changed.emit()
