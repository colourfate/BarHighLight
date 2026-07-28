import ctypes
import ctypes.wintypes as wintypes
import threading
import logging
from dataclasses import dataclass

import uiautomation as auto

log = logging.getLogger("BarHighLight.taskbar")

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


def _get_pid_from_hwnd(hwnd: int) -> int:
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _get_process_name_from_pid(pid: int) -> str:
    if not pid:
        return ""
    handle = kernel32.OpenProcess(0x0400 | 0x0010, False, pid)
    if not handle:
        log.debug("无法打开进程 PID=%d, 错误=%d", pid, kernel32.GetLastError())
        return ""
    try:
        buf = ctypes.create_unicode_buffer(260)
        if psapi.GetModuleBaseNameW(handle, None, buf, 260):
            return buf.value.lower()
    except Exception as e:
        log.debug("获取进程名失败 PID=%d: %s", pid, e)
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

    # Python 3.14 对 WINFUNCTYPE 回调签名检查更严格
    # 改用 ctypes.POINTER 方式避免回调签名验证问题
    hwnd = user32.GetTopWindow(0)
    while hwnd:
        if user32.IsWindowVisible(hwnd):
            title = _get_window_text(hwnd)
            if title:
                pid = _get_pid_from_hwnd(hwnd)
                proc = _get_process_name_from_pid(pid)
                if proc:
                    mapping[title] = proc
        hwnd = user32.GetWindow(hwnd, 2)  # GW_HWNDNEXT
    log.debug("窗口标题映射: %d 条", len(mapping))
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


def _query_legacy_taskbar(hwnd: int) -> list:
    """通过 MSTaskListWClass 子控件枚举任务栏图标（Win10 及更早版本）。"""
    icons = []
    try:
        ml = auto.ControlFromHandle(hwnd)
        if not ml:
            return icons
        for child in ml.GetChildren():
            try:
                rect = child.BoundingRectangle
                if not rect:
                    continue
                left, top = int(rect.left), int(rect.top)
                right, bottom = int(rect.right), int(rect.bottom)
                if (right - left) < 5 or (bottom - top) < 5:
                    continue
                icons.append((child.Name or "", child.NativeWindowHandle,
                              (left, top, right, bottom)))
            except Exception:
                continue
    except Exception:
        pass
    return icons


def _find_xaml_frame(ctrl, depth=0, max_depth=6):
    """递归查找 ClassName 为 Taskbar.TaskbarFrameAutomationPeer 的控件。"""
    if depth > max_depth:
        return None
    try:
        if (ctrl.ClassName or "") == "Taskbar.TaskbarFrameAutomationPeer":
            return ctrl
        for child in ctrl.GetChildren():
            result = _find_xaml_frame(child, depth + 1, max_depth)
            if result:
                return result
    except Exception:
        pass
    return None


def _query_xaml_taskbar(tray_hwnd: int) -> list:
    """通过 XAML UIA 树枚举任务栏图标（Windows 11）。

    查找 Taskbar.TaskbarFrameAutomationPeer 下的 Taskbar.TaskListButtonAutomationPeer。
    """
    icons = []
    try:
        shell_ctrl = auto.ControlFromHandle(tray_hwnd)
        if not shell_ctrl:
            return icons

        frame = _find_xaml_frame(shell_ctrl)
        if not frame:
            return icons

        # frame -> unnamed container -> buttons
        for child in frame.GetChildren():
            for btn in child.GetChildren():
                cname = btn.ClassName or ""
                if "TaskListButton" in cname:
                    rect = btn.BoundingRectangle
                    if rect and rect.width() > 5 and rect.height() > 5:
                        icons.append((btn.Name or "", btn.NativeWindowHandle,
                                      (int(rect.left), int(rect.top),
                                       int(rect.right), int(rect.bottom))))
    except Exception as e:
        log.debug("XAML 任务栏枚举异常: %s", e)
    return icons


def _find_all_taskbar_hwnds() -> list[int]:
    """返回所有任务栏窗口句柄（主屏+副屏）。"""
    hwnds = []
    shell = user32.FindWindowW("Shell_TrayWnd", None)
    if shell:
        hwnds.append(shell)
    # Windows 多显示器：副屏任务栏
    hwnd = 0
    while True:
        hwnd = user32.FindWindowExW(0, hwnd, "Shell_SecondaryTrayWnd", None)
        if not hwnd:
            break
        hwnds.append(hwnd)
    return hwnds


def query_taskbar_icons() -> list:
    icons: list = []
    title_map = _build_title_to_proc_map()
    seen = set()

    for tray_hwnd in _find_all_taskbar_hwnds():
        # 优先尝试 XAML 树（Windows 11）
        raw = _query_xaml_taskbar(tray_hwnd)
        # 回退到传统 MSTaskListWClass
        if not raw:
            rebar = user32.FindWindowExW(tray_hwnd, 0, "ReBarWindow32", None)
            sw = user32.FindWindowExW(rebar, 0, "MSTaskSwWClass", None) if rebar else 0
            legacy_hwnd = user32.FindWindowExW(sw, 0, "MSTaskListWClass", 0) if sw else 0
            if legacy_hwnd:
                raw = _query_legacy_taskbar(legacy_hwnd)

        for title, child_hwnd, rect in raw:
            left, top, right, bottom = rect
            key = (left, top, right, bottom)
            if key in seen:
                continue
            seen.add(key)

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

    log.debug("检测到 %d 个任务栏图标", len(icons))
    return icons


class TaskbarMonitor:
    def __init__(self):
        self._icons: list = []
        self._lock = threading.Lock()

    def refresh(self) -> list:
        try:
            auto.Initialize()
        except Exception as e:
            log.debug("UIA Initialize 异常 (可忽略): %s", e)
        icons = query_taskbar_icons()
        try:
            auto.Uninitialize()
        except Exception as e:
            log.debug("UIA Uninitialize 异常 (可忽略): %s", e)
        with self._lock:
            self._icons = icons
        return icons

    def get_icons(self) -> list:
        with self._lock:
            return list(self._icons)
