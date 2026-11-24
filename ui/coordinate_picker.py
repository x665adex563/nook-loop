import ctypes
import tkinter as tk
from ctypes import wintypes


user32 = ctypes.windll.user32

user32.GetClientRect.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.RECT)
]

user32.ScreenToClient.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.POINT)
]

user32.ClientToScreen.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.POINT)
]

user32.SetForegroundWindow.argtypes = [
    wintypes.HWND
]

user32.GetForegroundWindow.restype = wintypes.HWND

user32.ShowWindow.argtypes = [
    wintypes.HWND,
    ctypes.c_int
]

SW_RESTORE = 9


def pick_coordinate(parent, hwnd, callback):
    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.SetForegroundWindow(hwnd)

    def restore():
        parent.deiconify()
        parent.lift()
        parent.focus_force()

    def open_overlay():
        overlay = None

        try:
            if user32.GetForegroundWindow() != hwnd:
                user32.SetForegroundWindow(hwnd)

            if user32.GetForegroundWindow() != hwnd:
                raise RuntimeError("無法切換至目標視窗")

            parent.withdraw()

            rect = wintypes.RECT()

            if not user32.GetClientRect(
                hwnd, ctypes.byref(rect)
            ):
                raise RuntimeError("無法取得視窗大小")

            point = wintypes.POINT(0, 0)

            if not user32.ClientToScreen(
                hwnd, ctypes.byref(point)
            ):
                raise RuntimeError("無法取得視窗位置")

            width = rect.right - rect.left
            height = rect.bottom - rect.top

            if width <= 0 or height <= 0:
                raise RuntimeError("目標視窗大小無效")

            overlay = tk.Toplevel(parent)
            overlay.withdraw()
            overlay.overrideredirect(True)

            overlay.geometry(
                f"{width}x{height}"
                f"{point.x:+d}{point.y:+d}"
            )

            overlay.configure(
                background="black",
                cursor="crosshair"
            )

            overlay.attributes("-topmost", True)
            overlay.attributes("-alpha", 0.08)

            selected = None

            def finish(position=None):
                overlay.destroy()
                restore()

                if position is not None:
                    callback(*position)

            def on_press(event):
                nonlocal selected

                position = wintypes.POINT(
                    event.x_root,
                    event.y_root
                )

                if user32.ScreenToClient(
                    hwnd, ctypes.byref(position)
                ):
                    selected = (
                        position.x,
                        position.y
                    )

                return "break"

            def on_release(event):
                if selected is not None:
                    finish(selected)

                return "break"

            overlay.bind("<ButtonPress-1>", on_press)
            overlay.bind("<ButtonRelease-1>", on_release)
            overlay.bind("<Escape>", lambda event: finish())

            overlay.deiconify()
            overlay.lift()
            overlay.focus_force()
            overlay.grab_set()

        except Exception as error:
            if overlay is not None:
                overlay.destroy()

            restore()

            from tkinter import messagebox

            messagebox.showerror(
                "擷取失敗",
                str(error),
                parent=parent
            )

    parent.after(200, open_overlay)
