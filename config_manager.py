import json
import os
import sys
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Config:
    enabled: bool = True
    mode: str = "line"  # "line" or "overlay"
    opacity: int = 200
    line_height: int = 4
    refresh_interval: int = 800
    auto_start: bool = False
    highlights: dict = field(default_factory=lambda: {
        "chrome.exe": "#FF5722",
        "code.exe": "#2196F3",
        "explorer.exe": "#4CAF50",
        "python.exe": "#9C27B0",
    })


def _config_path() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config.json")


def _default_config() -> Config:
    return Config()


def load_config() -> Config:
    path = _config_path()
    cfg = _default_config()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg.enabled = data.get("enabled", cfg.enabled)
            cfg.mode = data.get("mode", cfg.mode)
            cfg.opacity = data.get("opacity", cfg.opacity)
            cfg.line_height = data.get("line_height", cfg.line_height)
            cfg.refresh_interval = data.get("refresh_interval", cfg.refresh_interval)
            cfg.auto_start = data.get("auto_start", cfg.auto_start)
            cfg.highlights = data.get("highlights", cfg.highlights)
        except (json.JSONDecodeError, OSError):
            cfg = _default_config()
    return cfg


def save_config(cfg: Config) -> None:
    path = _config_path()
    data = {
        "enabled": cfg.enabled,
        "mode": cfg.mode,
        "opacity": cfg.opacity,
        "line_height": cfg.line_height,
        "refresh_interval": cfg.refresh_interval,
        "auto_start": cfg.auto_start,
        "highlights": cfg.highlights,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


class ConfigManager:
    def __init__(self):
        self.config: Config = load_config()
        self._on_change_callbacks: list[Callable[[], None]] = []

    def register_on_change(self, callback: Callable[[], None]) -> None:
        self._on_change_callbacks.append(callback)

    def _notify_change(self) -> None:
        for cb in self._on_change_callbacks:
            cb()

    def reload(self) -> None:
        self.config = load_config()
        self._notify_change()

    def save(self) -> None:
        save_config(self.config)
        self._notify_change()

    def set_enabled(self, enabled: bool) -> None:
        self.config.enabled = enabled
        self.save()

    def set_mode(self, mode: str) -> None:
        self.config.mode = mode
        self.save()

    def set_highlight(self, process_name: str, color: str) -> None:
        self.config.highlights[process_name] = color
        self.save()

    def remove_highlight(self, process_name: str) -> None:
        self.config.highlights.pop(process_name, None)
        self.save()

    def get_color(self, process_name: str) -> Optional[str]:
        return self.config.highlights.get(process_name)

    def set_auto_start(self, auto_start: bool) -> None:
        self.config.auto_start = auto_start
        self.save()
        self._update_autostart_registry()

    def _update_autostart_registry(self) -> None:
        import winreg
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        app_name = "BarHighLight"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                                 winreg.KEY_SET_VALUE)
            if self.config.auto_start:
                if getattr(sys, "frozen", False):
                    exe_path = sys.executable
                else:
                    exe_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except OSError:
            pass
