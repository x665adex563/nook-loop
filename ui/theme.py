import ctypes
from tkinter import ttk
from ctypes import wintypes

LIGHT = {
    "background": "#F0F0F0",
    "sidebar": "#FFFFFF",
    "surface": "#E5E5E5",
    "input": "#FFFFFF",
    "border": "#CCCCCC",
    "foreground": "#333333",
    "muted": "#808080",
    "selection": "#CCE4F7",
    "separator": "#E5E5E5",
    "drop_target": "#C8E6C9",
    "placeholder": "#D9D9D9",
    "icon": "#404040",
    "blue": ("#DCEEFF", "#C5E2FA", "#245A85"),
    "green": ("#D9EFD9", "#C1E3C1", "#285C35"),
    "green_disabled": "#DFE7DF",
    "disabled_foreground": "#909E90"
}

DARK = {
    "background": "#22272E",
    "sidebar": "#1C2128",
    "surface": "#2D333B",
    "input": "#181D23",
    "border": "#444C56",
    "foreground": "#CDD9E5",
    "muted": "#768390",
    "selection": "#364B60",
    "separator": "#30363D",
    "drop_target": "#315C40",
    "placeholder": "#373E47",
    "icon": "#CDD9E5",
    "blue": ("#315D80", "#40749C", "#E1F0FF"),
    "green": ("#315C40", "#40754F", "#D9EFD9"),
    "green_disabled": "#303D35",
    "disabled_foreground": "#76877C"
}

THEMES = {
    "light": LIGHT,
    "dark": DARK
}

def apply_ttk_theme(root, theme, light_theme):
    style = ttk.Style(root)

    if theme == "dark":
        root.option_add(
            "*TCombobox*Listbox.background",
            DARK["input"]
        )
        root.option_add(
            "*TCombobox*Listbox.foreground",
            DARK["foreground"]
        )
        root.option_add(
            "*TCombobox*Listbox.selectBackground",
            DARK["selection"]
        )
        root.option_add(
            "*TCombobox*Listbox.selectForeground",
            DARK["foreground"]
        )
    else:
        root.option_add(
            "*TCombobox*Listbox.background",
            "SystemWindow"
        )
        root.option_add(
            "*TCombobox*Listbox.foreground",
            "SystemWindowText"
        )
        root.option_add(
            "*TCombobox*Listbox.selectBackground",
            "SystemHighlight"
        )
        root.option_add(
            "*TCombobox*Listbox.selectForeground",
            "SystemHighlightText"
        )

    if theme == "light":
        style.theme_use(light_theme)

        root.configure(
            background=style.lookup("TFrame", "background")
        )

        return

    colors = DARK

    style.theme_use("clam")

    root.configure(
        background=colors["background"]
    )

    style.configure(
        ".",
        background=colors["background"],
        foreground=colors["foreground"],
        bordercolor=colors["border"],
        lightcolor=colors["border"],
        darkcolor=colors["border"],
        troughcolor=colors["sidebar"],
        fieldbackground=colors["input"],
        selectbackground=colors["selection"],
        selectforeground=colors["foreground"],
        arrowcolor=colors["foreground"],
        insertcolor=colors["foreground"]
    )

    style.configure(
        "TButton",
        background=colors["surface"],
        foreground=colors["foreground"]
    )

    style.map(
        "TButton",
        background=[
            ("disabled", colors["sidebar"]),
            ("pressed", colors["selection"]),
            ("active", colors["border"])
        ],
        foreground=[
            ("disabled", colors["muted"])
        ]
    )

    style.configure(
        "TEntry",
        fieldbackground=colors["input"]
    )

    style.map(
        "TEntry",
        fieldbackground=[
            ("disabled", colors["sidebar"]),
            ("readonly", colors["input"])
        ],
        foreground=[
            ("disabled", colors["muted"])
        ]
    )

    style.configure(
        "TCombobox",
        background=colors["surface"],
        fieldbackground=colors["input"]
    )

    style.map(
        "TCombobox",
        fieldbackground=[
            ("readonly", colors["input"]),
            ("disabled", colors["sidebar"])
        ],
        foreground=[
            ("disabled", colors["muted"]),
            ("readonly", colors["foreground"])
        ],
        background=[
            ("active", colors["border"])
        ]
    )

    style.configure(
        "Treeview",
        background=colors["sidebar"],
        fieldbackground=colors["sidebar"],
        foreground=colors["foreground"]
    )

    style.map(
        "Treeview",
        background=[
            ("selected", colors["selection"])
        ],
        foreground=[
            ("selected", colors["foreground"])
        ]
    )

    style.configure(
        "Treeview.Heading",
        background=colors["surface"],
        foreground=colors["foreground"],
        relief="flat"
    )

    style.map(
        "Treeview.Heading",
        background=[
            ("active", colors["border"])
        ]
    )

    style.configure(
        "TCheckbutton",
        indicatorbackground=colors["input"],
        indicatorforeground=colors["foreground"]
    )

    style.map(
        "TCheckbutton",
        background=[
            ("active", colors["background"])
        ],
        foreground=[
            ("disabled", colors["muted"])
        ],
        indicatorbackground=[
            ("selected", colors["selection"])
        ]
    )

    style.configure(
        "TScrollbar",
        background=colors["border"],
        troughcolor=colors["sidebar"]
    )

    style.map(
        "TScrollbar",
        background=[
            ("active", colors["muted"])
        ]
    )

def apply_titlebar_theme(root, theme):
    get_parent = ctypes.windll.user32.GetParent
    get_parent.argtypes = [wintypes.HWND]
    get_parent.restype = wintypes.HWND

    hwnd = get_parent(root.winfo_id())

    value = ctypes.c_int(
        1 if theme == "dark" else 0
    )

    for attribute in (20, 19):
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            attribute,
            ctypes.byref(value),
            ctypes.sizeof(value)
        )

        if result == 0:
            user32 = ctypes.windll.user32

            WM_NCACTIVATE = 0x0086

            user32.SendMessageW(
                wintypes.HWND(hwnd),
                WM_NCACTIVATE,
                0,
                0
            )

            user32.SendMessageW(
                wintypes.HWND(hwnd),
                WM_NCACTIVATE,
                1,
                0
            )

            break
