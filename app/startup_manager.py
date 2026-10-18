from __future__ import annotations

import sys
import os
from pathlib import Path
import logging

from .utils import FROZEN


class StartupManager:
    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    RUN_VALUE = "Waky"
    SHORTCUT_NAME = "Waky.lnk"
    FALLBACK_NAME = "Waky.vbs"

    def __init__(self, launcher_script: Path, logger: logging.Logger | None = None) -> None:
        self.launcher_script = launcher_script.resolve()
        self.project_dir = self.launcher_script.parent
        self.logger = logger or logging.getLogger("waky")

    def startup_folder(self) -> Path:
        if sys.platform != "win32":
            return Path()
        appdata = os.environ.get("APPDATA", "")
        return Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"

    def _shortcut_path(self) -> Path:
        return self.startup_folder() / self.SHORTCUT_NAME

    def _fallback_vbs_path(self) -> Path:
        return self.startup_folder() / self.FALLBACK_NAME

    # Packaged exe: a per-user Run registry value pointing at Waky.exe (no scripts, no console).
    def _registry_enabled(self) -> bool:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY) as key:
                winreg.QueryValueEx(key, self.RUN_VALUE)
            return True
        except FileNotFoundError:
            return False

    def _registry_set(self, enabled: bool) -> None:
        import winreg

        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, self.RUN_VALUE, 0, winreg.REG_SZ, f'"{sys.executable}"')
                self.logger.info("[STARTUP] registry Run entry set to %s", sys.executable)
            else:
                try:
                    winreg.DeleteValue(key, self.RUN_VALUE)
                except FileNotFoundError:
                    pass

    def is_enabled(self) -> bool:
        if sys.platform != "win32":
            return False
        if FROZEN:
            return self._registry_enabled()
        return self._shortcut_path().exists() or self._fallback_vbs_path().exists()

    def set_enabled(self, enabled: bool) -> None:
        if sys.platform != "win32":
            return
        if FROZEN:
            self._registry_set(enabled)
            return
        shortcut_path = self._shortcut_path()
        if enabled:
            self.repair_startup_entry()
            return
        try:
            shortcut_path.unlink()
        except FileNotFoundError:
            pass
        try:
            self._fallback_vbs_path().unlink()
        except FileNotFoundError:
            pass

    def repair_startup_entry(self) -> None:
        if sys.platform != "win32":
            return
        if FROZEN:
            self._registry_set(True)  # refreshes the path if the install folder moved
            return
        self._ensure_launcher_exists()
        startup = self.startup_folder()
        startup.mkdir(parents=True, exist_ok=True)
        fallback = self._fallback_vbs_path()
        if fallback.exists():
            try:
                fallback.unlink()
                self.logger.info("[STARTUP] removed broken startup script")
            except Exception:
                self.logger.warning("[STARTUP] could not remove old startup script", exc_info=True)
        self._create_shortcut(self._shortcut_path())
        self.logger.info("[STARTUP] created corrected hidden launcher")
        self.logger.info("[STARTUP] startup target=%s", self.launcher_script)
        self.logger.info("[STARTUP] working directory=%s", self.project_dir)

    def _ensure_launcher_exists(self) -> None:
        if not self.launcher_script.exists():
            raise FileNotFoundError(f"Hidden launcher not found: {self.launcher_script}")
        pythonw = self.project_dir / ".venv" / "Scripts" / "pythonw.exe"
        main_py = self.project_dir / "main.py"
        if not pythonw.exists():
            raise FileNotFoundError(f"pythonw.exe not found: {pythonw}")
        if not main_py.exists():
            raise FileNotFoundError(f"main.py not found: {main_py}")

    def _create_shortcut(self, shortcut_path: Path) -> None:
        shortcut_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            import pythoncom  # type: ignore
            from win32com.client import Dispatch  # type: ignore

            pythoncom.CoInitialize()
            shell = Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(str(shortcut_path))
            shortcut.Targetpath = str(Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "wscript.exe")
            shortcut.Arguments = f'"{self.launcher_script}"'
            shortcut.WorkingDirectory = str(self.project_dir)
            shortcut.Description = "Start Waky silently"
            shortcut.save()
        except Exception:
            fallback = shortcut_path.with_suffix(".vbs")
            fallback.write_text(
                "\n".join(
                    [
                        "Option Explicit",
                        "Dim shell",
                        'Set shell = CreateObject("WScript.Shell")',
                        f'shell.CurrentDirectory = "{self.project_dir}"',
                        f'shell.Run "wscript.exe ""{self.launcher_script}""", 0, False',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            self.logger.warning("[STARTUP] shortcut creation failed; copied absolute-path VBS fallback", exc_info=True)
