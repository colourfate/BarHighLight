import ctypes
import ctypes.wintypes as wintypes
import threading
import logging
from typing import Optional

from config_manager import Config
from taskbar_monitor import TaskbarIcon

log = logging.getLogger("BarHighLight.overlay")


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", ctypes.c_long), ("cy", ctypes.c_long)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [
        ("BlendOp", ctypes.c_byte),
        ("SourceConstantAlpha", ctypes.c_byte),
        ("AlphaFormat", ctypes.c_byte),
        ("Reserved", ctypes.c_byte),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long), ("top", ctypes.c_long),
        ("right", ctypes.c_long), ("bottom", ctypes.c_long),
    ]


user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

user32.GetDC.argtypes = [wintypes.HWND]
user32.GetDC.restype = wintypes.HDC

user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
user32.ReleaseDC.restype = ctypes.c_int

user32.FillRect.argtypes = [wintypes.HDC, ctypes.POINTER(RECT), wintypes.HBRUSH]
user32.FillRect.restype = ctypes.c_int

user32.UpdateLayeredWindow.argtypes = [
    wintypes.HWND, wintypes.HDC, ctypes.POINTER(POINT),
    ctypes.POINTER(SIZE), wintypes.HDC, ctypes.POINTER(POINT),
    wintypes.DWORD, ctypes.POINTER(BLENDFUNCTION), wintypes.DWORD
]
user32.UpdateLayeredWindow.restype = wintypes.BOOL

gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC

gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP

gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.SelectObject.restype = wintypes.HGDIOBJ

gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteObject.restype = wintypes.BOOL

gdi32.DeleteDC.argtypes = [wintypes.HDC]
gdi32.DeleteDC.restype = wintypes.BOOL

gdi32.CreateSolidBrush.argtypes = [wintypes.COLORREF]
gdi32.CreateSolidBrush.restype = wintypes.HBRUSH

user32.DefWindowProcW.argtypes = [wintypes.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
user32.DefWindowProcW.restype = ctypes.c_ssize_t

user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint]
user32.GetMessageW.restype = wintypes.BOOL

user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.TranslateMessage.restype = wintypes.BOOL

user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
user32.DispatchMessageW.restype = ctypes.c_ssize_t

