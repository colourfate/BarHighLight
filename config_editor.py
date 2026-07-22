import ctypes
import ctypes.wintypes as wintypes
import logging

from PyQt6.QtCore import Qt, QFileInfo
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel,
    QLineEdit, QColorDialog, QMessageBox, QComboBox, QScrollArea,
    QFileIconProvider,
)

from config_manager import ConfigManager
from taskbar_monitor import TaskbarMonitor

log = logging.getLogger("BarHighLight.editor")


def _color_swatch(color_hex: str, size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(color_hex))
    return QIcon(pixmap)


PRESET_COLORS = [
    ("#FF5722", "橙红"),
    ("#2196F3", "蓝色"),
    ("#4CAF50", "绿色"),
    ("#9C27B0", "紫色"),
    ("#FF9800", "橙色"),
    ("#E91E63", "粉色"),
]


def _get_process_icon(hwnd: int):
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    if not pid.value:
        return None

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return None

    try:
        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            provider = QFileIconProvider()
            return provider.icon(QFileInfo(buf.value))
    except Exception:
        pass
    finally:
        kernel32.CloseHandle(handle)

    return None


class ConfigEditor(QWidget):
    def __init__(self, config_mgr: ConfigManager):
        super().__init__()
        self._config_mgr = config_mgr
        self.setWindowTitle("BarHighLight - 颜色配置")
        self.setFixedSize(520, 420)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Window
        )
        self._list = None
        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        btn_add = QPushButton("添加")
        btn_add.setFixedWidth(80)
        btn_add.clicked.connect(self._add_entry)
        btn_edit = QPushButton("修改颜色")
        btn_edit.setFixedWidth(80)
        btn_edit.clicked.connect(self._edit_color)
        btn_delete = QPushButton("删除")
        btn_delete.setFixedWidth(80)
        btn_delete.clicked.connect(self._delete_entry)
        toolbar.addWidget(btn_add)
        toolbar.addWidget(btn_edit)
        toolbar.addWidget(btn_delete)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._list = QListWidget()
        self._list.setFont(QApplication.font())
        self._list.itemDoubleClicked.connect(self._edit_color)
        layout.addWidget(self._list)

        bottom = QHBoxLayout()
        hint = QLabel("提示: 双击条目可快速修改颜色")
        hint.setStyleSheet("color: gray;")
        btn_close = QPushButton("关闭")
        btn_close.setFixedWidth(80)
        btn_close.clicked.connect(self.close)
        bottom.addWidget(hint)
        bottom.addStretch()
        bottom.addWidget(btn_close)
        layout.addLayout(bottom)

    def _refresh_list(self) -> None:
        self._list.clear()
        for proc, color in sorted(self._config_mgr.config.highlights.items()):
            item = QListWidgetItem(f"  {color}    {proc}")
            item.setIcon(_color_swatch(color))
            item.setData(Qt.ItemDataRole.UserRole, (proc, color))
            self._list.addItem(item)

    def _add_entry(self) -> None:
        dialog = QWidget(self, Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        dialog.setWindowTitle("添加进程")
        dialog.setFixedSize(340, 120)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("进程名 (如 chrome.exe):"))
        entry = QLineEdit()
        entry.setPlaceholderText("chrome.exe")
        entry.setFocus()
        layout.addWidget(entry)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton("确定")
        btn_cancel = QPushButton("取消")
        btn_row.addWidget(btn_ok)
        btn_row.addWidget(btn_cancel)
        layout.addLayout(btn_row)

        def confirm():
            name = entry.text().strip()
            if not name:
                QMessageBox.warning(dialog, "提示", "请输入进程名")
                return
            if not name.lower().endswith(".exe"):
                name += ".exe"
            color = "#4CAF50"
            chosen = QColorDialog.getColor(QColor(color), dialog, "选择颜色")
            if chosen.isValid():
                color = chosen.name()
            self._config_mgr.set_highlight(name.lower(), color)
            log.info("新增颜色配置: %s -> %s", name.lower(), color)
            self._refresh_list()
            dialog.close()

        btn_ok.clicked.connect(confirm)
        btn_cancel.clicked.connect(dialog.close)
        dialog.show()

    def _edit_color(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        proc, old_color = item.data(Qt.ItemDataRole.UserRole)
        chosen = QColorDialog.getColor(QColor(old_color), self, f"选择 {proc} 的颜色")
        if chosen.isValid():
            new_color = chosen.name()
            self._config_mgr.set_highlight(proc, new_color)
            log.info("修改颜色: %s %s -> %s", proc, old_color, new_color)
            self._refresh_list()

    def _delete_entry(self) -> None:
        item = self._list.currentItem()
        if not item:
            return
        proc, _ = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, "确认", f"删除 {proc} 的颜色配置?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._config_mgr.remove_highlight(proc)
            log.info("删除颜色配置: %s", proc)
            self._refresh_list()

    def closeEvent(self, event):
        log.info("配置编辑器已关闭")
        event.accept()


class TaskbarColorEditor(QWidget):
    def __init__(self, config_mgr: ConfigManager):
        super().__init__()
        self._config_mgr = config_mgr
        self._items: list[tuple[str, QComboBox]] = []
        self.setWindowTitle("BarHighLight - 任务栏图标颜色配置")
        self.setFixedSize(520, 480)
        self.setWindowFlags(
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Window
        )
        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        title = QLabel("当前任务栏图标:")
        title.setStyleSheet("font-weight: bold;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._list_widget)
        layout.addWidget(scroll)

        bottom = QHBoxLayout()
        hint = QLabel("确认后将在下次刷新时生效")
        hint.setStyleSheet("color: gray;")
        btn_confirm = QPushButton("确定")
        btn_confirm.setFixedWidth(80)
        btn_confirm.clicked.connect(self._confirm)
        btn_cancel = QPushButton("取消")
        btn_cancel.setFixedWidth(80)
        btn_cancel.clicked.connect(self.close)
        bottom.addWidget(hint)
        bottom.addStretch()
        bottom.addWidget(btn_confirm)
        bottom.addWidget(btn_cancel)
        layout.addLayout(bottom)

    def _refresh_list(self) -> None:
        for i in reversed(range(self._list_layout.count())):
            widget = self._list_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        self._items.clear()

        monitor = TaskbarMonitor()
        icons = monitor.refresh()
        highlights = self._config_mgr.config.highlights

        if not icons:
            empty = QLabel("未检测到任务栏图标")
            empty.setStyleSheet("color: gray;")
            self._list_layout.addWidget(empty)
            return

        for icon in icons:
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(4, 2, 4, 2)

            icon_label = QLabel()
            icon_label.setFixedSize(20, 20)
            process_icon = _get_process_icon(icon.hwnd)
            if process_icon:
                icon_label.setPixmap(process_icon.pixmap(16, 16))
            else:
                pixmap = QPixmap(16, 16)
                pixmap.fill(QColor(128, 128, 128))
                icon_label.setPixmap(pixmap)
            row_layout.addWidget(icon_label)

            name_label = QLabel(icon.process_name)
            name_label.setMinimumWidth(160)
            row_layout.addWidget(name_label)

            combo = QComboBox()
            combo.setFixedWidth(200)
            self._setup_color_combo(combo, icon.process_name)
            row_layout.addWidget(combo)

            self._list_layout.addWidget(row)
            self._items.append((icon.process_name, combo))

        log.info("任务栏图标颜色编辑器: 加载 %d 个图标", len(icons))

    def _setup_color_combo(self, combo: QComboBox, process_name: str) -> None:
        combo.addItem("无颜色", None)
        for hex_color, name in PRESET_COLORS:
            combo.addItem(_color_swatch(hex_color), f"{hex_color} {name}", hex_color)

        current_color = self._config_mgr.get_color(process_name)
        if current_color:
            for i in range(combo.count()):
                if combo.itemData(i) == current_color:
                    combo.setCurrentIndex(i)
                    break

    def _confirm(self) -> None:
        for process_name, combo in self._items:
            color = combo.currentData()
            if color:
                self._config_mgr.set_highlight(process_name, color)
            else:
                self._config_mgr.remove_highlight(process_name)
        log.info("任务栏图标颜色配置已保存")
        self.close()

    def closeEvent(self, event):
        log.info("任务栏图标颜色编辑器已关闭")
        event.accept()
