import frida
import threading


HOOK_SCRIPT = """
const user32 = Process.getModuleByName("user32.dll");
const pressed = new Set();
let cursorPosition = null;
let cursorTimer = null;
let keyboardHwnd = null;
let targetHwnd = null;
let checkingForeground = false;

const getForegroundWindow = new NativeFunction(
    user32.getExportByName("GetForegroundWindow"),
    "pointer",
    []
);

function isTargetBackground() {
    if (targetHwnd === null) {
        return false;
    }

    checkingForeground = true;

    try {
        return !getForegroundWindow().equals(targetHwnd);
    } finally {
        checkingForeground = false;
    }
}

for (const name of [
    "GetForegroundWindow",
    "GetActiveWindow",
    "GetFocus"
]) {
    Interceptor.attach(user32.getExportByName(name), {
        onLeave(retval) {
            if (checkingForeground) {
                return;
            }

            if (keyboardHwnd !== null && pressed.size > 0) {
                retval.replace(keyboardHwnd);
            } else if (cursorPosition !== null) {
                retval.replace(cursorPosition.hwnd);
            }
        }
    });
}

Interceptor.attach(user32.getExportByName("GetCursorPos"), {
    onEnter(args) {
        this.point = args[0];
    },
    onLeave(retval) {
        if (cursorPosition !== null && !this.point.isNull()) {
            this.point.writeS32(cursorPosition.x);
            this.point.add(4).writeS32(cursorPosition.y);

            retval.replace(1);
        }
    }
});

Interceptor.attach(user32.getExportByName("ScreenToClient"), {
    onEnter(args) {
        this.hwnd = args[0];
        this.point = args[1];
    },

    onLeave(retval) {
        if (
            cursorPosition !== null &&
            !this.point.isNull() &&
            this.hwnd.equals(cursorPosition.hwnd)
        ) {
            this.point.writeS32(cursorPosition.cx);
            this.point.add(4).writeS32(cursorPosition.cy);

            retval.replace(1);
        }
    }
});

for (const name of ["GetAsyncKeyState", "GetKeyState"]) {
    Interceptor.attach(user32.getExportByName(name), {
        onEnter(args) {
            this.vk = args[0].toInt32();
        },
        onLeave(retval) {
            if (pressed.has(this.vk)) {
                retval.replace(0x8000);
            }
        }
    });
}

Interceptor.attach(user32.getExportByName("GetKeyboardState"), {
    onEnter(args) {
        this.buffer = args[0];
    },
    onLeave(retval) {
        if (retval.toInt32() === 0 || this.buffer.isNull()) {
            return;
        }

        for (const vk of pressed) {
            const byte = this.buffer.add(vk);
            byte.writeU8(byte.readU8() | 0x80);
        }
    }
});

const setCursorPosAddress = user32.findExportByName("SetCursorPos");

if (setCursorPosAddress !== null) {
    const originalSetCursorPos = new NativeFunction(
        setCursorPosAddress,
        "int",
        ["int", "int"]
    );

    Interceptor.replace(
        setCursorPosAddress,
        new NativeCallback(
            function (x, y) {
                if (isTargetBackground()) {
                    return 1;
                }

                return originalSetCursorPos(x, y);
            },
            "int",
            ["int", "int"]
        )
    );
}

rpc.exports = {
setcursor(hwnd, sx, sy, cx, cy) {
    targetHwnd = ptr(hwnd);

    cursorPosition = {
        hwnd: ptr(hwnd),
        x: sx,
        y: sy,
        cx: cx,
        cy: cy
    };

    if (cursorTimer !== null) {
        clearTimeout(cursorTimer);
    }

    cursorTimer = setTimeout(() => {
        cursorPosition = null;
        cursorTimer = null;
    }, 500);
},

    setkey(hwnd, vk, down) {
        targetHwnd = ptr(hwnd);

        if (down) {
            keyboardHwnd = ptr(hwnd);
            pressed.add(vk);
        } else {
            pressed.delete(vk);

            if (pressed.size === 0) {
                keyboardHwnd = null;
            }
        }
    },

    releaseall() {
        pressed.clear();
        keyboardHwnd = null;
        targetHwnd = null;
    }
};

send("ready");
"""


class FridaManager:
    def __init__(self):
        self.sessions = {}
        self.lock = threading.RLock()

    def attach(self, pid):
        with self.lock:
            if pid in self.sessions:
                return self.sessions[pid]["script"]

            ready = threading.Event()
            errors = []

            def on_message(message, data):
                if message.get("type") == "send":
                    if message.get("payload") == "ready":
                        ready.set()

                elif message.get("type") == "error":
                    error = message.get(
                        "description", "未知錯誤"
                    )

                    errors.append(error)

                    print(
                        f"[Frida] Script error: {error}",
                        flush=True
                    )

                    ready.set()

            print(f"[Frida] Attaching PID: {pid}", flush=True)

            session = frida.attach(pid)

            try:
                script = session.create_script(HOOK_SCRIPT)
                script.on("message", on_message)
                script.load()

                if not ready.wait(3):
                    raise RuntimeError("Frida ready timeout")

                if errors:
                    raise RuntimeError(errors[0])

            except Exception:
                session.detach()
                raise

            self.sessions[pid] = {
                "session": session,
                "script": script
            }

            print(f"[Frida] Ready PID: {pid}", flush=True)

            return script

    def set_key(self, pid, hwnd, vk, down):
        with self.lock:
            script = self.attach(pid)
            script.exports_sync.setkey(hwnd, vk, down)

    def set_cursor(self, pid, hwnd, sx, sy, cx, cy):
        with self.lock:
            script = self.attach(pid)

            script.exports_sync.setcursor(
                hwnd, sx, sy, cx, cy
            )

    def detach(self, pid):
        with self.lock:
            entry = self.sessions.pop(pid, None)

            if entry is None:
                return

            try:
                entry["script"].exports_sync.releaseall()
            finally:
                entry["session"].detach()

    def detach_all(self):
        with self.lock:
            errors = []

            for pid in list(self.sessions):
                try:
                    self.detach(pid)
                except Exception as error:
                    errors.append(str(error))

            return errors
