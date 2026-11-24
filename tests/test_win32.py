import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

LRESULT = ctypes.c_ssize_t

WNDPROC = ctypes.WINFUNCTYPE(
    LRESULT,
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
)


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR)
    ]


user32.DefWindowProcW.argtypes = [
    wintypes.HWND,
    wintypes.UINT,
    wintypes.WPARAM,
    wintypes.LPARAM
]
user32.DefWindowProcW.restype = LRESULT

user32.RegisterClassW.argtypes = [
    ctypes.POINTER(WNDCLASS)
]
user32.RegisterClassW.restype = wintypes.ATOM

user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID
]
user32.CreateWindowExW.restype = wintypes.HWND

kernel32.GetModuleHandleW.argtypes = [
    wintypes.LPCWSTR
]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE

user32.SetWindowTextW.argtypes = [
    wintypes.HWND,
    wintypes.LPCWSTR
]

user32.ShowWindow.argtypes = [
    wintypes.HWND,
    ctypes.c_int
]

user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short

user32.GetCursorPos.argtypes = [
    ctypes.POINTER(wintypes.POINT)
]

user32.ScreenToClient.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.POINT)
]

user32.SetTimer.argtypes = [
    wintypes.HWND,
    ctypes.c_size_t,
    wintypes.UINT,
    ctypes.c_void_p
]
user32.SetTimer.restype = ctypes.c_size_t

user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    wintypes.UINT,
    wintypes.UINT
]
user32.GetMessageW.restype = ctypes.c_int

user32.TranslateMessage.argtypes = [
    ctypes.POINTER(wintypes.MSG)
]

user32.DispatchMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG)
]
user32.DispatchMessageW.restype = LRESULT

WM_DESTROY = 0x0002
WM_TIMER = 0x0113
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202

click_count = 0
last_click = "--"
mouse_state = "Released"
status = None


@WNDPROC
def window_proc(hwnd, msg, wparam, lparam):
    global click_count, last_click, mouse_state

    if msg == WM_LBUTTONDOWN:
        x = ctypes.c_short(lparam & 0xFFFF).value
        y = ctypes.c_short((lparam >> 16) & 0xFFFF).value

        click_count += 1
        last_click = f"{x}, {y}"
        mouse_state = "Pressed"

        print(
            f"Mouse DOWN: {x}, {y} | Count: {click_count}",
            flush=True
        )

        return 0

    if msg == WM_LBUTTONUP:
        mouse_state = "Released"
        print("Mouse UP", flush=True)
        return 0

    if msg == WM_TIMER:
        pressed = bool(
            user32.GetAsyncKeyState(0x41) & 0x8000
        )

        key_pressed = bool(user32.GetKeyState(0x41) & 0x8000)

        keyboard = (ctypes.c_ubyte * 256)()
        user32.GetKeyboardState(keyboard)
        keyboard_pressed = bool(keyboard[0x41] & 0x80)

        point = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(point))
        user32.ScreenToClient(hwnd, ctypes.byref(point))

        text = (
            f"GetAsyncKeyState: {pressed}\r\n"
            f"GetKeyState: {key_pressed}\r\n"
            f"GetKeyboardState: {keyboard_pressed}\r\n"
            f"Cursor: {point.x}, {point.y}\r\n"
            f"Last Click: {last_click}\r\n"
            f"Click Count: {click_count}\r\n"
            f"Mouse: {mouse_state}"
        )

        if status:
            user32.SetWindowTextW(status, text)

        return 0

    if msg == WM_DESTROY:
        user32.PostQuitMessage(0)
        return 0

    return user32.DefWindowProcW(
        hwnd, msg, wparam, lparam
    )


instance = kernel32.GetModuleHandleW(None)

wc = WNDCLASS()
wc.lpfnWndProc = window_proc
wc.hInstance = instance
wc.hbrBackground = 6
wc.lpszClassName = "BackgroundInputTest"

if not user32.RegisterClassW(ctypes.byref(wc)):
    raise RuntimeError("無法註冊視窗類別")

hwnd = user32.CreateWindowExW(
    0,
    wc.lpszClassName,
    "Background Input Win32 Test",
    0x00CF0000,
    200, 200,
    450, 320,
    None, None,
    instance, None
)

if not hwnd:
    raise RuntimeError("無法建立視窗")

status = user32.CreateWindowExW(
    0,
    "STATIC",
    "",
    0x50000000,
    20, 20,
    390, 110,
    hwnd, None,
    instance, None
)

user32.ShowWindow(hwnd, 5)
user32.SetTimer(hwnd, 1, 50, None)

print(f"Test HWND: {hwnd}", flush=True)

message = wintypes.MSG()

while user32.GetMessageW(
    ctypes.byref(message), None, 0, 0
) > 0:
    user32.TranslateMessage(ctypes.byref(message))
    user32.DispatchMessageW(ctypes.byref(message))
