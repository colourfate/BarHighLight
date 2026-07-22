"""
PyQt6 Overlay Demo
Tests: transparency, colored drawing, click-through

Usage:
  python demo_pyqt_overlay.py          # Step-by-step (press Enter)
  python demo_pyqt_overlay.py auto     # Auto 3s per step
  python demo_pyqt_overlay.py coords   # Print taskbar coordinates only
"""

import sys
import ctypes
import time

from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QApplication, QWidget


WS_EX_TRANSPARENT = 0x00000020
GWL_EXSTYLE = -20


class TestOverlay(QWidget):
    def __init__(self, mode="line", color=(255, 0, 0)):
        super().__init__()
        self._mode = mode
        self._color = color
        self._rects = []
        self._dpi_scale = 1.0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        user32 = ctypes.windll.user32
        phys_w = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
        phys_h = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
        self.setGeometry(0, 0, phys_w, phys_h)

        screen = QApplication.primaryScreen().geometry()
        self._dpi_scale = phys_w / screen.width()
        print(f"[Overlay] Physical: {phys_w}x{phys_h}, Logical: {screen.width()}x{screen.height()}, scale={self._dpi_scale}")

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
        s = self._dpi_scale  # physical-to-logical scale factor

        if self._mode == "full_red":
            painter.fillRect(self.rect(), QColor(r, g, b, 80))
            painter.fillRect(0, 0, self.width(), 6, QColor(255, 255, 0))

        elif self._mode == "line":
            for rect in self._rects:
                x, y, w, h = rect
                lx, ly, lw, lh = x/s, y/s, w/s, h/s
                painter.fillRect(int(lx), int(ly) - 4, int(lw), 4, QColor(r, g, b))

        elif self._mode == "overlay":
            for rect in self._rects:
                x, y, w, h = rect
                lx, ly, lw, lh = x/s, y/s, w/s, h/s
                painter.fillRect(int(lx), int(ly), int(lw), int(lh), QColor(r, g, b, 100))

        painter.end()

    def mousePressEvent(self, event):
        print(f"[Overlay] Mouse event at ({event.position().x()}, {event.position().y()})")


def get_taskbar_rects():
    """Get taskbar icon rects using same approach as taskbar_monitor.py."""
    import ctypes
    user32 = ctypes.windll.user32
    try:
        import uiautomation as auto

        shell = user32.FindWindowW("Shell_TrayWnd", None)
        rebar = user32.FindWindowExW(shell, 0, "ReBarWindow32", None)
        sw = user32.FindWindowExW(rebar, 0, "MSTaskSwWClass", None)
        hwnd = user32.FindWindowExW(sw, 0, "MSTaskListWClass", 0)
        if not hwnd:
            print("[Coord] MSTaskListWClass HWND not found")
            return []

        ml = auto.ControlFromHandle(hwnd)
        if not ml:
            print("[Coord] Cannot get UIA control from handle")
            return []

        rects = []
        for child in ml.GetChildren():
            r = child.BoundingRectangle
            if r and r.width() > 5 and r.height() > 5:
                rects.append((int(r.left), int(r.top), int(r.width()), int(r.height())))
        return rects
    except Exception as e:
        print(f"[Coord] UIA error: {e}")
        return []


def print_coords():
    rects = get_taskbar_rects()
    SM_XVIRTUALSCREEN = 76
    SM_YVIRTUALSCREEN = 77
    SM_CXVIRTUALSCREEN = 78
    SM_CYVIRTUALSCREEN = 79
    user32 = ctypes.windll.user32
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    print(f"\nVirtual desktop: {vx},{vy} {vw}x{vh}")
    print(f"Qt primaryScreen: {QApplication.primaryScreen().geometry().width()}x{QApplication.primaryScreen().geometry().height()}")
    print(f"Taskbar icons found: {len(rects)}")
    for i, (x, y, w, h) in enumerate(rects):
        print(f"  [{i}] x={x}, y={y}, w={w}, h={h}")


def run_demo(auto=False):
    print("PyQt6 Overlay Demo")
    print("=" * 50)
    SM_CXVIRTUALSCREEN = 78
    SM_CYVIRTUALSCREEN = 79
    user32 = ctypes.windll.user32
    vw = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    vh = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    print(f"Virtual desktop: {vw}x{vh}")

    rects = get_taskbar_rects()
    print(f"Taskbar icons: {len(rects)}")
    for i, (x, y, w, h) in enumerate(rects):
        print(f"  [{i}] x={x}, y={y}, w={w}, h={h}")

    overlay = TestOverlay()
    overlay.show()

    steps = [
        ("full_red", (255, 0, 0), "Full screen red overlay + yellow top line. Can you see it? Can you click taskbar?"),
        ("line", (0, 255, 0), "Green lines above taskbar icons. Can you see them? Can you click icons?"),
        ("overlay", (0, 0, 255), "Blue semi-transparent overlay on taskbar icons. Can you see them?"),
        ("line", (255, 165, 0), "Orange lines. Final check - click icons to verify pass-through."),
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
