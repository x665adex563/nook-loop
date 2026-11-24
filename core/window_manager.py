import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32

ENUMPROC = ctypes.WINFUNCTYPE(
    wintypes.BOOL,
    wintypes.HWND,
    wintypes.LPARAM
)

user32.EnumWindows.argtypes = [ENUMPROC, wintypes.LPARAM]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [
    wintypes.HWND,
    wintypes.LPWSTR,
    ctypes.c_int
]
user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.DWORD)
]


def get_windows():
    windows = []

    @ENUMPROC
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

    return sorted(
        windows,
        key=lambda window: window["title"].casefold()
    )


def is_window(hwnd):
    return bool(user32.IsWindow(hwnd))


def find_window(title):
    matches = [
        window for window in get_windows()
        if window["title"] == title
    ]

    if len(matches) != 1:
        return None

    return matches[0]


if __name__ == "__main__":
    for window in get_windows():
        print(
            f"HWND: {window['hwnd']} | "
            f"PID: {window['pid']} | "
            f"{window['title']}"
        )
