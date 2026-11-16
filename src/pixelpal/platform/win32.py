"""Windows 10/11 integration through ctypes only (no extra dependencies, no admin rights).

Every call is defensive: if an API misbehaves the pet falls back to plain screen edges.
"""
from __future__ import annotations

import ctypes
import os
import sys
from ctypes import wintypes

from ..core.geometry import Rect
from ..core.sysmon import Sample
from .base import NativeWindow, Platform

WS_EX_TOOLWINDOW = 0x00000080
GWL_EXSTYLE = -20
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
IGNORED_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
                   "Windows.UI.Core.CoreWindow", "XamlExplorerHostIslandWindow"}
MIN_W, MIN_H = 120, 60
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "PixelPal"


def acceptable(visible: bool, minimized: bool, cloaked: bool, tool: bool, title: str,
               cls: str, own: bool, rect: Rect) -> bool:
    """Is this a real application window worth standing on? (Pure, so it is unit-tested.)"""
    if not visible or minimized or cloaked or tool or own:
        return False
    if not title or cls in IGNORED_CLASSES:
        return False
    return rect.width >= MIN_W and rect.height >= MIN_H


class _FILETIME(ctypes.Structure):
    _fields_ = [("lo", wintypes.DWORD), ("hi", wintypes.DWORD)]

    @property
    def value(self) -> int:
        return (self.hi << 32) | self.lo


class _POWER(ctypes.Structure):
    _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                ("BatteryLifeTime", wintypes.DWORD), ("BatteryFullLifeTime", wintypes.DWORD)]


class WindowsPlatform(Platform):
    name = "windows"
    supports_windows = True
    supports_autostart = True

    def __init__(self) -> None:
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        try:
            self.dwm = ctypes.WinDLL("dwmapi")
        except OSError:
            self.dwm = None
        self._enum_proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self.user32.EnumWindows.argtypes = [self._enum_proc, wintypes.LPARAM]
        self.user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        for fn in (self.user32.IsWindowVisible, self.user32.IsIconic):
            fn.argtypes = [wintypes.HWND]
        self._pid = os.getpid()
        self._cpu_prev: tuple[int, int] | None = None

    # -- windows --------------------------------------------------------------------------
    def list_windows(self) -> list[NativeWindow]:
        found: list[NativeWindow] = []

        def visit(hwnd, _lparam):
            try:
                info = self._describe(hwnd)
                if info is not None:
                    found.append(info)
            except Exception:
                pass
            return True

        try:
            self.user32.EnumWindows(self._enum_proc(visit), 0)   # enumerates in z-order, top first
        except Exception:
            return []
        return found

    def _describe(self, hwnd) -> NativeWindow | None:
        u = self.user32
        if not u.IsWindowVisible(hwnd):
            return None
        title = ctypes.create_unicode_buffer(256)
        u.GetWindowTextW(hwnd, title, 256)
        cls = ctypes.create_unicode_buffer(256)
        u.GetClassNameW(hwnd, cls, 256)
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        cloaked = wintypes.DWORD(0)
        rc = wintypes.RECT()
        have_rect = False
        if self.dwm is not None:
            self.dwm.DwmGetWindowAttribute(wintypes.HWND(hwnd), DWMWA_CLOAKED,
                                           ctypes.byref(cloaked), ctypes.sizeof(cloaked))
            # The visible frame; GetWindowRect also includes invisible resize borders.
            have_rect = self.dwm.DwmGetWindowAttribute(
                wintypes.HWND(hwnd), DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(rc), ctypes.sizeof(rc)) == 0
        if not have_rect and not u.GetWindowRect(hwnd, ctypes.byref(rc)):
            return None
        rect = Rect(rc.left, rc.top, rc.right, rc.bottom)
        ok = acceptable(True, bool(u.IsIconic(hwnd)), bool(cloaked.value),
                        bool(u.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW),
                        title.value, cls.value, pid.value == self._pid, rect)
        return NativeWindow(int(hwnd), rect, title.value) if ok else None

    # -- system -----------------------------------------------------------------------------
    def sample_system(self) -> Sample:
        cpu = battery = None
        on_ac = True
        try:
            idle, kernel, user = _FILETIME(), _FILETIME(), _FILETIME()
            if self.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
                total, idle_t = kernel.value + user.value, idle.value     # kernel time includes idle
                if self._cpu_prev is not None:
                    dt, di = total - self._cpu_prev[0], idle_t - self._cpu_prev[1]
                    if dt > 0:
                        cpu = max(0.0, min(100.0, 100.0 * (dt - di) / dt))
                self._cpu_prev = (total, idle_t)
            power = _POWER()
            if self.kernel32.GetSystemPowerStatus(ctypes.byref(power)):
                on_ac = power.ACLineStatus != 0
                if power.BatteryLifePercent <= 100 and not power.BatteryFlag & 128:   # 128 = no battery
                    battery = int(power.BatteryLifePercent)
        except Exception:
            pass
        return Sample(cpu, battery, on_ac)

    def open_path(self, target: str) -> None:
        os.startfile(target)   # noqa: S606 - same as double-clicking it in Explorer

    # -- launch at login (per-user Run key, no admin needed) ---------------------------------
    @staticmethod
    def launch_command() -> str:
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        exe = sys.executable
        pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")
        return f'"{pythonw if os.path.exists(pythonw) else exe}" -m pixelpal'

    def autostart_enabled(self) -> bool:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
                winreg.QueryValueEx(key, RUN_VALUE)
                return True
        except OSError:
            return False

    def set_autostart(self, enabled: bool) -> None:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, self.launch_command())
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
