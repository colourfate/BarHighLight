import ctypes
import logging

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QColor
from PyQt6.QtWidgets import QWidget, QApplication

from config_manager import Config

log = logging.getLogger("BarHighLight.overlay")

WS_EX_TRANSPARENT = 0x00000020
GWL_EXSTYLE = -20
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79


def _parse_color(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    if len(h) == 6:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 128, 128, 128


class OverlayWindow(QWidget):
    _update_icons_signal = pyqtSignal(list)
    _update_config_signal = pyqtSignal(object)

    def __init__(self, config: Config):
        super().__init__()
        self._config = config
        self._icons: list = []
        self._dpi_scale: float = 1.0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        user32 = ctypes.windll.user32
        phys_w = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
        phys_h = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
        self.setGeometry(0, 0, phys_w, phys_h)

        screen = QApplication.primaryScreen().geometry()
        if screen.width() > 0:
            self._dpi_scale = phys_w / screen.width()

        self._update_icons_signal.connect(self._on_update_icons)
        self._update_config_signal.connect(self._on_update_config)
        log.info("覆盖层初始化: 物理=%dx%d, 逻辑=%dx%d, 缩放=%.2f",
                 phys_w, phys_h, screen.width(), screen.height(), self._dpi_scale)

    def create(self) -> None:
        self.show()
        log.info("覆盖层窗口已创建")

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
        for icon in self._icons:
            color_hex = self._config.highlights.get(icon.process_name, "#808080")
            r, g, b = _parse_color(color_hex)
            left, top, right, bottom = icon.rect
            lx = int(left / s)
            ly = int(top / s)
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
