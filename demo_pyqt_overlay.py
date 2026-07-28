"""
PyQt6 Overlay Demo
Tests: transparency, colored drawing, click-through, multi-screen support

Usage:
  python demo_pyqt_overlay.py          # Step-by-step (press Enter)
  python demo_pyqt_overlay.py auto     # Auto 3s per step
  python demo_pyqt_overlay.py coords   # Print taskbar coordinates only
"""

import sys
import ctypes
import time

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QApplication, QWidget

from overlay_window import get_available_screens


WS_EX_TRANSPARENT = 0x00000020
GWL_EXSTYLE = -20


class TestOverlay(QWidget):
    """测试用覆盖层，仅覆盖选定的单个屏幕。"""

    def __init__(self, screen_info: dict, mode="line", color=(255, 0, 0)):
        super().__init__()
        self._mode = mode
        self._color = color
        self._rects = []

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # 从屏幕信息获取参数
        self._dpr = screen_info["dpr"]
        self._phys_x, self._phys_y = screen_info["physical_rect"][:2]
        gx, gy, gw, gh = screen_info["logical_rect"]
        self.setGeometry(gx, gy, gw, gh)

        print(f"[Overlay] 屏幕[{screen_info['index']}] {screen_info['name']}")
        print(f"  逻辑: {gw}x{gh}@({gx},{gy}), DPR={self._dpr}")
        print(f"  物理原点: ({self._phys_x},{self._phys_y})")

    def showEvent(self, event):
        super().showEvent(event)
        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        ctypes.windll.user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE,
            style | WS_EX_TRANSPARENT)
        print(f"[Overlay] hwnd={hwnd:#x}, WS_EX_TRANSPARENT set")

    def set_rects(self, rects):
        self._rects = rects
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        r, g, b = self._color
        s = self._dpr
        ox, oy = self._phys_x, self._phys_y

        if self._mode == "full_red":
            painter.fillRect(self.rect(), QColor(r, g, b, 80))
            painter.fillRect(0, 0, self.width(), 6, QColor(255, 255, 0))

        elif self._mode == "line":
            for rect in self._rects:
                x, y, w, h = rect
                lx = int((x - ox) / s)
                ly = int((y - oy) / s)
                lw = int(w / s)
                lh = int(h / s)
                painter.fillRect(lx, ly - 4, lw, 4, QColor(r, g, b))

        elif self._mode == "overlay":
            for rect in self._rects:
                x, y, w, h = rect
                lx = int((x - ox) / s)
                ly = int((y - oy) / s)
                lw = int(w / s)
                lh = int(h / s)
                painter.fillRect(lx, ly, lw, lh, QColor(r, g, b, 100))

        painter.end()

    def mousePressEvent(self, event):
        print(f"[Overlay] Mouse event at ({event.position().x()}, {event.position().y()})")


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


def get_taskbar_rects():
    """Get taskbar icon rects — supports both Win10 (MSTaskListWClass) and Win11 (XAML)."""
    user32 = ctypes.windll.user32
    rects = []
    try:
        import uiautomation as auto
        try:
            auto.Initialize()
        except Exception:
            pass

        # 枚举所有任务栏窗口（主屏 + 副屏）
        tray_hwnds = []
        shell = user32.FindWindowW("Shell_TrayWnd", None)
        if shell:
            tray_hwnds.append(shell)
        hwnd = 0
        while True:
            hwnd = user32.FindWindowExW(0, hwnd, "Shell_SecondaryTrayWnd", None)
            if not hwnd:
                break
            tray_hwnds.append(hwnd)

        for tray_hwnd in tray_hwnds:
            # Win11: 通过 XAML 树查找 TaskListButton
            shell_ctrl = auto.ControlFromHandle(tray_hwnd)
            if not shell_ctrl:
                continue
            frame = _find_xaml_frame(shell_ctrl)
            if frame:
                for child in frame.GetChildren():
                    for btn in child.GetChildren():
                        cname = btn.ClassName or ""
                        if "TaskListButton" in cname:
                            r = btn.BoundingRectangle
                            if r and r.width() > 5 and r.height() > 5:
                                rects.append((int(r.left), int(r.top),
                                              int(r.width()), int(r.height())))
                continue

            # Win10 回退: MSTaskListWClass
            rebar = user32.FindWindowExW(tray_hwnd, 0, "ReBarWindow32", None)
            sw = user32.FindWindowExW(rebar, 0, "MSTaskSwWClass", None) if rebar else 0
            hwnd = user32.FindWindowExW(sw, 0, "MSTaskListWClass", 0) if sw else 0
            if hwnd:
                ml = auto.ControlFromHandle(hwnd)
                if ml:
                    for child in ml.GetChildren():
                        r = child.BoundingRectangle
                        if r and r.width() > 5 and r.height() > 5:
                            rects.append((int(r.left), int(r.top),
                                          int(r.width()), int(r.height())))

        try:
            auto.Uninitialize()
        except Exception:
            pass
    except Exception as e:
        print(f"[Coord] UIA error: {e}")
    return rects


