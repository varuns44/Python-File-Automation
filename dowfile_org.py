from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from pathlib import Path
import shutil


DEFAULT_FOLDER = Path.home() / "Downloads"

file_types = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
    "Documents": [".pdf", ".docx", ".txt", ".doc", ".xlsx", ".pptx"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov"],
    "Music": [".mp3", ".wav", ".acc"],
    "Python": [".py", ".java", ".c", ".cpp", ".html", ".js"],
    "Archives": [".zip", ".rar"],
    "Applications": [".exe", ".msi"],
}


@dataclass(frozen=True)
class FileResult:
    name: str
    category: str
    status: str
    detail: str = ""


def move_file(file, folder):
    if not file.is_file():
        return

    category = "Others"
    for name, extensions in file_types.items():
        if file.suffix.lower() in extensions:
            category = name
            break

    destination = folder / category
    target = destination / file.name

    try:
        destination.mkdir(exist_ok=True)
        if target.exists() or target.is_symlink():
            return FileResult(file.name, category, "skipped", "A file with this name already exists.")
        shutil.move(str(file), str(target))
        return FileResult(file.name, category, "moved")
    except OSError as error:
        return FileResult(file.name, category, "failed", str(error))


def organize_all(folder):
    if not folder.is_dir():
        raise NotADirectoryError("Choose an existing folder.")

    files = sorted(folder.iterdir())
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(partial(move_file, folder=folder), files))

    return [result for result in results if result is not None]
