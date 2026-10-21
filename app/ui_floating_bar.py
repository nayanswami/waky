from __future__ import annotations

import time

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QCursor, QPainter
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from . import pill_styles

VISIBILITY_MODES = (
    ("always", "Always show"),
    ("active", "Only while dictating"),
    ("hidden", "Always hidden"),
)


ANCHORS = {
    "top_left": ("left", "top"), "top_center": ("center", "top"), "top_right": ("right", "top"),
    "middle_left": ("left", "middle"), "middle_right": ("right", "middle"),
    "bottom_left": ("left", "bottom"), "bottom_center": ("center", "bottom"), "bottom_right": ("right", "bottom"),
}


class FloatingBar(QWidget):
    settings_requested = Signal()
    mic_test_requested = Signal()
    pause_requested = Signal()
    position_changed = Signal(int, int)

    BOTTOM_MARGIN = 4

    def __init__(self, settings: dict, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.status_name = "Idle"
        self.status_started_at = time.monotonic()
        self.drag_offset: QPoint | None = None
        self.hovered = False
        self.controls_visible = False
        self.animation_phase = 0.0
        self._expand = 0.0   # 0 idle .. 1 active, driven by a spring so the pill pops open
        self._vel = 0.0
        self.pill_style = pill_styles.get_style(None)
        self.accent = pill_styles.DEFAULT_ACCENT
        self.scale_factor = 1.0
        self._alpha = 1.0           # fade level for the visibility modes
        self._linger_until = 0.0    # keep the pill up briefly after a result so it never blinks
        self.setWindowTitle("Waky")
        self.setToolTip("")
        self._apply_window_flags()
        self._read_look()
        self._apply_size()
        self._place_from_settings()

        self.animation = QTimer(self)
        self.animation.timeout.connect(self._tick)
        self.animation.start(16)

        self.keep_on_top_timer = QTimer(self)
        self.keep_on_top_timer.timeout.connect(self.keep_on_top)
        self.keep_on_top_timer.start(1500)

    # ---------- look ----------
    def _read_look(self) -> None:
        fb = self.settings.get("floating_bar", {})
        self.pill_style = pill_styles.get_style(fb.get("style"))
        self.accent = str(fb.get("accent") or pill_styles.DEFAULT_ACCENT)
        try:
            self.scale_factor = max(0.5, min(2.5, float(fb.get("size", 100)) / 100.0))
        except (TypeError, ValueError):
            self.scale_factor = 1.0

    def _apply_size(self) -> None:
        w = int(self.pill_style.active_size[0] * self.scale_factor + 34)
        h = int(self.pill_style.active_size[1] * self.scale_factor + self.BOTTOM_MARGIN * self.scale_factor + 14)
        self.setFixedSize(max(w, 70), max(h, 34))

    def apply_look(self, key: str | None = None) -> None:
        """Re-read style, accent and size from settings (or preview `key`) and give the pill a spring kick."""
        self._read_look()
        if key:
            self.pill_style = pill_styles.get_style(key)
        self._apply_size()
        self.ensure_on_screen(reset=False)
        self._vel += 3.2
        self.update()

    def apply_style(self, key: str | None = None) -> None:  # older call sites
        self.apply_look(key)

    def _apply_window_flags(self) -> None:
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.WindowDoesNotAcceptFocus
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)

    # ---------- visibility: always / only while dictating / hidden ----------
    def visibility_mode(self) -> str:
        fb = self.settings.get("floating_bar", {})
        mode = fb.get("visibility")
        if mode not in dict(VISIBILITY_MODES):
            mode = "hidden" if fb.get("hidden") else "always"
        return mode

    def _visibility_target(self) -> float:
        mode = self.visibility_mode()
        if mode == "hidden":
            return 0.0
        if mode == "active":
            busy = self._target() == 1.0 or time.monotonic() < self._linger_until
            return 1.0 if busy else 0.0
        return 1.0

    def present(self) -> None:
        """Snap to the right visibility for the current mode (used on start and after settings change)."""
        self._alpha = self._visibility_target()
        if self._alpha > 0:
            self.show()
            self.raise_()
        else:
            self.hide()
        self.update()

    # ---------- position ----------
    def _place_from_settings(self) -> None:
        pos = self.settings.get("floating_bar", {})
        saved = pos.get("position") if isinstance(pos.get("position"), dict) else {}
        self.ensure_on_screen(saved.get("x", pos.get("x")), saved.get("y", pos.get("y")))

    def keep_on_top(self) -> None:
        if self.isVisible():
            self.raise_()

    def _anchor_point(self, geo) -> tuple[int, int]:
        fb = self.settings.get("floating_bar", {})
        h_anchor, v_anchor = ANCHORS.get(fb.get("anchor", "bottom_center"), ANCHORS["bottom_center"])
        margin = int(fb.get("margin", 40) or 0)
        x = {"left": geo.x() + margin, "center": geo.x() + (geo.width() - self.width()) // 2, "right": geo.x() + geo.width() - self.width() - margin}[h_anchor]
        y = {"top": geo.y() + margin, "middle": geo.y() + (geo.height() - self.height()) // 2, "bottom": geo.y() + geo.height() - self.height() - margin}[v_anchor]
        return x, y

    def ensure_on_screen(self, x: int | None = None, y: int | None = None, reset: bool = False, logger=None) -> None:
        """Place the bar at the chosen preset anchor every launch, or at the remembered spot if the user chose that."""
        primary = QApplication.primaryScreen()
        screens = QApplication.screens()
        mode = self.settings.get("floating_bar", {}).get("position_mode", "preset")

        def screen_for(px: int, py: int):
            rect = QRectF(px, py, self.width(), self.height()).toRect()
            return next((s for s in screens if s.availableGeometry().contains(rect)), None)

        use_saved = mode == "remember" and not reset and x is not None and y is not None
        saved_screen = screen_for(int(x), int(y)) if use_saved else None
        screen = saved_screen or primary or QApplication.screenAt(QCursor.pos())
        geo = screen.availableGeometry() if screen else self.geometry()
        if use_saved and saved_screen:
            tx, ty = int(x), int(y)
        else:
            tx, ty = self._anchor_point(geo)
            if use_saved and logger:
                logger.info("[FLOATING_BAR] saved position is off-screen, using the preset anchor")
        tx = max(geo.x(), min(tx, geo.x() + geo.width() - self.width()))
        ty = max(geo.y(), min(ty, geo.y() + geo.height() - self.height()))
        self.move(tx, ty)
        if logger:
            logger.info("[FLOATING_BAR] mode=%s screen=%s position=%s,%s", mode, screen.name() if screen else "unknown", tx, ty)

    # ---------- status / motion ----------
    def set_status(self, status: str) -> None:
        if status != self.status_name:
            self.status_started_at = time.monotonic()
            self.animation_phase = 0.0
        self.status_name = status
        if status != "Idle":
            self._linger_until = time.monotonic() + 1.1
        self.update()
        self.keep_on_top()
        if status in ("Pasted", "Copied"):
            QTimer.singleShot(450, lambda: self.set_status("Idle"))

    def _target(self) -> float:
        return 0.0 if pill_styles.is_idle_state(pill_styles.state_for(self.status_name, 99.0)) else 1.0

    def _tick(self) -> None:
        dt = 0.016
        target = self._target()
        accel = 300.0 * (target - self._expand) - 24.0 * self._vel   # slightly under-damped spring
        self._vel += accel * dt
        self._expand += self._vel * dt
        moving = abs(target - self._expand) > 0.002 or abs(self._vel) > 0.02
        if not moving:
            self._expand, self._vel = target, 0.0
        self.animation_phase = (self.animation_phase + 0.016 * 1.1) % 1.0
        goal = self._visibility_target()
        fading = abs(goal - self._alpha) > 0.001
        if fading:
            step = dt / (0.14 if goal > self._alpha else 0.30)
            self._alpha = min(goal, self._alpha + step) if goal > self._alpha else max(goal, self._alpha - step)
        if self._alpha > 0.001 and not self.isVisible():
            self.show()
            self.raise_()
        elif self._alpha <= 0.001 and self.isVisible():
            self.hide()
            return
        if fading or moving or target == 1.0 or self.status_name in ("Pasted", "Copied", "Error", "Cancelled"):
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        try:
            a = max(0.0, min(1.0, self._alpha))
            painter.setOpacity(a * a * (3 - 2 * a))
            pill_styles.paint(
                painter, QRectF(0, 0, self.width(), self.height()), self.pill_style, self.status_name, self.animation_phase,
                time.monotonic() - self.status_started_at, self.BOTTOM_MARGIN, self.scale_factor, self.accent, self._expand,
            )
        finally:
            if painter.isActive():
                painter.end()

    # ---------- Shift+click opens settings, Alt+drag moves ----------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and bool(event.modifiers() & Qt.ShiftModifier):
            self.settings_requested.emit()
            event.accept()
            return
        alt_drag_only = self.settings.get("floating_bar", {}).get("alt_drag_only", True)
        if event.button() == Qt.LeftButton and (bool(event.modifiers() & Qt.AltModifier) or not alt_drag_only):
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self.drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self.drag_offset is not None:
            self.drag_offset = None
            self.position_changed.emit(self.x(), self.y())
        super().mouseReleaseEvent(event)


class TrayController:
    def __init__(self, app, icon, on_settings, on_pause, on_resume, on_restart, on_force_reset, on_reset_bar, on_set_visibility, get_visibility, on_quit) -> None:
        self.tray = QSystemTrayIcon(icon, app)
        self.tray.setToolTip("Waky")
        self._get_visibility = get_visibility
        self.menu = QMenu()
        menu = self.menu
        settings_action = menu.addAction("Open Settings")
        settings_action.triggered.connect(on_settings)
        menu.addSeparator()

        bar_menu = menu.addMenu("Floating Bar")
        group = QActionGroup(bar_menu)
        group.setExclusive(True)
        self._visibility_actions: dict[str, QAction] = {}
        for key, label in VISIBILITY_MODES:
            action = bar_menu.addAction(label)
            action.setCheckable(True)
            group.addAction(action)
            action.triggered.connect(lambda _checked=False, k=key: on_set_visibility(k))
            self._visibility_actions[key] = action
        bar_menu.addSeparator()
        bar_menu.addAction("Reset Position").triggered.connect(on_reset_bar)
        menu.aboutToShow.connect(self._refresh)

        pause_action = menu.addAction("Pause")
        pause_action.triggered.connect(on_pause)
        resume_action = menu.addAction("Resume")
        resume_action.triggered.connect(on_resume)
        menu.addSeparator()
        self._extras_anchor = menu.addSeparator()   # app-specific items (update, paste last) are inserted above this
        menu.addAction("Restart Waky").triggered.connect(on_restart)
        menu.addAction("Force Reset").triggered.connect(on_force_reset)
        menu.addSeparator()
        menu.addAction("Quit Waky").triggered.connect(on_quit)
        self.tray.setContextMenu(menu)
        self._refresh()
        self.tray.show()

    def _refresh(self) -> None:
        current = self._get_visibility()
        for key, action in self._visibility_actions.items():
            action.setChecked(key == current)

    def add_action(self, text: str, callback, visible: bool = True) -> QAction:
        action = QAction(text, self.menu)
        action.triggered.connect(callback)
        action.setVisible(visible)
        self.menu.insertAction(self._extras_anchor, action)
        return action

    def notify(self, title: str, message: str, on_click=None) -> None:
        if on_click is not None:
            try:
                self.tray.messageClicked.disconnect()
            except Exception:
                pass
            self.tray.messageClicked.connect(on_click)
        self.tray.showMessage(title, message, QSystemTrayIcon.Information, 8000)

    def hide(self) -> None:
        self.tray.hide()
