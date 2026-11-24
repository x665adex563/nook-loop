import ctypes
import threading
from ctypes import wintypes
from contextlib import ExitStack

from core.window_manager import is_window


user32 = ctypes.windll.user32

user32.PostMessageW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
]
user32.PostMessageW.restype = wintypes.BOOL

user32.ClientToScreen.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.POINT)
]

user32.ClientToScreen.restype = wintypes.BOOL

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101

WM_MOUSEMOVE = 0x0200
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202

KEY_MAP = {
    "BACKSPACE": 0x08,
    "TAB": 0x09,
    "ENTER": 0x0D,
    "SHIFT": 0x10,
    "CTRL": 0x11,
    "ALT": 0x12,
    "ESC": 0x1B,
    "ESCAPE": 0x1B,
    "SPACE": 0x20,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "DELETE": 0x2E
}

KEY_MAP.update({
    f"F{i}": 0x6F + i
    for i in range(1, 13)
})


def resolve_key(key):
    key = key.strip().upper()

    if key in KEY_MAP:
        return KEY_MAP[key]

    if len(key) == 1 and key in (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    ):
        return ord(key)

    raise ValueError(f"不支援的按鍵：{key}")


def resolve_keys(key):
    return list(dict.fromkeys(
        resolve_key(part)
        for part in key.split("+")
    ))


def post_message(hwnd, message, wparam, lparam):
    if not user32.PostMessageW(
        hwnd, message, wparam, lparam
    ):
        raise RuntimeError("無法傳送視窗訊息")


class BackgroundInput:
    def __init__(self, frida_manager):
        self.frida = frida_manager
        self.lock = threading.Lock()

    def send_key(
        self, hwnd, pid, key,
        hold_ms=120, stop_event=None
    ):
        stop_event = stop_event or threading.Event()

        with self.lock:
            if stop_event.is_set():
                return

            if not is_window(hwnd):
                raise RuntimeError("目標視窗已關閉")

            keys = resolve_keys(key)

            def release_key(vk, up_param):
                try:
                    self.frida.set_key(pid, vk, False)
                finally:
                    post_message(
                        hwnd, WM_KEYUP, vk, up_param
                    )

            with ExitStack() as stack:
                for vk in keys:
                    if stop_event.is_set():
                        return

                    scan = user32.MapVirtualKeyW(vk, 0)
                    down_param = (scan << 16) | 1

                    if vk in (
                        0x25, 0x26, 0x27, 0x28, 0x2E
                    ):
                        down_param |= 1 << 24

                    up_param = (
                        down_param | (1 << 30) | (1 << 31)
                    )

                    self.frida.set_key(pid, vk, True)

                    stack.callback(
                        release_key, vk, up_param
                    )

                    post_message(
                        hwnd, WM_KEYDOWN, vk, down_param
                    )

                stop_event.wait(hold_ms / 1000)

    def click(self, hwnd, pid, x, y, stop_event=None):
        stop_event = stop_event or threading.Event()

        with self.lock:
            if stop_event.is_set():
                return

            if not is_window(hwnd):
                raise RuntimeError("目標視窗已關閉")

            point = wintypes.POINT(int(x), int(y))

            if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
                raise RuntimeError("無法轉換滑鼠座標")

            self.frida.set_cursor(
                pid,
                hwnd,
                point.x,
                point.y,
                int(x),
                int(y)
            )

            if stop_event is not None and stop_event.is_set():
                return

            lparam = (
                (int(y) & 0xFFFF) << 16
            ) | (int(x) & 0xFFFF)

            if stop_event.wait(0.02):
                return

            post_message(
                hwnd, WM_LBUTTONDOWN, 1, lparam
            )

            try:
                stop_event.wait(0.05)
            finally:
                post_message(
                    hwnd, WM_LBUTTONUP, 0, lparam
                )
