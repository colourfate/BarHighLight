import ctypes
import sys
import threading

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from config_manager import ConfigManager
from taskbar_monitor import TaskbarMonitor
from overlay_window import OverlayWindow
from tray_app import TrayApp


class App:
    def __init__(self):
        self._config_mgr = ConfigManager()
        self._overlay = OverlayWindow(self._config_mgr.config)
        self._monitor = TaskbarMonitor()
        self._tray = None
        self._running = True

    def run(self) -> None:
        self._overlay.create()

        self._tray = TrayApp(
            config_mgr=self._config_mgr,
            on_toggle=self._on_toggle,
            on_mode_change=self._on_mode_change,
            on_edit_config=self._on_edit_config,
            on_refresh=self._on_refresh,
            on_exit=self._on_exit,
        )

        tray_thread = threading.Thread(target=self._tray.run, daemon=True)
        tray_thread.start()

        self._config_mgr.register_on_change(self._on_config_change)

        interval = self._config_mgr.config.refresh_interval / 1000.0
        while self._running:
            try:
                if self._config_mgr.config.enabled:
                    icons = self._monitor.refresh()
                    self._overlay.draw(icons)
            except Exception:
                pass
            try:
                interval = self._config_mgr.config.refresh_interval / 1000.0
            except Exception:
                interval = 0.8
            import time
            time.sleep(interval)

    def _on_config_change(self) -> None:
        self._overlay.update_config(self._config_mgr.config)
        if self._config_mgr.config.enabled:
            icons = self._monitor.refresh()
            self._overlay.draw(icons)

    def _on_toggle(self) -> None:
        if self._config_mgr.config.enabled:
            icons = self._monitor.refresh()
            self._overlay.draw(icons)
        else:
            self._overlay.draw([])

    def _on_mode_change(self, mode: str) -> None:
        if self._config_mgr.config.enabled:
            icons = self._monitor.refresh()
            self._overlay.draw(icons)

    def _on_edit_config(self) -> None:
        try:
            from config_editor import open_editor
            open_editor(self._config_mgr)
        except Exception:
            pass

    def _on_refresh(self) -> None:
        if self._config_mgr.config.enabled:
            icons = self._monitor.refresh()
            self._overlay.draw(icons)

    def _on_exit(self) -> None:
        self._running = False
        self._overlay.destroy()
        sys.exit(0)


def main():
    app = App()
    app.run()


if __name__ == "__main__":
    main()
