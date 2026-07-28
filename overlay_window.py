import ctypes
import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QWidget, QApplication

from config_manager import Config

log = logging.getLogger("BarHighLight.overlay")

WS_EX_TRANSPARENT = 0x00000020
GWL_EXSTYLE = -20
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


def _parse_color(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    if len(h) == 6:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 128, 128, 128


def get_available_screens() -> list[dict]:
    """返回所有可用屏幕信息列表。

    QScreen.geometry() 的位置坐标与 UIA 坐标在同一参考系中，
    物理原点直接取逻辑位置，仅尺寸需要乘 DPR。
    """
    user32 = ctypes.windll.user32
    vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)

    screens = []
    for i, screen in enumerate(QApplication.screens()):
        geo = screen.geometry()
        dpr = screen.devicePixelRatio()
        screens.append({
            "index": i,
            "name": screen.name(),
            "logical_rect": (geo.x(), geo.y(), geo.width(), geo.height()),
            "physical_rect": (vx + geo.x(), vy + geo.y(),
                              int(geo.width() * dpr), int(geo.height() * dpr)),
            "dpr": dpr,
            "is_primary": screen == QApplication.primaryScreen(),
        })
    return screens


class OverlayWindow(QWidget):
    _update_icons_signal = pyqtSignal(list)
    _update_config_signal = pyqtSignal(object)

    def __init__(self, config: Config):
        super().__init__()
        self._config = config
        self._icons: list = []
        self._dpi_scale: float = 1.0
        self._screen_phys_x: int = 0  # 屏幕物理原点 X (虚拟桌面坐标)
        self._screen_phys_y: int = 0  # 屏幕物理原点 Y

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._target_screen_index: int = -1

        self._update_icons_signal.connect(self._on_update_icons)
        self._update_config_signal.connect(self._on_update_config)

    def _apply_screen(self, screen_index: int) -> None:
        """将覆盖层定位到指定屏幕。screen_index=-1 表示使用主屏幕。"""
        screens = QApplication.screens()
        if not screens:
            log.warning("未检测到屏幕")
            return

        if screen_index < 0 or screen_index >= len(screens):
            screen_index = 0

        self._target_screen_index = screen_index
        screen = screens[screen_index]
        geo = screen.geometry()
        dpr = screen.devicePixelRatio()

        user32 = ctypes.windll.user32
        vx = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
        vy = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)

        # 物理原点 = 虚拟桌面偏移 + 逻辑位置（位置坐标无需乘 DPR）
        self._screen_phys_x = vx + geo.x()
        self._screen_phys_y = vy + geo.y()
        self._dpi_scale = dpr

        # setGeometry 使用逻辑坐标，覆盖层仅覆盖选定屏幕
        self.setGeometry(geo.x(), geo.y(), geo.width(), geo.height())
        log.info("覆盖层定位到屏幕[%d] %s: 逻辑=%dx%d@(%d,%d), 物理原点=(%d,%d), DPR=%.2f",
                 screen_index, screen.name(),
                 geo.width(), geo.height(), geo.x(), geo.y(),
                 self._screen_phys_x, self._screen_phys_y, dpr)

    def set_screen(self, screen_index: int) -> None:
        """指定覆盖层目标屏幕并重新应用几何体。"""
        self._apply_screen(screen_index)
        if self.isVisible():
            self.update()

    def create(self) -> None:
        self._apply_screen(self._target_screen_index)
        self.show()
        log.info("覆盖层窗口已创建 (屏幕[%d])", self._target_screen_index)

    def destroy(self) -> None:
        self.close()
        log.info("覆盖层窗口已销毁")

    def update_config(self, config: Config) -> None:
        self._update_config_signal.emit(config)

    def draw(self, icons: list) -> None:
        self._update_icons_signal.emit(icons)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            hwnd = int(self.winId())
            style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
            ctypes.windll.user32.SetWindowLongPtrW(
                hwnd, GWL_EXSTYLE, style | WS_EX_TRANSPARENT
            )
            log.debug("WS_EX_TRANSPARENT 已设置 hwnd=%#x", hwnd)
        except Exception as e:
            log.warning("设置点击穿透失败: %s", e)

    def paintEvent(self, event):
        painter = QPainter(self)
        s = self._dpi_scale
        ox, oy = self._screen_phys_x, self._screen_phys_y
        for icon in self._icons:
            color_hex = self._config.highlights.get(icon.process_name, "#808080")
            r, g, b = _parse_color(color_hex)
            left, top, right, bottom = icon.rect
            # UIA 坐标是虚拟桌面物理像素
            # 减去屏幕物理原点再除以 DPR 得到覆盖层本地逻辑坐标
            lx = int((left - ox) / s)
            ly = int((top - oy) / s)
            lw = int((right - left) / s)
            lh = int((bottom - top) / s)

            if self._config.mode == "line":
                lh_draw = max(1, int(self._config.line_height / s))
                painter.fillRect(lx, ly - lh_draw, lw, lh_draw, QColor(r, g, b))
            else:
                alpha = self._config.opacity
                painter.fillRect(lx, ly, lw, lh, QColor(r, g, b, alpha))
        painter.end()

    def _on_update_icons(self, icons: list):
        self._icons = icons
        self.update()

    def _on_update_config(self, config: Config):
        self._config = config
        if config.screen_index != self._target_screen_index:
            self._apply_screen(config.screen_index)
