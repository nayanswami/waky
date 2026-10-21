"""Update checker: asks GitHub for the newest release, downloads the installer, verifies its SHA-256, runs it."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen

from PySide6.QtCore import QObject, Signal

from . import __version__

LOGGER = logging.getLogger("waky")
REPO = "nayanswami/waky"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
ASSET_NAME = "Waky-Setup.exe"
USER_AGENT = f"Waky/{__version__}"


class UpdateError(RuntimeError):
    pass


@dataclass
class UpdateInfo:
    version: str
    notes: str
    asset_url: str
    sha256: str
    page_url: str
    size: int = 0


def parse_version(text: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", text.split("-")[0])
    return tuple(int(n) for n in nums[:4]) or (0,)


def is_newer(latest: str, current: str = __version__) -> bool:
    a, b = parse_version(latest), parse_version(current)
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


def info_from_release(data: dict) -> UpdateInfo | None:
    tag = str(data.get("tag_name", "")).strip()
    if not tag or data.get("draft") or data.get("prerelease"):
        return None
    asset = next((a for a in data.get("assets", []) if a.get("name") == ASSET_NAME), None)
    if not asset:
        return None
    notes = str(data.get("body") or "")
    match = re.search(r"\b[0-9a-fA-F]{64}\b", notes)
    return UpdateInfo(
        version=tag.lstrip("vV"),
        notes=notes,
        asset_url=str(asset.get("browser_download_url", "")),
        sha256=match.group(0).lower() if match else "",
        page_url=str(data.get("html_url", f"https://github.com/{REPO}/releases")),
        size=int(asset.get("size", 0) or 0),
    )


def fetch_latest(timeout: float = 8) -> UpdateInfo | None:
    request = Request(API_URL, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return info_from_release(json.loads(response.read().decode("utf-8")))
    except Exception as exc:
        raise UpdateError(f"Could not reach GitHub ({exc.__class__.__name__}).") from exc


def download(info: UpdateInfo, progress=None) -> Path:
    """Download the installer into its own fresh folder and verify the checksum when the release publishes one."""
    folder = Path(tempfile.mkdtemp(prefix="waky-update-"))
    target = folder / ASSET_NAME
    digest = hashlib.sha256()
    request = Request(info.asset_url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=30) as response, open(target, "wb") as out:
            total = int(response.headers.get("Content-Length") or info.size or 0)
            done = 0
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                digest.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(int(done * 100 / total))
    except Exception as exc:
        raise UpdateError(f"Download failed ({exc.__class__.__name__}). Check your internet and try again.") from exc
    if info.sha256 and digest.hexdigest().lower() != info.sha256:
        target.unlink(missing_ok=True)
        raise UpdateError("The downloaded file did not match the published checksum, so it was discarded.")
    return target


def launch_installer(path: Path) -> None:
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(path), "/SILENT", "/NORESTART", "/SUPPRESSMSGBOXES"], creationflags=flags, close_fds=True)


class UpdateChecker(QObject):
    update_found = Signal(object)      # UpdateInfo
    up_to_date = Signal()
    check_failed = Signal(str)
    progress = Signal(int)
    installer_ready = Signal(object)   # Path
    install_failed = Signal(str)

    def __init__(self, config, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.latest: UpdateInfo | None = None
        self._busy = False

    def _settings(self) -> dict:
        return self.config.settings.setdefault("updates", {"auto_check": True, "last_check": 0, "skipped": ""})

    def auto_check(self) -> None:
        s = self._settings()
        if s.get("auto_check", True) and time.time() - float(s.get("last_check", 0) or 0) > 20 * 3600:
            self.check(manual=False)

    def check(self, manual: bool = True) -> None:
        if self._busy:
            return
        self._busy = True

        def work() -> None:
            try:
                info = fetch_latest()
                s = self._settings()
                s["last_check"] = time.time()
                self.config.save_settings()
                if info and is_newer(info.version):
                    self.latest = info
                    if manual or info.version != s.get("skipped"):
                        self.update_found.emit(info)
                else:
                    self.latest = None
                    if manual:
                        self.up_to_date.emit()
            except UpdateError as exc:
                LOGGER.info("Update check failed: %s", exc)
                if manual:
                    self.check_failed.emit(str(exc))
            finally:
                self._busy = False

        threading.Thread(target=work, daemon=True, name="waky-update-check").start()

    def install(self, info: UpdateInfo | None = None) -> None:
        info = info or self.latest
        if not info or self._busy:
            return
        self._busy = True

        def work() -> None:
            try:
                path = download(info, self.progress.emit)
                self.installer_ready.emit(path)
            except UpdateError as exc:
                self.install_failed.emit(str(exc))
            finally:
                self._busy = False

        threading.Thread(target=work, daemon=True, name="waky-update-download").start()

    def skip(self, version: str) -> None:
        self._settings()["skipped"] = version
        self.config.save_settings()
