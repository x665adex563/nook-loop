import ctypes
import threading
from ctypes import wintypes

from core.bg_input import resolve_key


user32 = ctypes.windll.user32

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000

MODIFIERS = {
    "ALT": 0x0001,
    "CTRL": 0x0002,
    "SHIFT": 0x0004,
    "WIN": 0x0008
}


class HotkeyManager:
    def __init__(self, callback):
        self.callback = callback
        self.thread = None
        self.stop_event = threading.Event()
        self.ready = threading.Event()
        self.errors = []

    def parse(self, hotkey):
        parts = hotkey.upper().replace(" ", "").split("+")

        modifiers = MOD_NOREPEAT

        for part in parts[:-1]:
            if part not in MODIFIERS:
                raise ValueError(f"無效的快捷鍵：{part}")

            modifiers |= MODIFIERS[part]

        return modifiers, resolve_key(parts[-1])

    def start(self, hotkeys):
        bindings = {}

        for hotkey in hotkeys:
            if not hotkey:
                continue

            binding = self.parse(hotkey)
            bindings[binding] = hotkey

        self.stop()

        self.stop_event.clear()
        self.ready.clear()
        self.errors = []

        self.thread = threading.Thread(
            target=self._listen,
            args=(bindings,),
            daemon=True
        )

        self.thread.start()
        self.ready.wait()

        return self.errors.copy()

    def _listen(self, bindings):
        registered = {}

        try:
            for index, (binding, hotkey) in enumerate(
                bindings.items(), start=1
            ):
                modifiers, vk = binding

                success = user32.RegisterHotKey(
                    None, index, modifiers, vk
                )

                if success:
                    registered[index] = hotkey

                else:
                    self.errors.append(
                        f"{hotkey}：快捷鍵註冊失敗，"
                        "可能已被其他程式使用"
                    )

            self.ready.set()

            message = wintypes.MSG()

            while not self.stop_event.is_set():
                while user32.PeekMessageW(
                    ctypes.byref(message),
                    None, 0, 0, 1
                ):
                    if message.message == WM_HOTKEY:
                        hotkey = registered.get(
                            message.wParam
                        )

                        if hotkey is not None:
                            self.callback(hotkey)

                self.stop_event.wait(0.02)

        finally:
            self.ready.set()

            for index in registered:
                user32.UnregisterHotKey(None, index)

    def stop(self):
        self.stop_event.set()

        if self.thread and self.thread.is_alive():
            self.thread.join()

        self.thread = None
