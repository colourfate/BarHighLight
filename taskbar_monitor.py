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
    return user32.FindWindowExW(sw, 0, "MSTaskListWClass", 0)


def _get_pid_from_hwnd(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _get_process_name_from_pid(pid: int) -> str:
    if not pid:
        return ""
    handle = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
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


def _get_window_text(hwnd: int) -> str:
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def _build_title_to_proc_map() -> dict:
    mapping = {}

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def callback(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            title = _get_window_text(hwnd)
            if title:
                pid = _get_pid_from_hwnd(hwnd)
                proc = _get_process_name_from_pid(pid)
                if proc:
                    mapping[title] = proc
        return True

    user32.EnumWindows(WNDENUMPROC(callback), 0)
    return mapping


def _match_proc_from_title(button_title: str, title_map: dict) -> str:
    button_core = button_title.split(" - ")[0].strip().lower()
    if not button_core:
        return ""
    for win_title, proc in title_map.items():
        win_lower = win_title.lower()
        if button_core in win_lower:
            return proc
    for win_title, proc in title_map.items():
        win_lower = win_title.lower()
        for part in win_lower.split(" - "):
            part = part.strip()
            if part and len(part) > 2 and part in button_core:
                return proc
    if "资源管理器" in button_core or "explorer" in button_core:
        return "explorer.exe"
    if "终端" in button_core or "terminal" in button_core:
        return "windowsterminal.exe"
    if "任务管理器" in button_core or "task" in button_core:
        return "taskmgr.exe"
    if "记事本" in button_core or "notepad" in button_core:
        return "notepad.exe"
    if "设置" in button_core or "setting" in button_core:
        return "systemsettings.exe"
    return ""


def query_taskbar_icons() -> list:
    icons: list = []
    hwnd = _find_taskbar_list_hwnd()
    if not hwnd:
        return icons

    title_map = _build_title_to_proc_map()

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
                if child_hwnd and user32.IsWindow(child_hwnd):
                    pid = _get_pid_from_hwnd(child_hwnd)
                    proc_name = _get_process_name_from_pid(pid)

                if not proc_name:
                    proc_name = _match_proc_from_title(title, title_map)

                if not proc_name:
                    core = title.split(" - ")[0].strip().lower()
                    proc_name = core if core else "unknown"

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
