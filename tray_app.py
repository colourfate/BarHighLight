import sys
import threading
import logging
from typing import Callable
from PIL import Image, ImageDraw
import pystray

from config_manager import ConfigManager

log = logging.getLogger("BarHighLight.tray")

_tray_app_instance: "TrayApp" = None


def _create_icon_image(color: str = "#4CAF50") -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    h = color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    draw.rounded_rectangle([4, 4, 60, 60], radius=8, fill=(r, g, b, 255))
    draw.text((16, 12), "HL", fill=(255, 255, 255, 255))
    return img


class TrayApp:
    def __init__(
        self,
        config_mgr: ConfigManager,
        on_toggle: Callable[[], None],
        on_mode_change: Callable[[str], None],
        on_edit_config: Callable[[], None],
        on_refresh: Callable[[], None],
        on_exit: Callable[[], None],
    ):
        global _tray_app_instance
        _tray_app_instance = self

        self._config_mgr = config_mgr
        self._on_toggle = on_toggle
        self._on_mode_change = on_mode_change
        self._on_edit_config = on_edit_config
        self._on_refresh = on_refresh
        self._on_exit = on_exit
        self._icon: pystray.Icon = None
        self._build_icon()

    def _build_icon(self) -> None:
        cfg = self._config_mgr.config
        icon_img = _create_icon_image("#4CAF50" if cfg.enabled else "#9E9E9E")

        menu = pystray.Menu(
            pystray.MenuItem(
                "启用高亮",
                self._menu_toggle,
                checked=lambda item: self._config_mgr.config.enabled,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "横线模式",
                lambda: self._menu_set_mode("line"),
                checked=lambda item: self._config_mgr.config.mode == "line",
                radio=True,
            ),
            pystray.MenuItem(
                "半透明覆盖模式",
                lambda: self._menu_set_mode("overlay"),
                checked=lambda item: self._config_mgr.config.mode == "overlay",
                radio=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("编辑颜色配置", self._menu_edit_config),
            pystray.MenuItem("刷新状态", self._menu_refresh),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "开机自启",
                self._menu_autostart,
                checked=lambda item: self._config_mgr.config.auto_start,
            ),
            pystray.MenuItem("退出", self._menu_exit),
        )

        self._icon = pystray.Icon(
            "BarHighLight",
            icon_img,
            "BarHighLight",
            menu,
        )

    def _update_icon_image(self) -> None:
        cfg = self._config_mgr.config
        color = "#4CAF50" if cfg.enabled else "#9E9E9E"
        self._icon.icon = _create_icon_image(color)

    def _menu_toggle(self) -> None:
        self._config_mgr.set_enabled(not self._config_mgr.config.enabled)
        self._update_icon_image()
        self._on_toggle()

    def _menu_set_mode(self, mode: str) -> None:
        self._config_mgr.set_mode(mode)
        self._on_mode_change(mode)

    def _menu_edit_config(self) -> None:
        threading.Thread(target=self._on_edit_config, daemon=True).start()

    def _menu_refresh(self) -> None:
        threading.Thread(target=self._on_refresh, daemon=True).start()

    def _menu_autostart(self) -> None:
        self._config_mgr.set_auto_start(not self._config_mgr.config.auto_start)

    def _menu_exit(self) -> None:
        self._on_exit()

    def run(self) -> None:
        log.info("系统托盘图标已启动")
        self._icon.run()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
