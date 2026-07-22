import tkinter as tk
from tkinter import colorchooser, messagebox

from config_manager import ConfigManager


class ConfigEditor:
    def __init__(self, config_mgr: ConfigManager):
        self._config_mgr = config_mgr
        self._root = tk.Tk()
        self._root.title("BarHighLight - 颜色配置")
        self._root.geometry("520x420")
        self._root.resizable(False, False)
        self._root.attributes("-topmost", True)
        self._listbox = None
        self._build_ui()
        self._refresh_list()

    def _build_ui(self) -> None:
        toolbar = tk.Frame(self._root)
        toolbar.pack(fill=tk.X, padx=8, pady=(8, 4))

        tk.Button(toolbar, text="添加", width=8, command=self._add_entry).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="修改颜色", width=8, command=self._edit_color).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="删除", width=8, command=self._delete_entry).pack(side=tk.LEFT, padx=2)

        list_frame = tk.Frame(self._root)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._listbox = tk.Listbox(
            list_frame, font=("Consolas", 11),
            yscrollcommand=scrollbar.set, selectmode=tk.SINGLE
        )
        self._listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self._listbox.yview)

        bottom = tk.Frame(self._root)
        bottom.pack(fill=tk.X, padx=8, pady=(4, 8))

        tk.Label(bottom, text="提示: 双击条目可快速修改颜色", fg="gray").pack(side=tk.LEFT)
        tk.Button(bottom, text="关闭", width=8, command=self._root.destroy).pack(side=tk.RIGHT, padx=2)

        self._listbox.bind("<Double-1>", lambda e: self._edit_color())

    def _refresh_list(self) -> None:
        self._listbox.delete(0, tk.END)
        highlights = self._config_mgr.config.highlights
        for proc, color in sorted(highlights.items()):
            self._listbox.insert(tk.END, f"  {color}    {proc}")

    def _add_entry(self) -> None:
        dialog = tk.Toplevel(self._root)
        dialog.title("添加进程")
        dialog.geometry("320x120")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grab_set()

        tk.Label(dialog, text="进程名 (如 chrome.exe):").pack(padx=12, pady=(12, 2), anchor=tk.W)
        proc_entry = tk.Entry(dialog, width=36)
        proc_entry.pack(padx=12, pady=2)
        proc_entry.focus_set()

        def confirm():
            name = proc_entry.get().strip()
            if not name:
                messagebox.showwarning("提示", "请输入进程名", parent=dialog)
                return
            if not name.lower().endswith(".exe"):
                name += ".exe"
            color = "#4CAF50"
            chooser_result = colorchooser.askcolor(
                initialcolor=color, title="选择颜色", parent=dialog
            )
            if chooser_result and chooser_result[1]:
                color = chooser_result[1]
            self._config_mgr.set_highlight(name.lower(), color)
            self._refresh_list()
            dialog.destroy()

        tk.Button(dialog, text="确定", width=10, command=confirm).pack(pady=8)

    def _edit_color(self) -> None:
        sel = self._listbox.curselection()
        if not sel:
            return
        item_text = self._listbox.get(sel[0]).strip()
        parts = item_text.split()
        if len(parts) < 2:
            return
        old_color = parts[0]
        proc_name = parts[1]

        chooser_result = colorchooser.askcolor(
            initialcolor=old_color, title=f"选择 {proc_name} 的颜色"
        )
        if chooser_result and chooser_result[1]:
            new_color = chooser_result[1]
            self._config_mgr.set_highlight(proc_name, new_color)
            self._refresh_list()

    def _delete_entry(self) -> None:
        sel = self._listbox.curselection()
        if not sel:
            return
        item_text = self._listbox.get(sel[0]).strip()
        parts = item_text.split()
        if len(parts) < 2:
            return
        proc_name = parts[1]
        if messagebox.askyesno("确认", f"删除 {proc_name} 的颜色配置?"):
            self._config_mgr.remove_highlight(proc_name)
            self._refresh_list()

    def show(self) -> None:
        self._root.mainloop()


def open_editor(config_mgr: ConfigManager) -> None:
    editor = ConfigEditor(config_mgr)
    editor.show()
