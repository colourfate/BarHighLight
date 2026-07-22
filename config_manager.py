import json
import os
import sys
import logging
from dataclasses import dataclass, field
from typing import Callable, Optional

log = logging.getLogger("BarHighLight.config")


@dataclass
class Config:
    enabled: bool = True
    mode: str = "line"  # "line" or "overlay"
    opacity: int = 100
    line_height: int = 4
    refresh_interval: int = 800
    auto_start: bool = False
    debug: bool = False
    highlights: dict = field(default_factory=lambda: {
        "chrome.exe": "#FF5722",
        "code.exe": "#2196F3",
        "explorer.exe": "#4CAF50",
        "windowsterminal.exe": "#9C27B0",
        "taskmgr.exe": "#FF9800",
        "v2rayn": "#E91E63",
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
            cfg.debug = data.get("debug", cfg.debug)
            cfg.highlights = data.get("highlights", cfg.highlights)
            log.info("配置已加载: %s", path)
            log.debug("配置内容: enabled=%s, mode=%s, debug=%s, highlights=%d项",
                       cfg.enabled, cfg.mode, cfg.debug, len(cfg.highlights))
        except (json.JSONDecodeError, OSError) as e:
            log.warning("配置文件读取失败，使用默认配置: %s", e)
            cfg = _default_config()
    else:
        log.info("配置文件不存在，使用默认配置")
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
        "debug": cfg.debug,
        "highlights": cfg.highlights,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    log.debug("配置已保存: %s", path)


class ConfigManager:
    def __init__(self):
        self.config: Config = load_config()
        self._on_change_callbacks: list[Callable[[], None]] = []

    def register_on_change(self, callback: Callable[[], None]) -> None:
        self._on_change_callbacks.append(callback)

    def _notify_change(self) -> None:
        for cb in self._on_change_callbacks:
            try:
                cb()
            except Exception as e:
                log.error("配置变更回调执行失败: %s", e)

    def reload(self) -> None:
        self.config = load_config()
        self._notify_change()

    def save(self) -> None:
        save_config(self.config)
        self._notify_change()

    def set_enabled(self, enabled: bool) -> None:
        self.config.enabled = enabled
        log.info("高亮已%s", "启用" if enabled else "禁用")
        self.save()

    def set_mode(self, mode: str) -> None:
        self.config.mode = mode
        log.info("显示模式切换为: %s", mode)
        self.save()

    def set_highlight(self, process_name: str, color: str) -> None:
        self.config.highlights[process_name] = color
        log.info("设置颜色: %s -> %s", process_name, color)
        self.save()

    def remove_highlight(self, process_name: str) -> None:
        self.config.highlights.pop(process_name, None)
        log.info("移除颜色配置: %s", process_name)
        self.save()

    def get_color(self, process_name: str) -> Optional[str]:
        return self.config.highlights.get(process_name)

    def set_auto_start(self, auto_start: bool) -> None:
        self.config.auto_start = auto_start
        log.info("开机自启: %s", "启用" if auto_start else "禁用")
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
                log.debug("注册表开机自启已写入: %s", exe_path)
            else:
                try:
                    winreg.DeleteValue(key, app_name)
                    log.debug("注册表开机自启已删除")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except OSError as e:
            log.error("注册表操作失败: %s", e)
