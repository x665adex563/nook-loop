import threading
import math
from pathlib import Path

from core.window_manager import find_window, is_window
from core.frida_bg import FridaManager
from core.bg_input import BackgroundInput


class MacroRunner:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback or print

        self.frida = FridaManager()
        self.bg_input = BackgroundInput(self.frida)

        self.lock = threading.RLock()
        self.tasks = {}

    def log(self, message):
        self.log_callback(message)

    def start(self, macros):
        if not macros:
            self.log("沒有已勾選的巨集")
            return False

        started = False

        for path, macro in macros.items():
            if self.start_macro(path, macro):
                started = True

        return started

    def start_macro(self, path, macro):
        path = Path(path).resolve()

        with self.lock:
            if path in self.tasks:
                return False

            if not macro.get("enabled", False):
                return False

            stop_event = threading.Event()

            thread = threading.Thread(
                target=self._run_task,
                args=(path, macro, stop_event),
                daemon=True
            )

            self.tasks[path] = {
                "thread": thread,
                "stop_event": stop_event
            }

            thread.start()

            return True

    def _run_task(self, path, macro, stop_event):
        try:
            self._run_macro(macro, stop_event)

        finally:
            with self.lock:
                self.tasks.pop(path, None)

                if not self.tasks:
                    try:
                        for error in self.frida.detach_all():
                            self.log(f"資源釋放失敗：{error}")

                    finally:
                        self.log("所有巨集已結束")

    def _run_macro(self, macro, stop_event):
        name = macro["name"]

        try:
            window = find_window(
                macro.get("window_title", "")
            )

            if window is None:
                raise RuntimeError(
                    "找不到唯一的目標視窗"
                )

            hwnd = window["hwnd"]
            pid = window["pid"]

            commands = macro.get("commands", [])
            repeat = macro.get("repeat", {})
            mode = repeat.get("mode", "once")

            if not commands:
                self.log(f"{name}：沒有指令，已跳過")
                return

            if mode not in ("once", "interval", "loop"):
                raise ValueError("無效的執行方式")

            self.log(f"{name}：開始執行")

            while not stop_event.is_set():
                for command in commands:
                    if stop_event.is_set():
                        break

                    if not is_window(hwnd):
                        raise RuntimeError("目標視窗已關閉")

                    self._execute_command(
                        hwnd, pid, command, stop_event
                    )

                if stop_event.is_set():
                    break

                if mode == "once":
                    break

                if mode == "interval":
                    interval = self._duration(
                        repeat.get("interval", 30)
                    )

                    stop_event.wait(interval)

                elif mode == "loop":
                    stop_event.wait(0.01)

            status = (
                "已停止"
                if stop_event.is_set()
                else "執行完成"
            )

            self.log(f"{name}：{status}")

        except Exception as error:
            self.log(f"{name}：執行失敗 - {error}")

    def _duration(self, value):
        value = float(value)

        if not math.isfinite(value) or value < 0:
            raise ValueError("時間必須為非負有限數值")

        return value

    def _execute_command(
        self, hwnd, pid, command, stop_event
    ):
        command_type = command["type"]

        if command_type == "key":
            self.bg_input.send_key(
                hwnd,
                pid,
                command["key"],
                self._duration(
                    command.get("hold_ms", 120)
                ),
                stop_event
            )

        elif command_type == "click":
            self.bg_input.click(
                hwnd,
                pid,
                int(command["x"]),
                int(command["y"]),
                stop_event
            )

        elif command_type == "wait":
            stop_event.wait(
                self._duration(command["seconds"])
            )

        else:
            raise ValueError(
                f"未知的指令類型：{command_type}"
            )

    def stop_macro(self, path):
        path = Path(path).resolve()

        with self.lock:
            task = self.tasks.get(path)

            if task is None:
                return False

            task["stop_event"].set()

            return True

    def stop(self):
        with self.lock:
            if not self.tasks:
                return

            self.log("正在停止所有巨集...")

            for task in self.tasks.values():
                task["stop_event"].set()

    def is_macro_running(self, path):
        path = Path(path).resolve()

        with self.lock:
            return path in self.tasks

    def is_running(self):
        with self.lock:
            return bool(self.tasks)
