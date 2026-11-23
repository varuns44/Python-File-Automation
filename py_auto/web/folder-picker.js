(() => {
  const dialog = document.querySelector("#folder-picker");
  if (typeof dialog.showModal !== "function") return;

  const browse = document.querySelector("#browse");
  const folderInput = document.querySelector("#folder");
  const selectionStatus = document.querySelector("#folder-selection");
  const token = document.querySelector("#form-token").value;
  const pathLabel = document.querySelector("#picker-path");
  const message = document.querySelector("#picker-message");
  const locations = document.querySelector("#folder-locations");
  const folderList = document.querySelector("#folder-list");
  const parentButton = document.querySelector("#parent-folder");
  const selectButton = document.querySelector("#select-folder");
  let current = null;
  let pending = null;

  function folderButton(folder, className) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = className;
    button.textContent = folder.name;
    button.addEventListener("click", () => loadFolder(folder.path));
    return button;
  }

  async function loadFolder(path, fallback = false) {
    pending?.abort();
    const controller = new AbortController();
    pending = controller;
    parentButton.disabled = true;
    selectButton.disabled = true;
    message.textContent = "Loading folders…";

    try {
      const response = await fetch("/browse", {
        method: "POST",
        body: new URLSearchParams({ folder: path, token }),
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (response.status === 400 && fallback && path) return loadFolder("");
      if (response.status === 403) throw new Error("Refresh the page to open the folder picker.");
      if (!response.ok) throw new Error("This folder could not be opened.");

      const listing = await response.json();
      if (controller.signal.aborted) return;
      current = listing;
      pathLabel.textContent = current.path;
      locations.replaceChildren(...current.locations.map(folder => folderButton(folder, "secondary")));
      const entries = document.createDocumentFragment();
      for (const folder of current.children) {
        const entry = document.createElement("li");
        entry.append(folderButton(folder, ""));
        entries.append(entry);
      }
      folderList.replaceChildren(entries);
      folderList.scrollTop = 0;
      if (path) pathLabel.focus();
      message.textContent = current.children.length ? "" : "No subfolders here.";
    } catch (error) {
      if (!controller.signal.aborted) message.textContent = error.message;
    } finally {
      if (pending === controller) {
        pending = null;
        parentButton.disabled = !current?.parent;
        selectButton.disabled = !current;
      }
    }
  }

  browse.addEventListener("click", () => {
    current = null;
    pathLabel.textContent = "Choose where to organize files.";
    locations.replaceChildren();
    folderList.replaceChildren();
    dialog.showModal();
    loadFolder(folderInput.value.trim(), true);
  });
  parentButton.addEventListener("click", () => {
    if (current?.parent) loadFolder(current.parent);
  });
  selectButton.addEventListener("click", () => {
    if (!current) return;
    folderInput.value = current.path;
    dialog.close();
    selectionStatus.textContent = "Folder is selected.";
  });
  folderInput.addEventListener("input", () => {
    selectionStatus.textContent = "";
  });
  dialog.addEventListener("close", () => {
    pending?.abort();
    pending = null;
  });
  browse.hidden = false;
})();
