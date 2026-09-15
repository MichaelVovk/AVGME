"""Thin wrapper over the `adb` CLI.

Everything the bot does to the game goes through here: grab a frame, tap a point,
press Back. Using plain adb rather than an emulator's own automation API is what
keeps this portable across BlueStacks / LDPlayer / MuMu and onto a real phone.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from dataclasses import dataclass

import cv2
import numpy as np

log = logging.getLogger(__name__)


class AdbError(RuntimeError):
    """An adb invocation failed or returned something unusable."""


@dataclass
class Adb:
    host: str = "127.0.0.1"
    port: int = 5555
    timeout: int = 20

    @property
    def serial(self) -> str:
        return f"{self.host}:{self.port}"

    # -- plumbing ---------------------------------------------------------

    @staticmethod
    def executable() -> str:
        exe = shutil.which("adb")
        if exe is None:
            raise AdbError(
                "adb is not on PATH. Install Android platform-tools and add the "
                "folder to PATH, then reopen your terminal."
            )
        return exe

    def _run(self, *args: str, binary: bool = False) -> bytes | str:
        cmd = [self.executable(), "-s", self.serial, *args]
        proc = subprocess.run(cmd, capture_output=True, timeout=self.timeout)
        if proc.returncode != 0:
            stderr = proc.stderr.decode("utf-8", "replace").strip()
            raise AdbError(f"adb {' '.join(args)} failed: {stderr or 'no stderr'}")
        return proc.stdout if binary else proc.stdout.decode("utf-8", "replace")

    def connect(self) -> None:
        """Attach to the emulator. Safe to call when already connected."""
        exe = self.executable()
        proc = subprocess.run(
            [exe, "connect", self.serial], capture_output=True, timeout=self.timeout
        )
        out = proc.stdout.decode("utf-8", "replace").strip()
        if "connected" not in out.lower():
            raise AdbError(
                f"could not connect to {self.serial}: {out or 'no output'}. "
                "Is the emulator running, and is ADB enabled in its settings?"
            )
        log.debug("adb connect: %s", out)

    def is_connected(self) -> bool:
        exe = self.executable()
        proc = subprocess.run([exe, "devices"], capture_output=True, timeout=self.timeout)
        listing = proc.stdout.decode("utf-8", "replace")
        return any(
            line.startswith(self.serial) and line.split("\t")[-1].strip() == "device"
            for line in listing.splitlines()
        )

    # -- input ------------------------------------------------------------

    def tap(self, x: int, y: int) -> None:
        self._run("shell", "input", "tap", str(int(x)), str(int(y)))

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self._run(
            "shell", "input", "swipe",
            str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(duration_ms)),
        )

    def back(self) -> None:
        self._run("shell", "input", "keyevent", "4")

    # -- screen -----------------------------------------------------------

    def resolution(self) -> tuple[int, int]:
        """Return (width, height) as reported by the device."""
        out = str(self._run("shell", "wm", "size"))
        # Prefer "Override size:" when present - that's what is actually rendered.
        size = None
        for line in out.splitlines():
            if ":" in line and "x" in line:
                label, _, value = line.partition(":")
                value = value.strip()
                if "Override" in label:
                    size = value
                elif size is None:
                    size = value
        if not size:
            raise AdbError(f"could not parse `wm size` output: {out!r}")
        w, _, h = size.partition("x")
        return int(w), int(h)

    def screencap(self) -> np.ndarray:
        """Grab the current frame as a BGR ndarray."""
        raw = self._run("exec-out", "screencap", "-p", binary=True)
        frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is not None:
            return frame

        # Some emulator adb builds on Windows push screencap through a shell that
        # rewrites \n as \r\n, corrupting the PNG. Undo that and retry before
        # giving up.
        log.debug("exec-out screencap did not decode; retrying via shell with CRLF repair")
        raw = self._run("shell", "screencap", "-p", binary=True)
        repaired = raw.replace(b"\r\r\n", b"\n").replace(b"\r\n", b"\n")
        frame = cv2.imdecode(np.frombuffer(repaired, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            raise AdbError(
                "screencap returned data that is not a decodable PNG. Try updating "
                "platform-tools, or restart the emulator's ADB."
            )
        return frame
