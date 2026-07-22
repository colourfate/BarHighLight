import ctypes
import ctypes.wintypes as wintypes
import threading
import time
from dataclasses import dataclass
from typing import Optional

import uiautomation as auto

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
psapi = ctypes.windll.psapi


@dataclass
class TaskbarIcon:
    process_name: str
    window_title: str
    rect: tuple
    hwnd: int

    def __eq__(self, other):
        if not isinstance(other, TaskbarIcon):
            return False
        return (self.process_name == other.process_name and
                self.window_title == other.window_title and
                self.rect == other.rect)

    def __hash__(self):
        return hash((self.process_name, self.window_title, self.rect))


def _find_taskbar_list_hwnd() -> int:
    shell = user32.FindWindowW("Shell_TrayWnd", None)
    if not shell:
        return 0
    rebar = user32.FindWindowExW(shell, 0, "ReBarWindow32", None)
    if not rebar:
        return 0
    sw = user32.FindWindowExW(rebar, 0, "MSTaskSwWClass", None)
    if not sw:
        return 0
    return user32.FindWindowExW(sw, 0, "MSTaskListWClass", None)


def _get_process_name_from_hwnd(hwnd: int) -> str:
    if not hwnd:
        return ""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    handle = kernel32.OpenProcess(0x0400 | 0x0010, False, pid.value)
    if not handle:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(260)
        if psapi.GetModuleBaseNameW(handle, None, buf, 260):
            return buf.value.lower()
    except Exception:
        pass
    finally:
        kernel32.CloseHandle(handle)
    return ""


def query_taskbar_icons() -> list:
    icons: list = []
    hwnd = _find_taskbar_list_hwnd()
    if not hwnd:
        return icons
    try:
        ml = auto.ControlFromHandle(hwnd)
        if not ml:
            return icons
        for child in ml.GetChildren():
            try:
                if child.ControlType != auto.ControlType.ButtonControl:
                    continue
                rect = child.BoundingRectangle
                if not rect:
                    continue
                left, top = int(rect.left), int(rect.top)
                right, bottom = int(rect.right), int(rect.bottom)
                if (right - left) < 5 or (bottom - top) < 5:
                    continue
                title = child.Name or ""
                child_hwnd = child.NativeWindowHandle
                proc_name = ""
                if child_hwnd:
                    proc_name = _get_process_name_from_hwnd(child_hwnd)
                if not proc_name:
                    proc_name = title.lower().split(" - ")[0].strip()
                    if not proc_name:
                        proc_name = "unknown"
                icons.append(TaskbarIcon(
                    process_name=proc_name,
                    window_title=title,
                    rect=(left, top, right, bottom),
                    hwnd=child_hwnd,
                ))
            except Exception:
                continue
    except Exception:
        pass
    return icons


class TaskbarMonitor:
    def __init__(self):
        self._icons: list = []
        self._lock = threading.Lock()

    def refresh(self) -> list:
        try:
            auto.Initialize()
        except Exception:
            pass
        icons = query_taskbar_icons()
        try:
            auto.Uninitialize()
        except Exception:
            pass
        with self._lock:
            self._icons = icons
        return icons

    def get_icons(self) -> list:
        with self._lock:
            return list(self._icons)
