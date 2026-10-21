"""macOS-style design system for Waky's desktop UI: palettes, stylesheet, fonts.

Every widget colour is set explicitly here, so nothing depends on the Windows light/dark theme.
Rules the whole app follows: 13 px type, small radii (6 on controls, 10 on grouped lists), hairline separators,
neutral surfaces, and one accent colour used sparingly.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from string import Template

from PySide6.QtCore import QObject, QRectF, Qt, Signal
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
    field: str
    text: str
    text2: str
    text3: str
    sep: str
    border: str
    hover: str
    accent: str
    accent_fill: str   # translucent accent for tinted selections
    accent_fill_hover: str
    danger: str
    success: str
    shadow: str
    is_dark: bool


LIGHT = Palette(
    "light", bg="#F3F3F6", surface="#FFFFFF", surface2="#F1F1F4", sidebar="#EBEBF0", field="#FFFFFF", text="#1D1D1F", text2="#68686F",
    text3="#9A9AA1", sep="#E6E6EB", border="#D3D3D9", hover="rgba(0,0,0,0.055)", accent=BLUE, accent_fill="rgba(46,98,255,0.10)",
    accent_fill_hover="rgba(46,98,255,0.18)", danger="#E5342B", success="#2FB457", shadow="rgba(0,0,0,0.08)", is_dark=False,
)
DARK = Palette(
    "dark", bg="#1E1E21", surface="#2A2A2E", surface2="#35353A", sidebar="#252528", field="#1F1F22", text="#F5F5F7", text2="#A8A8AF",
    text3="#76767D", sep="#3A3A3F", border="#4A4A50", hover="rgba(255,255,255,0.07)", accent="#4A78FF", accent_fill="rgba(74,120,255,0.20)",
    accent_fill_hover="rgba(74,120,255,0.32)", danger="#FF5A50", success="#32C75E", shadow="rgba(0,0,0,0.6)", is_dark=True,
)

FONT_FAMILIES = ["Segoe UI Variable Text", "Segoe UI Variable", "Segoe UI", "Inter", "Arial"]
_current = LIGHT


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
        path = folder / f"{p.name}_v2_{name}.png"
        img.save(str(path))
        out[name] = path.as_posix()

    def chevron(qp: QPainter) -> None:
        pen = QPen(QColor(p.text2), 4.5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        qp.setPen(pen)
        path = QPainterPath()
        path.moveTo(15, 19)
        path.lineTo(24, 28)
        path.lineTo(33, 19)
        qp.drawPath(path)

    def radio_off(qp: QPainter) -> None:
        qp.setPen(QPen(QColor(p.border), 3.4))
        qp.setBrush(QColor(p.field))
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
QLabel#pageTitle { font-size: 22px; font-weight: 700; color: $text; }
QLabel#pageSubtitle, QLabel#sub, QLabel#settingsSubtitle { color: $text2; }
QLabel#settingsTitle { font-size: 15px; font-weight: 700; }
QLabel#title { font-size: 26px; font-weight: 700; color: $text; }
QLabel#caption { color: $text2; font-size: 12px; }
QLabel#rowLabel { color: $text; font-size: 13px; }
QLabel#ok { color: $success; font-weight: 600; }
QLabel#bad { color: $danger; font-weight: 600; }
QLabel#section { color: $text2; font-size: 12px; font-weight: 600; }

QFrame#group { background: $surface; border: 1px solid $sep; border-radius: 10px; }
QFrame#sideFrame { background: $sidebar; border: none; border-right: 1px solid $sep; }
QFrame#styleCard { background: $surface; border: 1px solid $border; border-radius: 10px; }
QFrame#styleCard[selected="true"] { border: 2px solid $accent; background: $surface; }
QFrame#styleCard:hover { border-color: $text3; }
QFrame#footer { background: $bg; border: none; border-top: 1px solid $sep; }
QFrame#miniScreen { background: $surface2; border: 1px solid $border; border-radius: 6px; }
QPushButton#anchor { background: $border; border: none; border-radius: 4px; padding: 0; min-height: 0; }
QPushButton#anchor:hover { background: $text3; }
QPushButton#anchor:checked { background: $accent; }
QPushButton#anchor:disabled { background: $sep; }
QFrame#hairline { background: $sep; border: none; max-height: 1px; min-height: 1px; }
QFrame#segment { background: $surface2; border: 1px solid $sep; border-radius: 8px; }

QPushButton {
  background: $surface; color: $text; border: 1px solid $border; border-radius: 6px;
  padding: 3px 14px; font-weight: 500; min-height: 22px;
}
QPushButton:hover { background: $surface2; }
QPushButton:pressed { background: $sep; }
QPushButton:disabled { background: $surface2; color: $text3; border-color: $sep; }
QPushButton#primary { background: $accent; color: #FFFFFF; border: 1px solid $accent_press; font-weight: 600; }
QPushButton#primary:hover { background: $accent_hover; }
QPushButton#primary:pressed { background: $accent_press; }
QPushButton#primary:disabled { background: $surface2; color: $text3; border-color: $sep; }
QPushButton#plain { background: transparent; color: $text2; border: 1px solid transparent; }
QPushButton#plain:hover { color: $text; background: $hover; }
QPushButton#link { background: transparent; color: $accent; border: none; padding: 2px 4px; }
QPushButton#link:hover { text-decoration: underline; }
QPushButton#danger { background: transparent; color: $danger; border: 1px solid transparent; }
QPushButton#danger:hover { background: rgba(229,52,43,0.12); }
QPushButton#swatch { border: 2px solid $border; border-radius: 11px; min-width: 22px; max-width: 22px; min-height: 22px; max-height: 22px; padding: 0; }
QPushButton#swatch:checked { border: 2px solid $text; }
QPushButton#gear { background: rgba(20,20,24,0.92); color: #FFFFFF; border: 1px solid #3A3C45; border-radius: 9px; padding: 0; }

QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox {
  background: $field; color: $text; border: 1px solid $border; border-radius: 6px; padding: 3px 8px;
  selection-background-color: $accent; selection-color: #FFFFFF;
}
QLineEdit, QSpinBox, QDoubleSpinBox { min-height: 22px; }
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QSpinBox:focus { border: 1px solid $accent; }
QLineEdit:read-only { background: $field; }
QLineEdit#hotkey { font-weight: 600; background: $surface2; border-radius: 6px; qproperty-alignment: AlignCenter; }
QLineEdit#hotkey:hover { border-color: $text3; }
QLineEdit#hotkey:focus { border: 1px solid $accent; }
QLineEdit#hotkeyBig { font-size: 20px; font-weight: 600; padding: 10px 14px; background: $surface; border-radius: 10px; qproperty-alignment: AlignCenter; }
QLineEdit#hotkeyBig:focus { border: 2px solid $accent; }
QSpinBox::up-button, QSpinBox::down-button { width: 0; }

QComboBox {
  background: $surface; color: $text; border: 1px solid $border; border-radius: 6px; padding: 2px 8px; min-height: 22px;
}
QComboBox:hover { background: $surface2; }
QComboBox:focus, QComboBox:on { border: 1px solid $accent; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox::down-arrow { image: url("$chevron"); width: 10px; height: 10px; }
QComboBox QAbstractItemView {
  background: $surface; color: $text; border: 1px solid $border; border-radius: 6px; padding: 4px;
  selection-background-color: $accent; selection-color: #FFFFFF; outline: 0;
}

QListWidget { background: $surface; color: $text; border: 1px solid $sep; border-radius: 8px; padding: 4px; }
QListWidget::item { padding: 5px 8px; border-radius: 5px; }
QListWidget::item:selected { background: $accent; color: #FFFFFF; }
QListWidget::item:hover:!selected { background: $hover; }
QListWidget#sidebar { background: transparent; border: none; padding: 0; }
QListWidget#sidebar::item { padding: 3px 6px; margin: 1px 0; border-radius: 6px; color: $text; }
QListWidget#sidebar::item:selected { background: $accent; color: #FFFFFF; }
QListWidget#sidebar::item:hover:!selected { background: $hover; }
QListWidget#steps { background: transparent; border: none; padding: 0; }
QListWidget#steps::item { padding: 4px 6px; margin: 1px 0; border-radius: 6px; color: $text2; }
QListWidget#steps::item:selected { background: $hover; color: $text; }

QRadioButton { color: $text; spacing: 8px; padding: 3px 2px; background: transparent; }
QRadioButton::indicator { width: 16px; height: 16px; }
QRadioButton::indicator:unchecked { image: url("$radio_off"); }
QRadioButton::indicator:checked { image: url("$radio_on"); }

QSlider::groove:horizontal { height: 4px; border-radius: 2px; background: $border; }
QSlider::sub-page:horizontal { background: $accent; border-radius: 2px; }
QSlider::handle:horizontal { background: #FFFFFF; border: 1px solid rgba(0,0,0,0.25); width: 16px; height: 16px; margin: -7px 0; border-radius: 9px; }

QScrollArea { border: none; background: transparent; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px 1px; }
QScrollBar::handle:vertical { background: $border; border-radius: 4px; min-height: 36px; }
QScrollBar::handle:vertical:hover { background: $text3; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 1px 2px; }
QScrollBar::handle:horizontal { background: $border; border-radius: 4px; min-width: 36px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }

QToolTip { background: $surface; color: $text; border: 1px solid $border; border-radius: 6px; padding: 4px 8px; }
QMenu { background: $surface; color: $text; border: 1px solid $border; border-radius: 8px; padding: 5px; }
QMenu::item { padding: 5px 22px 5px 12px; border-radius: 5px; }
QMenu::item:selected { background: $accent; color: #FFFFFF; }
QMenu::item:disabled { color: $text3; }
QMenu::separator { height: 1px; background: $sep; margin: 4px 8px; }
QProgressBar { background: $sep; border: none; border-radius: 3px; max-height: 6px; min-height: 6px; text-align: center; color: transparent; }
QProgressBar::chunk { background: $accent; border-radius: 3px; }
""")


def build_qss(p: Palette) -> str:
    assets = _render_assets(p, DATA_DIR / "cache" / "ui")
    accent = QColor(p.accent)
    return QSS.substitute(
        bg=p.bg, surface=p.surface, surface2=p.surface2, sidebar=p.sidebar, field=p.field, text=p.text, text2=p.text2, text3=p.text3,
        sep=p.sep, border=p.border, hover=p.hover, accent=p.accent, danger=p.danger, success=p.success,
        accent_hover=accent.lighter(110).name(), accent_press=accent.darker(112).name(),
        chevron=assets["chevron"], radio_off=assets["radio_off"], radio_on=assets["radio_on"],
    )


class ThemeManager(QObject):
    """Applies the palette app-wide and follows the Windows light/dark setting when appearance == 'system'."""

    changed = Signal()

    def __init__(self, app, appearance: str = "light") -> None:
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
            return DARK if scheme == Qt.ColorScheme.Dark else LIGHT
        except Exception:
            return LIGHT

    def apply(self, appearance: str | None = None) -> None:
        global _current
        if appearance:
            self.appearance = appearance
        _current = self.resolve(self.appearance)
        self.app.setStyleSheet(build_qss(_current))
        self.changed.emit()
