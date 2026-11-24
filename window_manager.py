import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32


def get_windows():
    windows = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def callback(hwnd, lparam):
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True

        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        windows.append({
            "hwnd": hwnd,
            "pid": pid.value,
            "title": title.value
        })

        return True

    user32.EnumWindows(callback, 0)

    return windows


if __name__ == "__main__":
    for window in get_windows():
        print(
            f"HWND: {window['hwnd']} | "
            f"PID: {window['pid']} | "
            f"{window['title']}"
        )
