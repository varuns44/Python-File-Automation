import tkinter as tk
from tkinter import filedialog, ttk
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import shutil


folder = Path.home() / "Downloads"

file_types = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
    "Documents": [".pdf", ".docx", ".txt", ".doc", ".xlsx", ".pptx"],
    "Videos": [".mp4", ".mkv", ".avi", ".mov"],
    "Music": [".mp3", ".wav", ".acc"],
    "Python": [".py", ".java", ".c", ".cpp", ".html", ".js"],
    "Archives": [".zip", ".rar"],
    "Applications": [".exe", ".msi"],
}


def move_file(file):
    if not file.is_file():
        return

    category = "Others"
    for name, extensions in file_types.items():
        if file.suffix.lower() in extensions:
            category = name
            break

    destination = folder / category
    destination.mkdir(exist_ok=True)
    target = destination / file.name

    if target.exists():
        print(f"Skipped: {file.name}")
        return

    try:
        shutil.move(str(file), str(target))
        print(f"Moved: {file.name}")
    except OSError as error:
        print(f"Could not move {file.name}: {error}")


def organize_all():
    if not folder.is_dir():
        print("Folder not found!")
        return

    files = list(folder.iterdir())
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(move_file, files))

    print("Python File Automation Process Completed!")


def launch_gui():
    root = tk.Tk()
    root.title("File Organizer")

    panel = ttk.Frame(root, padding=16)
    panel.grid(sticky="nsew")
    panel.columnconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)

    selected_folder = tk.StringVar(value=str(folder))
    status = tk.StringVar(value="Choose a folder to organize.")

    def browse():
        directory = filedialog.askdirectory(parent=root)
        if directory:
            selected_folder.set(directory)

    def check_progress(future):
        if not future.done():
            root.after(100, check_progress, future)
            return

        try:
            future.result()
        except Exception as error:
            status.set(f"Could not finish organizing: {error}")
        else:
            status.set("Finished. See the terminal for file-by-file results.")
        finally:
            organize_button.state(["!disabled"])

    def start_organizing():
        global folder

        entered_path = selected_folder.get().strip()
        if not entered_path or not Path(entered_path).expanduser().is_dir():
            status.set("Choose an existing folder.")
            return

        folder = Path(entered_path).expanduser()
        organize_button.state(["disabled"])
        status.set("Organizing files…")

        future = worker.submit(organize_all)
        root.after(100, check_progress, future)

    ttk.Label(panel, text="Folder").grid(row=0, column=0, sticky="w")
    ttk.Entry(panel, textvariable=selected_folder, width=45).grid(
        row=1, column=0, sticky="ew", padx=(0, 8)
    )
    ttk.Button(panel, text="Browse…", command=browse).grid(row=1, column=1)

    organize_button = ttk.Button(
        panel, text="Organize Files", command=start_organizing
    )
    organize_button.grid(row=2, column=0, sticky="w", pady=12)

    ttk.Label(panel, textvariable=status).grid(
        row=3, column=0, columnspan=2, sticky="w"
    )

    with ThreadPoolExecutor(max_workers=1) as worker:
        root.mainloop()


if __name__ == "__main__":
    launch_gui()
        
