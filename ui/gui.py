import tkinter as tk
import math
import ctypes
from tkinter import ttk, messagebox, simpledialog
from tkinter import font as tkfont
from pathlib import Path
from queue import Queue, Empty
from datetime import datetime

from core.window_manager import get_windows, find_window
from core.hotkey_manager import HotkeyManager
from core.bg_input import KEY_MAP
from services.macro_manager import MacroManager, MACROS_DIR
from services.macro_runner import MacroRunner
from ui.coordinate_picker import pick_coordinate
from ui.theme import THEMES, apply_ttk_theme, apply_titlebar_theme
from PIL import Image, ImageDraw, ImageGrab, ImageTk


class App:
    def __init__(self, root):
        self.root = root

        self.root.title("Nook Loop")
        self.root.iconbitmap(
            str(Path(__file__).resolve().parent.parent / "assets" / "icon.ico")
        )
        self.root.geometry("1050x720")
        self.root.minsize(850, 550)

        self.manager = MacroManager()
        self.events = Queue()

        self.runner = MacroRunner(
            log_callback=lambda message: self.events.put(("log", message))
        )

        self.hotkey = HotkeyManager(lambda hotkey: self.events.put(("hotkey", hotkey)))

        self.config = self.manager.load_config()
        self.font_size = self.config.get("font_size", "小")

        self.theme = self.config.get("theme", "light")
        self.colors = THEMES[self.theme]
        self.light_ttk_theme = ttk.Style().theme_use()

        self.current_path = None
        self.current_data = None
        self.selected_path = None

        self.loading = False

        self.drag_path = None
        self.drag_start = None
        self.drag_preview = None
        self.drag_target = None

        self.command_drag = None
        self.last_running = False

        self.windows = []

        self.build_ui()
        self.apply_theme()
        self.refresh_windows()
        self.refresh_tree()
        self.register_hotkey()

        self.root.after(100, self.resize_window_for_font)

        self.root.after(100, self.process_events)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def build_ui(self):
        self.panes = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.panes.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.left = ttk.Frame(self.panes, width=420)
        self.right = ttk.Frame(self.panes)

        self.panes.add(self.left, weight=1)
        self.panes.add(self.right, weight=2)

        self.build_tree()
        self.build_editor()
        self.build_log()

    def create_status_light(self, parent):
        return tk.Canvas(
            parent,
            width=18,
            height=18,
            highlightthickness=0,
            borderwidth=0,
            background=ttk.Style().lookup("TFrame", "background"),
        )

    def draw_status_light(self, canvas, status):
        canvas.delete("all")

        colors = {"running": "#22A447", "enabled": "#D6A500"}

        if status in colors:
            canvas.create_oval(4, 4, 14, 14, fill=colors[status], outline="")

        elif status == "idle":
            canvas.create_oval(4, 4, 14, 14, fill="", outline="#808080", width=1)

    def resize_window_for_font(self):
        width, height = {"小": (1200, 650), "中": (1500, 800), "大": (1850, 950)}[
            self.font_size
        ]

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        width = min(width, screen_width - 40)
        height = min(height, screen_height - 100)

        if self.root.state() == "zoomed":
            self.root.state("normal")

        self.root.geometry(f"{width}x{height}")

        self.root.after(100, self.resize_panes_for_font)

    def resize_panes_for_font(self):
        self.panes.sashpos(0, int(self.panes.winfo_width() * 0.38))

        self.update_tree_status()

    def update_colored_buttons(self):
        for button, color in (
            (self.add_file_button, "blue"),
            (self.add_command_button, "blue"),
            (self.macro_start_button, "green"),
        ):
            background, active, foreground = self.colors[color]

            button.configure(
                background=background,
                activebackground=active,
                foreground=foreground,
                activeforeground=foreground,
                disabledforeground=self.colors["disabled_foreground"],
            )

    def update_status_light_backgrounds(self):
        background = ttk.Style().lookup("TFrame", "background")

        self.macro_status_light.configure(background=background)

    def update_log_theme(self):
        if self.theme == "light":
            self.log_text.configure(**self.light_log_colors)
        else:
            self.log_text.configure(
                background=self.colors["input"],
                foreground=self.colors["foreground"],
                insertbackground=self.colors["foreground"],
                selectbackground=self.colors["selection"],
                selectforeground=self.colors["foreground"],
                highlightbackground=self.colors["border"],
                highlightcolor=self.colors["border"],
            )

    def update_combobox_theme(self):
        if self.theme == "dark":
            colors = {
                "background": self.colors["input"],
                "foreground": self.colors["foreground"],
                "selectbackground": self.colors["selection"],
                "selectforeground": self.colors["foreground"],
            }
        else:
            colors = {
                "background": "SystemWindow",
                "foreground": "SystemWindowText",
                "selectbackground": "SystemHighlight",
                "selectforeground": "SystemHighlightText",
            }

        for combo in (self.window_combo, self.mode_combo, self.kind_combo):
            popdown = combo.tk.call("ttk::combobox::PopdownWindow", str(combo))

            combo.tk.call(
                f"{popdown}.f.l",
                "configure",
                *[
                    value
                    for key, color in colors.items()
                    for value in (f"-{key}", color)
                ],
            )

    def apply_theme(self):
        apply_ttk_theme(self.root, self.theme, self.light_ttk_theme)

        self.apply_font_size()

        self.command_canvas.configure(
            background=ttk.Style().lookup("TFrame", "background")
        )

        self.update_colored_buttons()
        self.update_status_light_backgrounds()
        self.update_log_theme()
        self.update_combobox_theme()

        for row in self.commands.winfo_children():
            for widget in row.winfo_children():
                if isinstance(widget, tk.Frame):
                    widget.configure(background=self.colors["separator"])

        self.tree.tag_configure("drop_target", background=self.colors["drop_target"])

        self.root.after_idle(lambda: apply_titlebar_theme(self.root, self.theme))

        self.update_status()

    def toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"

        self.colors = THEMES[self.theme]

        self.theme_button.config(text="☀" if self.theme == "light" else "☾")

        self.apply_theme()

        self.config["theme"] = self.theme
        self.manager.save_config(self.config)

    def cycle_font_size(self):
        sizes = ["小", "中", "大"]

        index = sizes.index(self.font_size)

        self.font_size = sizes[(index + 1) % len(sizes)]

        self.apply_font_size()
        self.resize_window_for_font()

        self.config["font_size"] = self.font_size
        self.manager.save_config(self.config)

    def apply_font_size(self):
        size, title_size, row_height = {
            "小": (12, 17, 30),
            "中": (16, 21, 40),
            "大": (20, 25, 50),
        }[self.font_size]

        for name in (
            "TkDefaultFont",
            "TkTextFont",
            "TkHeadingFont",
            "TkMenuFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
            "TkTooltipFont",
        ):
            tkfont.nametofont(name).configure(family="Microsoft JhengHei", size=size)

        style = ttk.Style()

        style.configure("CommandMuted.TLabel", foreground=self.colors["muted"])

        style.configure(
            "CommandDelete.TButton",
            background=self.colors["background"],
            foreground=self.colors["muted"],
            borderwidth=0,
            relief="flat",
        )

        style.map(
            "CommandDelete.TButton",
            background=[("active", self.colors["surface"])],
            foreground=[("active", self.colors["foreground"])],
        )

        style.configure(".", font=("Microsoft JhengHei", size))

        style.configure("TEntry", padding=(4, 3))

        style.configure("Note.TEntry", foreground=self.colors["foreground"])

        style.configure("NotePlaceholder.TEntry", foreground=self.colors["muted"])

        style.configure("TCombobox", padding=(4, 3))

        style.configure("TButton", anchor="center", padding=(6, 3))

        style.configure(
            "Treeview", font=("Microsoft JhengHei", size), rowheight=row_height
        )

        style.configure("Treeview.Heading", font=("Microsoft JhengHei", size))

        style.configure("Title.TLabel", font=("Microsoft JhengHei", title_size, "bold"))

        style.configure("Section.TLabel", font=("Microsoft JhengHei", size + 2, "bold"))

        self.font_button.config(text=self.font_size)

        self.log_text.config(font=("Microsoft JhengHei", size + 1))

        icon_size = {"小": 17, "中": 21, "大": 25}[self.font_size]

        self.add_file_icon = self.create_add_icon(size=icon_size)

        self.add_folder_icon = self.create_add_icon(folder=True, size=icon_size)

        self.add_file_button.config(image=self.add_file_icon)

        self.add_folder_button.config(image=self.add_folder_icon)

        self.root.update_idletasks()

        self.add_file_button.config(
            width=self.add_folder_button.winfo_reqwidth() - 2,
            height=self.add_folder_button.winfo_reqheight() - 2,
            padx=0,
            pady=0,
            borderwidth=1,
        )

        hotkey_width, status_width, delete_width = {
            "小": (100, 100, 45),
            "中": (130, 130, 60),
            "大": (160, 160, 75),
        }[self.font_size]

        self.tree.column("hotkey", width=hotkey_width)

        self.tree.column("status", width=status_width)

        self.tree.column("delete", width=delete_width)

        self.root.after_idle(self.align_command_fields)

        style.configure(
            "Command.TEntry",
            bordercolor=self.colors["separator"],
            lightcolor=self.colors["separator"],
            darkcolor=self.colors["separator"],
        )

        style.configure(
            "Note.TEntry",
            bordercolor=self.colors["separator"],
            lightcolor=self.colors["separator"],
            darkcolor=self.colors["separator"],
        )

    def build_toolbar(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(side=tk.LEFT)

        self.log_button = ttk.Button(
            toolbar, text="📖", width=3, command=self.toggle_log
        )

        self.log_button.pack(side=tk.LEFT, padx=(0, 3))

        self.add_tooltip(self.log_button, "執行日誌")

        self.font_button = ttk.Button(
            toolbar, text=self.font_size, width=3, command=self.cycle_font_size
        )

        self.font_button.pack(side=tk.LEFT, padx=(0, 3))

        self.add_tooltip(self.font_button, "切換字體大小")

        self.theme_button = ttk.Button(
            toolbar,
            text="☀" if self.theme == "light" else "☾",
            width=3,
            command=self.toggle_theme,
        )

        self.theme_button.pack(side=tk.LEFT, padx=(0, 3))

        self.add_tooltip(self.theme_button, "切換深淺色模式")

    def create_colored_button(self, parent, color="blue", **kwargs):
        background, active, foreground = self.colors[color]

        return tk.Button(
            parent,
            background=background,
            activebackground=active,
            foreground=foreground,
            activeforeground=foreground,
            disabledforeground=self.colors["disabled_foreground"],
            font="TkDefaultFont",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            padx=8,
            pady=4,
            cursor="hand2",
            **kwargs,
        )

    def create_add_icon(self, folder=False, size=18):
        image = Image.new("RGBA", (48, 48))
        draw = ImageDraw.Draw(image)

        color = self.colors["icon"]

        if folder:
            draw.line(
                [(5, 39), (5, 10), (19, 10), (24, 16), (43, 16), (43, 39), (5, 39)],
                fill=color,
                width=3,
            )
        else:
            draw.line(
                [(10, 5), (29, 5), (39, 15), (39, 43), (10, 43), (10, 5)],
                fill=color,
                width=3,
            )

            draw.line([(29, 5), (29, 15), (39, 15)], fill=color, width=3)

        draw.line([(18, 28), (30, 28)], fill=color, width=3)

        draw.line([(24, 22), (24, 34)], fill=color, width=3)

        image = image.resize((size, size), Image.Resampling.LANCZOS)

        return ImageTk.PhotoImage(image)

    def build_tree(self):
        header = ttk.Frame(self.left)
        header.pack(fill=tk.X, pady=(0, 6))

        self.add_file_icon = self.create_add_icon()
        self.add_folder_icon = self.create_add_icon(folder=True)

        self.add_file_button = self.create_colored_button(
            header, color="blue", image=self.add_file_icon, command=self.create_macro
        )

        self.add_file_button.config(relief="raised", borderwidth=1, padx=3, pady=2)

        self.add_file_button.pack(side=tk.LEFT, padx=(0, 3))

        self.add_tooltip(self.add_file_button, "新增空巨集")

        self.add_folder_button = ttk.Button(
            header, image=self.add_folder_icon, command=self.create_folder
        )

        self.add_folder_button.pack(side=tk.LEFT, padx=(0, 3))

        self.add_tooltip(self.add_folder_button, "新增資料夾")

        self.build_toolbar(header)

        self.tree = ttk.Treeview(
            self.left,
            columns=("hotkey", "status", "check", "delete"),
            displaycolumns=("hotkey", "status", "delete"),
            show="tree headings",
            selectmode="browse",
        )

        self.tree.heading("#0", text="名稱")
        self.tree.heading("hotkey", text="快捷鍵")
        self.tree.heading("status", text="啟用快捷鍵")
        self.tree.heading("delete", text="")

        self.tree.column("#0", width=170, minwidth=100)
        self.tree.column(
            "hotkey", width=100, minwidth=65, stretch=False, anchor="center"
        )
        self.tree.column("status", width=45, stretch=False, anchor="center")
        self.tree.column("delete", width=45, stretch=False, anchor="center")

        self.tree.pack(fill=tk.BOTH, expand=True)

        self.tree_status_lights = {}
        self.tree_separators = {}

        self.tree_header_separator = tk.Frame(
            self.tree, background=self.colors["separator"], height=1, borderwidth=0
        )

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<ButtonPress-1>", self.on_tree_click)
        self.tree.bind("<ButtonRelease-1>", self.on_tree_release)

        self.tree.bind("<B1-Motion>", self.on_tree_drag)

        self.tree.tag_configure("drop_target", background=self.colors["drop_target"])

    def build_editor(self):
        self.title_var = tk.StringVar()

        title_row = ttk.Frame(self.right)
        self.title_row = title_row

        self.macro_hotkey_entry = None

        ttk.Label(title_row, textvariable=self.title_var, style="Title.TLabel").pack(
            side=tk.LEFT
        )

        self.editor_body = ttk.Frame(self.right)

        settings = ttk.Frame(self.editor_body)
        settings.pack(fill=tk.X)

        window_row = ttk.Frame(settings)
        window_row.pack(fill=tk.X, pady=(3, 10))

        ttk.Label(window_row, text="目標視窗").pack(side=tk.LEFT, padx=(0, 5))

        self.window_var = tk.StringVar()

        self.window_combo = ttk.Combobox(
            window_row,
            textvariable=self.window_var,
            state="readonly",
            postcommand=self.refresh_windows,
        )

        self.window_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.window_combo.bind("<<ComboboxSelected>>", self.save_settings)

        mode_row = ttk.Frame(settings)
        mode_row.pack(fill=tk.X, pady=5)

        ttk.Label(mode_row, text="執行方式").pack(side=tk.LEFT)

        self.mode_options = {
            "僅執行一次": "once",
            "固定間隔重複": "interval",
            "固定時間後停止": "timed",
            "無限循環": "loop",
        }

        self.mode_var = tk.StringVar(value="僅執行一次")

        self.mode_combo = ttk.Combobox(
            mode_row,
            textvariable=self.mode_var,
            values=list(self.mode_options),
            state="readonly",
            width=14,
        )

        self.mode_combo.pack(side=tk.LEFT, padx=(5, 15))

        self.mode_combo.bind("<<ComboboxSelected>>", self.on_mode_change)

        self.mode_label = ttk.Label(mode_row, text="每輪結束後等待")

        self.interval_var = tk.StringVar(value="30")

        self.interval_entry = ttk.Entry(
            mode_row,
            textvariable=self.interval_var,
            width=6,
            justify="center",
            state="disabled",
        )

        self.interval_entry.pack(side=tk.LEFT, padx=5)

        self.interval_entry.bind("<FocusOut>", self.save_settings)

        self.interval_entry.bind("<Return>", self.save_settings)

        self.seconds_label = ttk.Label(mode_row, text="秒")

        self.stop_label = ttk.Label(mode_row, text="後停止")

        command_header = ttk.Frame(self.editor_body)
        command_header.pack(fill=tk.X, pady=(5, 0))

        self.command_header = command_header

        ttk.Label(command_header, text="指令列表", style="Section.TLabel").pack(
            side=tk.LEFT, padx=(0, 8)
        )

        self.kind_var = tk.StringVar(value="鍵盤輸入")

        self.kind_combo = ttk.Combobox(
            command_header,
            textvariable=self.kind_var,
            values=("鍵盤輸入", "滑鼠點擊", "等待"),
            state="readonly",
            width=10,
        )

        self.kind_combo.pack(side=tk.LEFT, padx=(0, 5))

        self.add_command_button = self.create_colored_button(
            command_header, color="blue", text="+ 新增指令", command=self.add_command
        )

        self.add_command_button.pack(side=tk.LEFT)

        self.macro_start_button = self.create_colored_button(
            command_header,
            color="green",
            text="執行",
            command=self.toggle_macro,
            state="disabled",
        )

        self.macro_start_button.pack(side=tk.RIGHT, padx=(0, 5))

        self.macro_status_light = self.create_status_light(command_header)

        self.macro_status_light.pack(side=tk.RIGHT, padx=(0, 3))

        self.macro_status_light.bind("<Button-1>", self.on_macro_status_click)

        command_area = ttk.Frame(self.editor_body)
        command_area.pack(fill=tk.BOTH, expand=True, pady=5)

        self.command_canvas = tk.Canvas(command_area, highlightthickness=0)

        scrollbar = ttk.Scrollbar(
            command_area, orient=tk.VERTICAL, command=self.command_canvas.yview
        )

        self.command_canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.command_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.commands = ttk.Frame(self.command_canvas)

        self.command_window = self.command_canvas.create_window(
            (0, 0), window=self.commands, anchor="nw"
        )

        self.commands.bind(
            "<Configure>",
            lambda event: self.command_canvas.configure(
                scrollregion=self.command_canvas.bbox("all")
            ),
        )

        self.command_canvas.bind(
            "<Configure>",
            lambda event: self.command_canvas.itemconfigure(
                self.command_window, width=event.width
            ),
        )

        self.root.bind("<MouseWheel>", self.scroll_commands, add="+")

        self.saved_var = tk.StringVar()

        ttk.Label(self.editor_body, textvariable=self.saved_var).pack(
            anchor="e", pady=5
        )

        self.right.bind("<Button-1>", self.on_editor_blank_click)

        self.editor_body.bind("<Button-1>", self.on_editor_blank_click)

        self.command_canvas.bind("<Button-1>", self.on_editor_blank_click)

        self.commands.bind("<Button-1>", self.on_editor_blank_click)

    def on_editor_blank_click(self, event):
        self.root.focus_set()

        for combo in (self.window_combo, self.mode_combo, self.kind_combo):
            combo.selection_clear()

        return "break"

    def add_tooltip(self, widget, text):
        tooltip = None
        timer = None

        def show():
            nonlocal tooltip, timer

            timer = None

            tooltip = tk.Toplevel(self.root)
            tooltip.overrideredirect(True)
            tooltip.attributes("-topmost", True)

            x = widget.winfo_rootx()
            y = widget.winfo_rooty() + widget.winfo_height() + 5

            tooltip.geometry(f"+{x}+{y}")

            ttk.Label(
                tooltip, text=text, padding=(8, 5), relief="solid", borderwidth=1
            ).pack()

        def enter(event=None):
            nonlocal timer

            timer = widget.after(500, show)

        def leave(event=None):
            nonlocal tooltip, timer

            if timer is not None:
                widget.after_cancel(timer)
                timer = None

            if tooltip is not None:
                tooltip.destroy()
                tooltip = None

        widget.bind("<Enter>", enter)
        widget.bind("<Leave>", leave)
        widget.bind("<ButtonPress-1>", leave)
        widget.bind("<Destroy>", leave)

    def build_log(self):
        self.log_frame = ttk.Frame(self.root)

        self.log_visible = False

        self.log_text = tk.Text(
            self.log_frame, height=7, state="disabled", font=("Consolas", 10)
        )

        self.light_log_colors = {
            option: self.log_text.cget(option)
            for option in (
                "background",
                "foreground",
                "insertbackground",
                "selectbackground",
                "selectforeground",
                "highlightbackground",
                "highlightcolor",
            )
        }

        self.log_text.pack(fill=tk.BOTH, expand=True)

    def toggle_log(self):
        self.log_visible = not self.log_visible

        if self.log_visible:
            self.log_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        else:
            self.log_frame.pack_forget()

    def log(self, message):
        timestamp = datetime.now().strftime("%H:%M:%S")

        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def refresh_windows(self):
        self.windows = get_windows()

        titles = [window["title"] for window in self.windows]

        self.window_combo.config(values=titles)

    def refresh_tree(self, select=None):
        opened = {iid: self.tree.item(iid, "open") for iid in self.tree.get_children()}

        self.tree.delete(*self.tree.get_children())

        for folder in self.manager.get_folders():
            state = self.manager.get_folder_state(folder)

            symbol = {"checked": "☑", "unchecked": "☐", "partial": "▣"}[state]

            self.tree.insert(
                "",
                "end",
                iid=str(folder),
                text=f"✎  📁 {folder.name}",
                values=("", "", symbol, "🗑"),
                open=opened.get(str(folder), True),
            )

            for path in self.manager.get_macros(folder):
                self.insert_macro(path, str(folder))

        for path in self.manager.get_macros():
            self.insert_macro(path, "")

        target = select or self.selected_path

        if target and self.tree.exists(str(target)):
            self.tree.selection_set(str(target))
            self.tree.see(str(target))

    def insert_macro(self, path, parent):
        data = self.manager.load_macro(path)

        enabled = data.get("enabled", False)

        symbol = "☑" if enabled else "☐"

        self.tree.insert(
            parent,
            "end",
            iid=str(path),
            text=f'✎  {data["name"]}',
            values=(data["hotkey"] or "—", "", symbol, "🗑"),
        )

    def update_editor_visibility(self):
        self.title_row.pack_forget()
        self.editor_body.pack_forget()

        if self.selected_path is not None:
            self.title_row.pack(fill=tk.X, pady=(0, 10))

        if self.current_path is not None:
            self.editor_body.pack(fill=tk.BOTH, expand=True)

    def clear_selection(self):
        self.current_path = None
        self.current_data = None
        self.selected_path = None

        self.title_var.set("")
        self.window_var.set("")
        self.mode_var.set("僅執行一次")
        self.interval_var.set("30")
        self.saved_var.set("")

        self.update_interval_state()
        self.refresh_commands()
        self.update_status()
        self.update_editor_visibility()

    def on_tree_select(self, event=None):
        selection = self.tree.selection()

        if not selection:
            self.clear_selection()
            return

        path = Path(selection[0])
        self.selected_path = path

        if path.is_dir():
            self.current_path = None
            self.current_data = None
            self.title_var.set(path.name)
            self.window_var.set("")
            self.refresh_commands()
            self.update_status()
            self.update_editor_visibility()
            return

        self.load_macro(path)

    def can_toggle_enabled(self, path):
        if path.is_dir():
            return not any(
                self.runner.is_macro_running(child)
                for child in self.manager.get_macros(path)
            )

        return not self.runner.is_macro_running(path)

    def toggle_enabled(self, path):
        if not self.can_toggle_enabled(path):
            return

        if path.is_dir():
            state = self.manager.get_folder_state(path)

            self.manager.set_folder_enabled(path, state != "checked")
        else:
            data = self.manager.load(path)

            self.manager.set_enabled(path, not data.get("enabled", False))

        if self.current_path:
            self.current_data["enabled"] = self.manager.load(self.current_path).get(
                "enabled", False
            )

        self.refresh_tree()
        self.register_hotkey()

    def on_tree_click(self, event):
        iid = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        region = self.tree.identify_region(event.x, event.y)

        if region == "nothing" and not iid:
            self.root.focus_set()

            self.tree.selection_remove(*self.tree.selection())

            self.tree.focus("")
            self.clear_selection()

            return "break"

        if self.runner.is_running():
            if column == "#0":
                return

            if column != "#2":
                return "break"

        if not iid:
            return

        path = Path(iid)

        if column == "#1":
            if path.is_file() and self.is_hotkey_click(iid, event.x):
                self.tree.selection_set(iid)
                self.tree.focus(iid)

                self.configure_macro_hotkey(path)

                return "break"

            return

        if column == "#2":
            self.tree.selection_set(iid)
            self.tree.focus("")
            self.root.focus_set()
            return "break"

        if column == "#3":
            self.delete_item(path)
            return "break"

        if column == "#0":
            if self.is_rename_click(iid, event.x):
                self.rename_item(path)
                return "break"

        if column == "#0":
            element = self.tree.identify_element(event.x, event.y)

            if element.endswith("indicator"):
                return

            self.drag_path = path
            self.drag_start = (event.x, event.y)

    def create_drag_preview(self, text):
        preview = tk.Toplevel(self.root)

        preview.overrideredirect(True)
        preview.attributes("-topmost", True)
        preview.attributes("-alpha", 0.85)

        ttk.Label(
            preview, text=text, padding=(12, 8), relief="solid", borderwidth=1
        ).pack()

        return preview

    def move_drag_preview(self, preview, event):
        preview.geometry(f"+{event.x_root + 15}" f"+{event.y_root + 15}")

    def clear_tree_drag(self):
        if self.drag_preview is not None:
            self.drag_preview.destroy()
            self.drag_preview = None

        if self.drag_target:
            if self.tree.exists(self.drag_target):
                self.tree.item(self.drag_target, tags=())

        self.drag_target = None
        self.drag_path = None
        self.drag_start = None

        self.tree.configure(cursor="")

    def on_tree_drag(self, event):
        if not self.drag_path or not self.drag_start:
            return

        if self.runner.is_running():
            self.clear_tree_drag()
            return

        distance = abs(event.x - self.drag_start[0]) + abs(event.y - self.drag_start[1])

        if distance < 8 and self.drag_preview is None:
            return

        if self.drag_preview is None:
            path = self.drag_path

            text = f"📁 {path.name}" if path.is_dir() else path.stem

            self.drag_preview = self.create_drag_preview(text)

            self.tree.configure(cursor="fleur")

        self.move_drag_preview(self.drag_preview, event)

        if self.drag_target:
            if self.tree.exists(self.drag_target):
                self.tree.item(self.drag_target, tags=())

        self.drag_target = None

        if self.drag_path.is_dir():
            return

        iid = self.tree.identify_row(event.y)

        if iid:
            target = Path(iid)

            if target.is_file():
                target = target.parent

            if target != MACROS_DIR:
                self.drag_target = str(target)

                if self.tree.exists(self.drag_target):
                    self.tree.item(self.drag_target, tags=("drop_target",))

    def on_tree_release(self, event):
        path = self.drag_path
        dragging = self.drag_preview is not None

        self.clear_tree_drag()

        if not path or not dragging:
            return

        if self.runner.is_running():
            return

        if not (
            0 <= event.x < self.tree.winfo_width()
            and 0 <= event.y < self.tree.winfo_height()
        ):
            return

        if path.is_dir():
            return

        iid = self.tree.identify_row(event.y)

        if iid:
            target = Path(iid)

            if target == path:
                return

            folder = target if target.is_dir() else target.parent

        else:
            region = self.tree.identify_region(event.x, event.y)

            if region != "nothing":
                return

            folder = MACROS_DIR

        if folder == path.parent:
            return

        try:
            destination = self.manager.move_macro(path, folder)

            self.selected_path = destination
            self.refresh_tree(destination)
            self.load_macro(destination)

        except Exception as error:
            messagebox.showerror("移動失敗", str(error))

    def create_folder(self):
        if self.runner.is_running():
            return

        name = simpledialog.askstring("新增資料夾", "資料夾名稱：", parent=self.root)

        if not name:
            return

        try:
            path = self.manager.create_folder(name)
            self.refresh_tree(path)
        except Exception as error:
            messagebox.showerror("新增失敗", str(error))

    def create_macro(self):
        if self.runner.is_running():
            return

        name = simpledialog.askstring("新增巨集", "巨集名稱：", parent=self.root)

        if not name:
            return

        folder = MACROS_DIR

        if self.selected_path:
            folder = (
                self.selected_path
                if self.selected_path.is_dir()
                else self.selected_path.parent
            )

        try:
            path = self.manager.create_macro(name, folder)

            self.refresh_tree(path)
            self.load_macro(path)

        except Exception as error:
            messagebox.showerror("新增失敗", str(error))

    def is_hotkey_click(self, iid, mouse_x):
        bounds = self.tree.bbox(iid, "hotkey")

        if not bounds:
            return False

        x, y, width, height = bounds

        font_name = ttk.Style().lookup("Treeview", "font") or "TkDefaultFont"

        font = tkfont.Font(font=font_name)

        text = self.tree.set(iid, "hotkey")
        text_width = font.measure(text)

        center = x + width / 2
        half_width = text_width / 2 + 4

        return center - half_width <= mouse_x <= center + half_width

    def is_rename_click(self, iid, mouse_x):
        bounds = self.tree.bbox(iid, "#0")

        if not bounds:
            return False

        x, y, width, height = bounds

        font_name = ttk.Style().lookup("Treeview", "font") or "TkDefaultFont"

        font = tkfont.Font(font=font_name)
        center_y = y + height // 2

        for position in range(x, x + width):
            element = self.tree.identify_element(position, center_y)

            if element.endswith("text"):
                pencil_width = font.measure("✎")

                return position <= mouse_x <= position + pencil_width + 4

        return False

    def rename_item(self, path):
        if self.runner.is_running():
            return

        iid = str(path)
        bounds = self.tree.bbox(iid, "#0")

        if not bounds:
            return

        x, y, width, height = bounds

        is_folder = path.is_dir()

        old_name = path.name if is_folder else path.stem

        text_x = x
        center_y = y + height // 2

        for position in range(x, x + width):
            element = self.tree.identify_element(position, center_y)

            if element.endswith("text"):
                text_x = position
                break

        font_name = ttk.Style().lookup("Treeview", "font") or "TkDefaultFont"

        font = tkfont.Font(font=font_name)

        prefix = "✎  📁 " if is_folder else "✎  "

        text_x += font.measure(prefix)

        was_open = self.tree.item(iid, "open")

        entry = ttk.Entry(self.tree)

        entry.insert(0, old_name)

        entry.place(x=text_x, y=y, width=max(1, x + width - text_x), height=height)

        finished = False

        def finish(save):
            nonlocal finished

            if finished:
                return "break"

            finished = True

            name = entry.get().strip()
            entry.destroy()

            if not save or not name or name == old_name or self.runner.is_running():
                return "break"

            try:
                if is_folder:
                    destination = self.manager.rename_folder(path, name)
                else:
                    destination = self.manager.rename_macro(path, name)

                self.current_path = None
                self.current_data = None
                self.selected_path = destination

                self.refresh_tree(destination)

                if is_folder:
                    self.tree.item(str(destination), open=was_open)

                self.on_tree_select()

            except Exception as error:
                messagebox.showerror("改名失敗", str(error))

            return "break"

        entry.bind("<Return>", lambda event: finish(True))

        entry.bind("<Escape>", lambda event: finish(False))

        entry.bind("<FocusOut>", lambda event: finish(True))

        entry.focus_set()
        entry.select_range(0, tk.END)

    def delete_item(self, path):
        if self.runner.is_running():
            return

        if path.is_dir():
            count = len(self.manager.get_macros(path))

            message = (
                f"確定刪除「{path.name}」資料夾？\n\n"
                f"只會刪除資料夾本身，"
                f"其中 {count} 份巨集將保留"
                f"並移至根目錄。"
            )
        else:
            message = f"確定永久刪除「{path.stem}」？"

        if not messagebox.askyesno("確認刪除", message):
            return

        try:
            if path.is_dir():
                self.manager.delete_folder(path)
            else:
                self.manager.delete_macro(path)

            self.clear_selection()
            self.refresh_tree()
            self.register_hotkey()

        except Exception as error:
            messagebox.showerror("刪除失敗", str(error))

    def load_macro(self, path):
        self.loading = True

        try:
            self.current_path = Path(path)
            self.selected_path = Path(path)
            self.current_data = self.manager.load_macro(path)

            data = self.current_data
            repeat = data.get("repeat", {})

            self.title_var.set(data["name"])

            self.window_var.set(data.get("window_title", ""))

            mode = repeat.get("mode", "once")

            for label, value in self.mode_options.items():
                if value == mode:
                    self.mode_var.set(label)
                    break

            self.update_interval_state()

            self.interval_var.set(str(repeat.get("interval", 30)))

            self.refresh_commands()

        finally:
            self.loading = False
            self.update_editor_visibility()

    def save_current(self):
        if not self.current_path or not self.current_data:
            return

        latest = self.manager.load(self.current_path)

        self.current_data["enabled"] = latest.get("enabled", False)

        self.manager.save(self.current_path, self.current_data)

        self.saved_var.set("已自動儲存")

    def on_mode_change(self, event=None):
        self.update_interval_state()
        self.save_settings()

    def update_interval_state(self):
        mode = self.mode_options[self.mode_var.get()]

        self.mode_label.pack_forget()
        self.interval_entry.pack_forget()
        self.seconds_label.pack_forget()
        self.stop_label.pack_forget()

        if mode in ("interval", "timed"):
            self.mode_label.config(text="執行" if mode == "timed" else "每輪結束後等待")

            self.mode_label.pack(side=tk.LEFT)

            self.interval_entry.pack(side=tk.LEFT, padx=5)
            self.seconds_label.pack(side=tk.LEFT)

            if mode == "timed":
                self.stop_label.pack(side=tk.LEFT)

            self.interval_entry.config(state="normal")

        else:
            self.interval_entry.config(state="disabled")

    def save_settings(self, event=None):
        if self.loading or not self.current_data:
            return

        if self.runner.is_running():
            return

        try:
            interval = float(self.interval_var.get().strip())

            if interval < 0:
                interval = 0

        except ValueError:
            interval = 0

        self.interval_var.set(str(int(interval) if interval.is_integer() else interval))

        self.current_data["window_title"] = self.window_var.get()

        self.current_data["repeat"] = {
            "mode": self.mode_options[self.mode_var.get()],
            "interval": interval,
        }

        self.save_current()

    def scroll_commands(self, event):
        widget = self.root.winfo_containing(event.x_root, event.y_root)

        while widget is not None:
            if widget == self.command_canvas:
                self.command_canvas.yview_scroll(-int(event.delta / 120), "units")

                return "break"

            widget = getattr(widget, "master", None)

    def refresh_commands(self):
        for widget in self.commands.winfo_children():
            widget.destroy()

        if not self.current_data:
            return

        for index, command in enumerate(self.current_data["commands"]):
            self.create_command_row(index, command)

        self.root.after_idle(self.align_command_fields)

    def create_command_row(self, index, command):
        row = ttk.Frame(self.commands, padding=(5, 4))

        row.pack(fill=tk.X, pady=1)

        tk.Frame(
            row,
            background=self.colors["separator"],
            height=1,
            borderwidth=0,
            highlightthickness=0,
        ).pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))

        handle = ttk.Label(
            row,
            text="⠿",
            style="CommandMuted.TLabel",
            cursor="fleur",
            width=3,
            anchor="center",
        )

        handle.pack(side=tk.LEFT)

        handle.bind(
            "<ButtonPress-1>", lambda event: self.start_command_drag(event, index, row)
        )

        handle.bind("<B1-Motion>", self.drag_command)

        handle.bind("<ButtonRelease-1>", self.finish_command_drag)

        labels = {"key": "鍵盤輸入", "click": "滑鼠點擊", "wait": "等待"}

        ttk.Label(row, text=f"{index + 1}. {labels[command['type']]}", width=13).pack(
            side=tk.LEFT
        )

        ttk.Button(
            row,
            text="×",
            width=3,
            style="CommandDelete.TButton",
            cursor="hand2",
            command=lambda: self.delete_command(index),
        ).pack(side=tk.RIGHT, padx=1)

        content = ttk.Frame(row)
        content.pack(side=tk.LEFT, fill=tk.X, expand=True)

        content.columnconfigure(1, weight=1)

        fields = ttk.Frame(content)
        fields.grid(row=0, column=0, sticky="w")

        if command["type"] == "key":
            self.create_key_field(fields, command)

            self.create_number_field(fields, command, "hold_ms", "", "ms")

        elif command["type"] == "click":
            x_var = self.create_number_field(fields, command, "x", "X", integer=True)

            y_var = self.create_number_field(fields, command, "y", "Y", integer=True)

            ttk.Button(
                fields,
                text="擷取位置",
                command=lambda: self.capture_position(command, x_var, y_var),
            ).pack(side=tk.LEFT, padx=3)

        elif command["type"] == "wait":
            self.create_number_field(fields, command, "seconds", "", "ms", scale=1000)

        self.create_note_field(content, command).grid(
            row=0, column=1, sticky="ew", padx=(8, 5)
        )

    def align_command_fields(self):
        self.root.update_idletasks()

        contents = []

        for row in self.commands.winfo_children():
            for widget in row.winfo_children():
                if isinstance(widget, ttk.Frame):
                    fields = widget.grid_slaves(row=0, column=0)

                    if fields:
                        contents.append((widget, fields[0]))

        if not contents:
            return

        width = max(fields.winfo_reqwidth() for content, fields in contents)

        for content, fields in contents:
            content.columnconfigure(0, minsize=width)

    def create_note_field(self, parent, command):
        variable = tk.StringVar(value=command.get("note", ""))

        entry = ttk.Entry(parent, textvariable=variable, style="Note.TEntry", width=8)

        placeholder = ttk.Label(
            entry,
            text="備註",
            foreground=self.colors["muted"],
            background=ttk.Style().lookup("TEntry", "fieldbackground"),
        )

        def update_placeholder(event=None):
            if not variable.get() and entry.focus_get() != entry:
                placeholder.place(x=5, rely=0.5, anchor="w")
            else:
                placeholder.place_forget()

        def save_note(*args):
            command["note"] = variable.get()
            self.save_current()
            update_placeholder()

        def focus_entry(event=None):
            entry.focus_set()
            placeholder.place_forget()

        placeholder.bind("<Button-1>", focus_entry)

        entry.bind("<FocusIn>", update_placeholder)
        entry.bind("<FocusOut>", update_placeholder)

        variable.trace_add("write", save_note)

        update_placeholder()

        return entry

    def create_key_field(self, parent, command):
        def save_key(key):
            command["key"] = key
            self.save_current()

        entry = self.create_key_capture(parent, command.get("key", ""), save_key)

        entry.configure(width=7, style="Command.TEntry")

        entry.pack(side=tk.LEFT, padx=5)

    def create_key_capture(self, parent, initial_value, on_change):
        variable = tk.StringVar(value=initial_value)

        entry = ttk.Entry(
            parent, textvariable=variable, width=20, justify="center", state="readonly"
        )

        vk_map = {vk: key for key, vk in KEY_MAP.items()}

        vk_map[0x1B] = "ESC"

        vk_map.update({vk: chr(vk) for vk in range(0x41, 0x5B)})

        vk_map.update({vk: chr(vk) for vk in range(0x30, 0x3A)})

        get_key_state = ctypes.windll.user32.GetAsyncKeyState
        get_key_state.argtypes = [ctypes.c_int]
        get_key_state.restype = ctypes.c_short

        previous = set()
        captured = set()
        timer = None

        modifier_order = (0x11, 0x10, 0x12)

        def read_pressed():
            return {vk for vk in vk_map if get_key_state(vk) & 0x8000}

        def poll_keys():
            nonlocal previous, timer

            timer = None

            if not entry.winfo_exists():
                return

            if entry.focus_get() != entry:
                return

            current = read_pressed()
            new_keys = current - previous

            if not self.runner.is_running():
                if new_keys:
                    if not previous:
                        captured.clear()

                    captured.update(current)

                    ordered = [vk for vk in modifier_order if vk in captured]

                    ordered.extend(sorted(captured - set(modifier_order)))

                    key = "+".join(vk_map[vk] for vk in ordered)

                    variable.set(key)
                    on_change(key)

                if not current:
                    captured.clear()

            previous = current

            timer = entry.after(15, poll_keys)

        def start_capture(event=None):
            nonlocal previous, timer

            if timer is not None:
                return

            previous = read_pressed()
            captured.clear()
            timer = entry.after(15, poll_keys)

        def stop_capture(event=None):
            nonlocal timer

            if timer is not None:
                entry.after_cancel(timer)
                timer = None

        entry.bind("<FocusIn>", start_capture)
        entry.bind("<FocusOut>", stop_capture)
        entry.bind("<Destroy>", stop_capture)

        entry.bind("<KeyPress>", lambda event: "break")

        entry.bind("<Button-1>", lambda event: entry.focus_set())

        return entry

    def create_number_field(
        self, parent, command, key, label, unit="", integer=False, scale=1
    ):
        if label:
            ttk.Label(parent, text=label).pack(side=tk.LEFT)

        def display_value():
            value = command.get(key, 0) * scale
            return f"{value:g}"

        variable = tk.StringVar(value=display_value())

        entry = ttk.Entry(
            parent,
            textvariable=variable,
            width=6,
            style="Command.TEntry",
            justify="center",
        )

        entry.pack(side=tk.LEFT, padx=3)

        if unit:
            ttk.Label(parent, text=unit).pack(side=tk.LEFT, padx=(0, 3))

        def save_value(*args):
            if self.runner.is_running():
                return

            try:
                value = int(variable.get()) if integer else float(variable.get())

                if value < 0 or not math.isfinite(value):
                    return

            except ValueError:
                return

            command[key] = value if scale == 1 else value / scale

            self.save_current()

        def restore_value(event=None):
            variable.set(display_value())

        variable.trace_add("write", save_value)

        entry.bind("<FocusOut>", restore_value)
        entry.bind("<Return>", restore_value)

        return variable

    def add_command(self):
        if not self.current_data:
            return

        if self.runner.is_running():
            return

        defaults = {
            "鍵盤輸入": {"type": "key", "key": "", "hold_ms": 120},
            "滑鼠點擊": {"type": "click", "x": 0, "y": 0},
            "等待": {"type": "wait", "seconds": 1},
        }

        command = defaults[self.kind_var.get()]

        command["note"] = ""

        self.current_data["commands"].append(command)

        self.save_current()
        self.refresh_commands()

        self.root.update_idletasks()
        self.command_canvas.yview_moveto(1)

    def start_command_drag(self, event, index, row):
        if self.runner.is_running():
            return

        if not self.current_data:
            return

        self.root.focus_set()
        self.root.update_idletasks()

        x = row.winfo_rootx()
        y = row.winfo_rooty()
        width = row.winfo_width()
        height = row.winfo_height()

        image = ImageGrab.grab(
            bbox=(x, y, x + width, y + height),
            include_layered_windows=True,
            all_screens=True,
        ).convert("RGB")

        preview = tk.Toplevel(self.root)
        preview.withdraw()

        preview.overrideredirect(True)
        preview.attributes("-topmost", True)

        photo = ImageTk.PhotoImage(image)

        label = tk.Label(preview, image=photo, borderwidth=0, highlightthickness=0)

        label.image = photo
        label.pack()

        placeholder = tk.Label(
            row,
            text="",
            background=self.colors["placeholder"],
            relief="solid",
            borderwidth=1,
        )

        placeholder.place(x=0, y=0, relwidth=1, relheight=1)

        self.command_drag = {
            "index": index,
            "target": index,
            "row": row,
            "preview": preview,
            "placeholder": placeholder,
            "offset_x": event.x_root - x,
            "offset_y": event.y_root - y,
        }

        preview.geometry(f"{width}x{height}+{x}+{y}")

        preview.update_idletasks()
        preview.deiconify()

    def drag_command(self, event):
        if self.command_drag is None:
            return

        drag = self.command_drag
        row = drag["row"]

        x = event.x_root - drag["offset_x"]
        y = event.y_root - drag["offset_y"]

        drag["preview"].geometry(f"+{x}+{y}")

        rows = [widget for widget in self.commands.pack_slaves() if widget != row]

        target = len(rows)

        center_y = y + row.winfo_height() / 2

        for index, widget in enumerate(rows):
            middle = widget.winfo_rooty() + widget.winfo_height() / 2

            if center_y < middle:
                target = index
                break

        if target == drag["target"]:
            return

        if target < len(rows):
            row.pack_configure(before=rows[target])

        elif rows:
            row.pack_configure(after=rows[-1])

        drag["target"] = target

        self.root.update_idletasks()

    def finish_command_drag(self, event):
        if self.command_drag is None:
            return

        drag = self.command_drag
        self.command_drag = None

        drag["preview"].destroy()
        drag["placeholder"].destroy()

        index = drag["index"]
        target = drag["target"]

        if self.runner.is_running() or not self.current_data:
            self.refresh_commands()
            return

        if index != target:
            commands = self.current_data["commands"]

            command = commands.pop(index)
            commands.insert(target, command)

            self.save_current()

        self.refresh_commands()

    def delete_command(self, index):
        if self.runner.is_running():
            return

        if not self.current_data:
            return

        self.current_data["commands"].pop(index)

        self.save_current()
        self.refresh_commands()

    def capture_position(self, command, x_var, y_var):
        if self.runner.is_running():
            return

        window = find_window(self.window_var.get())

        if not window:
            messagebox.showerror("擷取失敗", "找不到唯一的目標視窗")
            return

        def receive(x, y):
            command["x"] = x
            command["y"] = y

            x_var.set(str(x))
            y_var.set(str(y))

            self.save_current()

        try:
            pick_coordinate(self.root, window["hwnd"], receive)
        except Exception as error:
            messagebox.showerror("擷取失敗", str(error))

    def register_hotkey(self):
        hotkeys = []
        errors = []

        running_paths = self.runner.get_running_paths()
        self.registered_running_paths = running_paths

        for path in self.manager.get_all_macros():
            macro = self.manager.load_macro(path)

            if macro.get("enabled", False) or path.resolve() in running_paths:
                hotkeys.append(macro.get("hotkey", ""))

        try:
            errors = self.hotkey.start(hotkeys)

            for error in errors:
                self.log(error)

            if not errors:
                self.log("快捷鍵已更新")

        except Exception as error:
            errors = [str(error)]
            self.log(str(error))

        self.update_status()

        return errors

    def configure_macro_hotkey(self, path):
        if self.runner.is_running():
            return

        if self.macro_hotkey_entry is not None:
            self.root.focus_set()
            return

        if not path or not path.is_file():
            return

        bounds = self.tree.bbox(str(path), "hotkey")

        if not bounds:
            return

        macro = self.manager.load_macro(path)
        old = macro.get("hotkey", "")

        value = ""

        self.hotkey.stop()

        def receive_key(key):
            nonlocal value
            value = key

        entry = self.create_key_capture(self.tree, "", receive_key)

        self.macro_hotkey_entry = entry

        entry.configure(justify="center", width=18)

        x, y, width, height = bounds

        entry.place(x=x, y=y, width=width, height=height)

        finished = False
        click_binding = None

        def finish(event=None, cancel=False):
            nonlocal finished, value

            if finished:
                return

            finished = True

            if cancel:
                value = old

            if click_binding is not None:
                self.root.unbind("<Button-1>", click_binding)

            self.macro_hotkey_entry = None
            entry.destroy()

            try:
                if value:
                    self.hotkey.parse(value)

                macro = self.manager.load_macro(path)
                macro["hotkey"] = value

                self.manager.save(path, macro)

                errors = self.register_hotkey()

                if errors:
                    macro["hotkey"] = old
                    self.manager.save(path, macro)

                    raise RuntimeError("\n".join(errors))

                if self.current_path == path:
                    self.current_data["hotkey"] = value

                if self.tree.exists(str(path)):
                    self.tree.set(str(path), "hotkey", value or "—")

            except Exception as error:
                messagebox.showerror("快捷鍵設定失敗", str(error))

            self.register_hotkey()
            self.update_status()

        def confirm(event=None):
            finish()
            return "break"

        def outside_click(event):
            if event.widget != entry:
                finish()

        entry.bind("<FocusOut>", finish, add="+")

        entry.bind("<Return>", confirm)

        entry.bind("<Escape>", lambda event: (finish(cancel=True), "break")[1])

        click_binding = self.root.bind("<Button-1>", outside_click, add="+")

        entry.focus_set()
        entry.select_range(0, tk.END)

    def toggle_macro(self):
        if not self.current_path:
            return

        if self.macro_hotkey_entry is not None:
            return

        path = self.current_path

        if self.runner.is_macro_running(path):
            self.runner.stop_macro(path)

        else:
            self.save_settings()

            macro = self.manager.load_macro(path)

            self.runner.start_macro(path, macro)

            self.register_hotkey()

        self.update_status()

    def handle_hotkey(self, hotkey):
        if self.macro_hotkey_entry is not None:
            return

        binding = self.hotkey.parse(hotkey)

        matched = {}

        for path in self.manager.get_all_macros():
            macro = self.manager.load_macro(path)

            if macro.get("hotkey") and self.hotkey.parse(macro["hotkey"]) == binding:
                matched[path] = macro

        running = [path for path in matched if self.runner.is_macro_running(path)]

        if running:
            for path in running:
                self.runner.stop_macro(path)

        else:
            enabled = {
                path: macro
                for path, macro in matched.items()
                if macro.get("enabled", False)
            }

            self.runner.start(enabled)

        self.update_status()

    def update_macro_status(self):
        if not self.current_path or not self.current_data:
            self.macro_start_button.config(
                text="執行",
                state="disabled",
                background=self.colors["green_disabled"],
                cursor="arrow",
            )

            self.macro_status_light.delete("all")

            self.macro_status_light.configure(cursor="")

            return

        macro = self.current_data

        running = self.runner.is_macro_running(self.current_path)

        enabled = macro.get("enabled", False)

        self.draw_status_light(
            self.macro_status_light,
            "running" if running else "enabled" if enabled else "idle",
        )

        self.macro_status_light.configure(cursor="" if running else "hand2")

        text = "停止" if running else "執行"

        self.macro_start_button.config(
            text=text,
            state="normal",
            background=self.colors["green"][0],
            cursor="hand2",
        )

    def update_tree_separators(self):
        self.tree_header_separator.configure(background=self.colors["separator"])

        for separator in self.tree_separators.values():
            separator.configure(background=self.colors["separator"])

        header_y = 0

        for y in range(self.tree.winfo_height()):
            region = self.tree.identify_region(10, y)

            if region == "heading":
                header_y = y

            elif header_y:
                break

        if header_y:
            self.tree_header_separator.place(
                x=1, y=header_y, width=self.tree.winfo_width() - 2, height=1
            )
        else:
            self.tree_header_separator.place_forget()

        visible = set()

        items = []

        for iid in self.tree.get_children():
            items.append(iid)
            items.extend(self.tree.get_children(iid))

        for iid in items:
            bounds = self.tree.bbox(iid)

            if not bounds:
                continue

            x, y, width, height = bounds

            line_y = y + height - 1

            if self.tree.identify_row(line_y) != iid:
                continue

            visible.add(iid)

            if iid not in self.tree_separators:
                self.tree_separators[iid] = tk.Frame(
                    self.tree,
                    background=self.colors["separator"],
                    height=1,
                    borderwidth=0,
                )

            self.tree_separators[iid].place(x=x, y=line_y, width=width, height=1)

        for iid in list(self.tree_separators):
            if iid not in visible:
                self.tree_separators.pop(iid).destroy()

    def update_tree_status(self):
        visible = set()

        for iid in self.tree.get_children():
            if self.update_item_status(iid):
                visible.add(iid)

            for child in self.tree.get_children(iid):
                if self.update_item_status(child):
                    visible.add(child)

        for iid in list(self.tree_status_lights):
            if iid not in visible:
                self.tree_status_lights.pop(iid).destroy()

        self.update_tree_separators()

    def on_macro_status_click(self, event):
        if not self.current_path or not self.current_data:
            return "break"

        return self.on_status_click(self.current_path)

    def on_status_click(self, path):
        if not self.can_toggle_enabled(path):
            return "break"

        self.root.focus_set()

        self.tree.selection_set(str(path))

        self.toggle_enabled(path)

        return "break"

    def scroll_tree_status(self, event):
        self.tree.yview_scroll(-int(event.delta / 120), "units")

        self.update_tree_status()

        return "break"

    def update_item_status(self, iid):
        bounds = self.tree.bbox(iid, "status")

        if not bounds:
            return False

        path = Path(iid)

        if path.is_dir():
            running = any(
                self.runner.is_macro_running(Path(child))
                for child in self.tree.get_children(iid)
            )

            enabled = self.tree.set(iid, "check") in ("☑", "▣")

        else:
            running = self.runner.is_macro_running(path)
            enabled = self.tree.set(iid, "check") == "☑"

        status = "running" if running else "enabled" if enabled else "idle"

        x, y, width, height = bounds

        center_x = x + width // 2
        center_y = y + height // 2

        if self.tree.identify_row(center_y) != iid:
            return False

        if iid not in self.tree_status_lights:
            canvas = self.create_status_light(self.tree)

            canvas.bind("<Button-1>", lambda event: "break")

            canvas.bind("<MouseWheel>", self.scroll_tree_status)

            self.tree_status_lights[iid] = canvas

        canvas = self.tree_status_lights[iid]

        style = ttk.Style()

        background = style.lookup(
            "Treeview",
            "background",
            ("selected",) if iid in self.tree.selection() else (),
        )

        if "drop_target" in self.tree.item(iid, "tags"):
            background = self.colors["drop_target"]

        canvas.configure(
            background=background or "#FFFFFF", cursor="" if running else "hand2"
        )

        self.draw_status_light(canvas, status)

        canvas.place(x=center_x - 9, y=center_y - 9)

        return True

    def update_status(self):
        self.update_macro_status()
        self.update_tree_status()

    def process_events(self):
        try:
            while True:
                kind, value = self.events.get_nowait()

                if kind == "log":
                    self.log(value)

                elif kind == "hotkey":
                    self.handle_hotkey(value)

        except Empty:
            pass

        if not getattr(self, "closing", False) and self.macro_hotkey_entry is None:
            if self.runner.get_running_paths() != getattr(
                self, "registered_running_paths", set()
            ):
                self.register_hotkey()

        self.update_status()
        self.root.after(100, self.process_events)

    def close(self):
        self.closing = True

        self.hotkey.stop()
        self.runner.stop()

        def finish():
            if self.runner.is_running():
                self.root.after(100, finish)
            else:
                self.root.destroy()

        finish()
