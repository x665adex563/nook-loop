import ctypes
import tkinter as tk

from ui.gui import App


def main():
    ctypes.windll.user32.SetProcessDPIAware()

    root = tk.Tk()

    App(root)

    root.mainloop()


if __name__ == "__main__":
    main()
