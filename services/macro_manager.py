import json
import re
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
MACROS_DIR = DATA_DIR / "macros"
CONFIG_PATH = DATA_DIR / "config.json"


class MacroManager:
    def __init__(self):
        MACROS_DIR.mkdir(parents=True, exist_ok=True)

    def validate_name(self, name):
        name = name.strip()

        if (
            not name
            or name in (".", "..")
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or name.endswith(".")
        ):
            raise ValueError("名稱不合法")

        if Path(name).is_reserved():
            raise ValueError("不能使用 Windows 保留名稱")

        return name

    def unique_path(self, path):
        if not path.exists():
            return path

        index = 2

        while True:
            candidate = path.with_name(
                f"{path.stem} ({index}){path.suffix}"
            )

            if not candidate.exists():
                return candidate

            index += 1

    def get_folders(self):
        return sorted(
            [
                path for path in MACROS_DIR.iterdir()
                if path.is_dir()
            ],
            key=lambda path: path.name.casefold()
        )

    def get_macros(self, folder=None):
        directory = Path(folder) if folder else MACROS_DIR

        return sorted(
            directory.glob("*.json"),
            key=lambda path: path.name.casefold()
        )

    def get_all_macros(self):
        macros = self.get_macros()

        for folder in self.get_folders():
            macros.extend(self.get_macros(folder))

        return macros

    def load(self, path):
        with Path(path).open("r", encoding="utf-8") as file:
            return json.load(file)

    def load_macro(self, path):
        data = self.load(path)

        if "hotkey" not in data:
            data["hotkey"] = ""

            self.save(path, data)

        return data

    def save(self, path, data):
        path = Path(path)
        temporary = path.with_suffix(path.suffix + ".tmp")

        with temporary.open("w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )

        temporary.replace(path)

    def create_macro(self, name, folder=None):
        name = self.validate_name(name)
        directory = Path(folder) if folder else MACROS_DIR

        path = self.unique_path(
            directory / f"{name}.json"
        )

        data = {
            "name": path.stem,
            "enabled": False,
            "hotkey": "",
            "window_title": "",
            "repeat": {
                "mode": "once",
                "interval": 30
            },
            "commands": []
        }

        self.save(path, data)

        return path

    def create_folder(self, name):
        name = self.validate_name(name)
        path = MACROS_DIR / name

        if path.exists():
            raise FileExistsError("資料夾名稱已存在")

        path.mkdir()

        return path

    def rename_macro(self, path, name):
        path = Path(path)
        name = self.validate_name(name)

        destination = path.with_name(f"{name}.json")

        if destination == path:
            return path

        if destination.exists():
            raise FileExistsError("巨集名稱已存在")

        data = self.load(path)
        data["name"] = name

        path.rename(destination)
        self.save(destination, data)

        return destination

    def rename_folder(self, path, name):
        path = Path(path)
        name = self.validate_name(name)

        destination = MACROS_DIR / name

        if destination == path:
            return path

        if destination.exists():
            raise FileExistsError("資料夾名稱已存在")

        path.rename(destination)

        return destination

    def delete_macro(self, path):
        Path(path).unlink()

    def delete_folder(self, folder):
        folder = Path(folder)

        if folder.parent != MACROS_DIR:
            raise ValueError("只能刪除巨集資料夾")

        for path in self.get_macros(folder):
            self.move_macro(path)

        folder.rmdir()

    def move_macro(self, path, folder=None):
        path = Path(path)
        directory = Path(folder) if folder else MACROS_DIR

        if path.parent == directory:
            return path

        if directory != MACROS_DIR:
            if directory.parent != MACROS_DIR:
                raise ValueError("不支援巢狀資料夾")

        destination = self.unique_path(
            directory / path.name
        )

        data = self.load(path)
        data["name"] = destination.stem

        path.rename(destination)
        self.save(destination, data)

        return destination

    def set_enabled(self, path, enabled):
        data = self.load(path)
        data["enabled"] = bool(enabled)
        self.save(path, data)

    def set_folder_enabled(self, folder, enabled):
        for path in self.get_macros(folder):
            self.set_enabled(path, enabled)

    def get_folder_state(self, folder):
        states = [
            self.load(path).get("enabled", False)
            for path in self.get_macros(folder)
        ]

        if not states or not any(states):
            return "unchecked"

        if all(states):
            return "checked"

        return "partial"

    def get_enabled_macros(self):
        macros = {}

        for path in self.get_all_macros():
            data = self.load_macro(path)

            if data.get("enabled", False):
                macros[path] = data

        return macros

    def load_config(self):
        if not CONFIG_PATH.exists():
            return {}

        return self.load(CONFIG_PATH)

    def save_config(self, config):
        self.save(CONFIG_PATH, config)
