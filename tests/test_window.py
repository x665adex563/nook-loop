import tkinter as tk
import ctypes
from ctypes import wintypes

root = tk.Tk()
root.title("Background Input Test")
root.geometry("400x300")

count = 0

label = tk.Label(
    root,
    text="等待按鍵輸入...",
    font=("Arial", 18)
)
label.pack(pady=30)


def on_key(event):
    global count
    count += 1

    label.config(
        text=f"Key: {event.keysym}\nCount: {count}"
    )

    print(f"Key: {event.keysym} | Count: {count}")

def check_key_state():
    state = ctypes.windll.user32.GetAsyncKeyState(0x41)

    if state & 0x8000:
        print("A key is pressed")

    root.after(100, check_key_state)

state_label = tk.Label(root, text="A: Released", font=("Arial", 18))
state_label.pack(pady=10)

get_key_state = ctypes.windll.user32.GetAsyncKeyState
get_key_state.argtypes = [ctypes.c_int]
get_key_state.restype = ctypes.c_short


def check_key_state():
    pressed = bool(get_key_state(0x41) & 0x8000)

    state_label.config(
        text="A: Pressed" if pressed else "A: Released",
        fg="green" if pressed else "black"
    )

    root.after(50, check_key_state)


check_key_state()

root.bind("<KeyPress>", on_key)

mouse_label = tk.Label(
    root,
    text="尚未收到滑鼠點擊",
    font=("Arial", 14)
)

mouse_label.pack(pady=10)


def on_mouse_click(event):
    x = event.x_root - root.winfo_rootx()
    y = event.y_root - root.winfo_rooty()

    message = f"Click: X={x}, Y={y}"

    mouse_label.config(text=message)

    print(message, flush=True)


root.bind_all("<ButtonPress-1>", on_mouse_click)

cursor_label = tk.Label(
    root,
    text="Cursor: --",
    font=("Arial", 14)
)

cursor_label.pack(pady=10)

user32 = ctypes.windll.user32

user32.GetCursorPos.argtypes = [
    ctypes.POINTER(wintypes.POINT)
]

user32.ScreenToClient.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.POINT)
]


def check_cursor():
    point = wintypes.POINT()

    if user32.GetCursorPos(ctypes.byref(point)):
        screen_x = point.x
        screen_y = point.y

        if user32.ScreenToClient(
            root.winfo_id(),
            ctypes.byref(point)
        ):
            cursor_label.config(
                text=(
                    f"Screen: {screen_x}, {screen_y}\n"
                    f"Client: {point.x}, {point.y}"
                )
            )

    root.after(50, check_cursor)


check_cursor()

root.update_idletasks()

LRESULT = ctypes.c_ssize_t

WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
)

user32.SetWindowLongPtrW.argtypes = [
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_void_p
]
user32.SetWindowLongPtrW.restype = ctypes.c_void_p

user32.CallWindowProcW.argtypes = [
    ctypes.c_void_p,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
]
user32.CallWindowProcW.restype = LRESULT

user32.GetParent.argtypes = [wintypes.HWND]
user32.GetParent.restype = wintypes.HWND

GWLP_WNDPROC = -4

messages = {
    0x0006: "WM_ACTIVATE",
    0x0200: "WM_MOUSEMOVE",
    0x0201: "WM_LBUTTONDOWN",
    0x0202: "WM_LBUTTONUP"
}

original_procs = {}


@WNDPROC
def monitor_proc(hwnd, msg, wparam, lparam):
    if msg in messages:
        print(
            f"HWND={hwnd} | {messages[msg]} | "
            f"wParam={wparam} | lParam={lparam}",
            flush=True
        )

    return user32.CallWindowProcW(
        original_procs[hwnd],
        hwnd,
        msg,
        wparam,
        lparam
    )


def monitor_window(hwnd):
    original_procs[hwnd] = user32.SetWindowLongPtrW(
        hwnd,
        GWLP_WNDPROC,
        ctypes.cast(monitor_proc, ctypes.c_void_p)
    )

    print(f"監測視窗 HWND: {hwnd}", flush=True)


child_hwnd = root.winfo_id()
parent_hwnd = user32.GetParent(child_hwnd)

monitor_window(child_hwnd)

if parent_hwnd and parent_hwnd != child_hwnd:
    monitor_window(parent_hwnd)

root.mainloop()
