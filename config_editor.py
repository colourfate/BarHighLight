import logging
import threading

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel,
    QLineEdit, QColorDialog, QMessageBox,
)

from config_manager import ConfigManager

log = logging.getLogger("BarHighLight.editor")


def _color_swatch(color_hex: str, size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(color_hex))
    return QIcon(pixmap)


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


def open_editor(config_mgr: ConfigManager) -> None:
    log.info("配置编辑器已打开")

    def _run():
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        editor = ConfigEditor(config_mgr)
        editor.show()
        app.exec()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
