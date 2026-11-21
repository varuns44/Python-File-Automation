from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import shutil

# folder to be organized
folder = Path.home() / "Downloads"

# file categories
file_types = {
    "Images": [".jpg", ".jpeg", ".png", ".gif",".webp"],
    "Documents": [".pdf", ".docx", ".txt",".doc",".xlsx",".pptx"],
    "Videos": [".mp4", ".mkv", ".avi",".mov"],
    "Music": [".mp3", ".wav",".acc"],
    "Python": [".py",".java",".c",".cpp",".html",".js"],
    "Archives": [".zip", ".rar"],
    "Applications": [".exe",".msi"]
}

def move_file(file):
    if not file.is_file():
        return

    #To catergorise files
    category = "Others"

    for name, extensions in file_types.items():
        if file.suffix.lower() in extensions:
            category = name
            break

    destination = folder / category
    destination.mkdir(exist_ok=True)

    target = destination / file.name

    # Avoid overwriting an existing file
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
    
    #Access to files inside Downloads folder
    files = list(folder.iterdir())

    #Automation
    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(move_file, files))

    print("Python File Automation Process Completed!")

organize_all()

        