user32.PostMessageW.argtypes = [wintypes.HWND, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
user32.PostMessageW.restype = wintypes.BOOL

user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t

user32.SetLayeredWindowAttributes.argtypes = [wintypes.HWND, wintypes.COLORREF, ctypes.c_byte, ctypes.c_uint]
user32.SetLayeredWindowAttributes.restype = wintypes.BOOL

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

user32.CreateWindowExW.argtypes = [
    ctypes.c_uint, wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_uint,
    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
    wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID
]
user32.CreateWindowExW.restype = wintypes.HWND

WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

LWA_ALPHA = 0x2
ULW_ALPHA = 0x2
WM_APP = 0x8000
WM_DRAW_OVERLAY = WM_APP + 1
GWL_WNDPROC = -4
SW_SHOWNA = 8


def _parse_color(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    if len(h) == 6:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 128, 128, 128


class OverlayWindow:
    def __init__(self, config: Config):
        self._config = config
        self._hwnd: int = 0
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._icons_to_draw: list = []
        self._draw_lock = threading.Lock()
        self._running = False
        self._screen_w = user32.GetSystemMetrics(0)
        self._screen_h = user32.GetSystemMetrics(1)
        self._wndproc_cb = None

    def create(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._window_thread, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)
        if self._hwnd:
            log.info("覆盖层窗口创建成功 hwnd=0x%X (%dx%d)", self._hwnd, self._screen_w, self._screen_h)
        else:
            log.error("覆盖层窗口创建失败！")

    def destroy(self) -> None:
        self._running = False
        if self._hwnd:
            user32.PostMessageW(self._hwnd, 0x0010, 0, 0)
            log.info("覆盖层窗口已销毁")
        if self._thread:
            self._thread.join(timeout=3)
            self._thread = None

    def update_config(self, config: Config) -> None:
        self._config = config
        log.debug("覆盖层配置已更新: mode=%s, opacity=%d", config.mode, config.opacity)

    def draw(self, icons: list) -> None:
        if not self._hwnd or not self._running:
            return
        with self._draw_lock:
            self._icons_to_draw = list(icons)
        user32.PostMessageW(self._hwnd, WM_DRAW_OVERLAY, 0, 0)

    def _window_thread(self) -> None:
        self._screen_w = user32.GetSystemMetrics(0)
        self._screen_h = user32.GetSystemMetrics(1)
        hInst = kernel32.GetModuleHandleW(None)

        self._hwnd = user32.CreateWindowExW(
            WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST |
            WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
            "STATIC", None,
            WS_POPUP,
            0, 0, self._screen_w, self._screen_h,
            0, 0, hInst, 0
        )

        if not self._hwnd:
            log.error("CreateWindowExW 失败, 错误=%d", kernel32.GetLastError())
            self._ready.set()
            return

        WNDPROCTYPE = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, wintypes.HWND, ctypes.c_uint,
            ctypes.c_size_t, ctypes.c_ssize_t
        )

        def wndproc(hwnd, msg, wparam, lparam):
            if msg == WM_DRAW_OVERLAY:
                self._do_draw()
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc_cb = WNDPROCTYPE(wndproc)
        user32.SetWindowLongPtrW(
            self._hwnd, GWL_WNDPROC,
            ctypes.c_ssize_t(ctypes.cast(self._wndproc_cb, ctypes.c_void_p).value)
        )

        user32.SetLayeredWindowAttributes(self._hwnd, 0, 255, LWA_ALPHA)
        user32.ShowWindow(self._hwnd, SW_SHOWNA)
        log.debug("覆盖层窗口线程启动, 消息循环开始")
        self._ready.set()

        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), 0, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def _do_draw(self) -> None:
        if not self._hwnd:
            return

        with self._draw_lock:
            icons = list(self._icons_to_draw)

        screen_dc = user32.GetDC(0)
        hdc_mem = gdi32.CreateCompatibleDC(screen_dc)
        hbmp = gdi32.CreateCompatibleBitmap(screen_dc, self._screen_w, self._screen_h)
        old_bmp = gdi32.SelectObject(hdc_mem, hbmp)

        black_brush = gdi32.CreateSolidBrush(0x00000000)
        user32.FillRect(hdc_mem, ctypes.byref(RECT(0, 0, self._screen_w, self._screen_h)), black_brush)
        gdi32.DeleteObject(black_brush)

        default_color = "#808080"
        for icon in icons:
            color_hex = self._config.highlights.get(icon.process_name, default_color)
            r, g, b = _parse_color(color_hex)
            color_ref = r | (g << 8) | (b << 16)
            left, top, right, bottom = icon.rect

            if self._config.mode == "line":
                line_h = self._config.line_height
                line_top = top - line_h
                if line_top < 0:
                    line_top = 0
                brush = gdi32.CreateSolidBrush(color_ref)
                user32.FillRect(hdc_mem, ctypes.byref(RECT(left, line_top, right, line_top + line_h)), brush)
                gdi32.DeleteObject(brush)
            else:
                alpha = self._config.opacity
                r_a = int(r * alpha / 255)
                g_a = int(g * alpha / 255)
                b_a = int(b * alpha / 255)
                blend_ref = r_a | (g_a << 8) | (b_a << 16) | (alpha << 24)
                brush = gdi32.CreateSolidBrush(blend_ref)
                user32.FillRect(hdc_mem, ctypes.byref(RECT(left, top, right, bottom)), brush)
                gdi32.DeleteObject(brush)

        pt = POINT(0, 0)
        sz = SIZE(self._screen_w, self._screen_h)
        bf = BLENDFUNCTION(0, 255, 1, 0)
        user32.UpdateLayeredWindow(
            self._hwnd, screen_dc, ctypes.byref(pt),
            ctypes.byref(sz), hdc_mem, ctypes.byref(POINT(0, 0)),
            0, ctypes.byref(bf), ULW_ALPHA
        )

        gdi32.SelectObject(hdc_mem, old_bmp)
        gdi32.DeleteObject(hbmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(0, screen_dc)
        log.debug("绘制完成: %d 个图标, 模式=%s", len(icons), self._config.mode)