def select_screen() -> dict:
    """列出所有屏幕并让用户选择。"""
    screens = get_available_screens()
    if len(screens) == 1:
        print(f"\n仅检测到一个屏幕: {screens[0]['name']}")
        return screens[0]

    print(f"\n检测到 {len(screens)} 个屏幕:")
    for s in screens:
        primary = " (主屏幕)" if s["is_primary"] else ""
        lx, ly, lw, lh = s["logical_rect"]
        px, py, pw, ph = s["physical_rect"]
        print(f"  [{s['index']}] {s['name']}{primary}")
        print(f"      逻辑: {lw}x{lh}@({lx},{ly}), DPR={s['dpr']}")
        print(f"      物理: {pw}x{ph}@({px},{py})")

    while True:
        try:
            choice = input(f"\n选择屏幕 [0-{len(screens)-1}] (回车=主屏幕): ").strip()
            if choice == "":
                idx = next(s["index"] for s in screens if s["is_primary"])
                return screens[idx]
            idx = int(choice)
            if 0 <= idx < len(screens):
                return screens[idx]
            print("无效索引，请重新输入")
        except ValueError:
            print("请输入数字")


def print_coords():
    app = QApplication.instance() or QApplication(sys.argv)
    rects = get_taskbar_rects()
    user32 = ctypes.windll.user32

    SM_XVIRTUALSCREEN = 76
    SM_YVIRTUALSCREEN = 77
    SM_CXVIRTUALSCREEN = 78
    SM_CYVIRTUALSCREEN = 79
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    print(f"\nVirtual desktop: {vx},{vy} {vw}x{vh}")

    screens = get_available_screens()
    for s in screens:
        primary = " (主)" if s["is_primary"] else ""
        lx, ly, lw, lh = s["logical_rect"]
        px, py, pw, ph = s["physical_rect"]
        print(f"  屏幕[{s['index']}] {s['name']}{primary}: "
              f"逻辑={lw}x{lh}@({lx},{ly}), 物理={pw}x{ph}@({px},{py}), DPR={s['dpr']}")

    print(f"\nTaskbar icons found: {len(rects)}")
    for i, (x, y, w, h) in enumerate(rects):
        print(f"  [{i}] x={x}, y={y}, w={w}, h={h}")


def run_demo(auto=False):
    print("PyQt6 Overlay Demo")
    print("=" * 50)

    # 选择屏幕
    screen_info = select_screen()
    print(f"\n已选择: 屏幕[{screen_info['index']}] {screen_info['name']}")

    rects = get_taskbar_rects()
    print(f"Taskbar icons: {len(rects)}")
    ox, oy = screen_info["physical_rect"][:2]
    s = screen_info["dpr"]
    for i, (x, y, w, h) in enumerate(rects):
        lx = int((x - ox) / s)
        ly = int((y - oy) / s)
        lw = int(w / s)
        lh = int(h / s)
        print(f"  [{i}] phys=({x},{y},{w},{h}) -> local=({lx},{ly},{lw},{lh})")

    overlay = TestOverlay(screen_info)
    overlay.show()

    steps = [
        ("full_red", (255, 0, 0), "半透明红色覆盖 + 黄色顶部线。能看到吗？能点击任务栏吗？"),
        ("line", (0, 255, 0), "任务栏图标上方的绿色线条。能看到吗？能点击图标吗？"),
        ("overlay", (0, 0, 255), "任务栏图标上的蓝色半透明覆盖。能看到吗？"),
        ("line", (255, 165, 0), "橙色线条。最终检查 - 点击图标验证穿透。"),
    ]

    for i, (mode, color, desc) in enumerate(steps):
        overlay._mode = mode
        overlay._color = color
        overlay.set_rects(rects)
        print(f"\n[Step {i+1}/4] {desc}")

        if not auto:
            input("Press Enter to continue...")
        else:
            time.sleep(3)

    print("\nDemo done. Closing overlay...")
    overlay.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    if len(sys.argv) > 1 and sys.argv[1] == "coords":
        print_coords()
    else:
        auto = len(sys.argv) > 1 and sys.argv[1] == "auto"
        run_demo(auto)
