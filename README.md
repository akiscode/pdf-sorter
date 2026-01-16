# PDF Sorter (Local Web App)

A small, self-contained local web app for rapidly previewing, renaming, and sorting PDF files.

Open a folder of PDFs in your browser, review them one-by-one with a full PDF preview, rename files, move them into folders (including custom nested folders), and work efficiently using keyboard shortcuts.

No cloud services. No uploads. Files never leave your machine.

---

## Features

- Inline PDF preview using a local PDF.js viewer (same-origin)
- Rename PDFs in place
- Move PDFs to:
  - preset folders
  - arbitrary custom folders (nested folders supported)
- Persistent recent-folder chips
  - remembered across restarts
  - one-click fill for fast filing
- Keyboard-driven workflow
- Safe trash (moves files into `_trash/`, no deletion)
- Local-only execution
  - binds to `127.0.0.1`
  - no network access required after first run

---

## Requirements

- Python 3.9+
- A modern browser (Chrome, Firefox, Edge, Safari)

Python dependency:
- flask

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/akiscode/pdf-sorter.git
cd pdf-sorter
```

Or download `pdf_sorter.py` directly.

---

### 2. Install dependencies

```bash
pip install flask 
```
or 
```bash
python3 -m pip install flask
```

---

### 3. Run the app

```bash
python pdf_sorter.py /path/to/your/pdf/folder
```

Example (Windows / PowerShell):

```powershell
python .\pdf_sorter.py "$env:USERPROFILE\Desktop\pdfs"
```

Example (macOS / Linux):

```bash
python pdf_sorter.py ~/Desktop/pdfs
```

---

### 4. Open in your browser

```
http://127.0.0.1:5055
```

---

## Usage

### Keyboard shortcuts

| Key | Action |
| --- | --- |
| j / → | Next PDF |
| k / ← | Previous PDF |
| r | Focus rename box |
| m | Focus move-folder box |
| Enter | Submit focused form |

Shortcuts are ignored while typing in input fields.

---

### Renaming files

1. Press `r`
2. Type the new filename
3. Press `Enter`

`.pdf` is automatically appended if missing.

---

### Moving files

Files can be moved in two ways.

#### Preset folders
Choose a destination from the dropdown and click **Move**.

#### Custom folders
Type any folder path relative to the root folder:

```
Invoices/2025
Reports/Quarterly
Scans/Archive
```

Folders are created automatically if they do not exist.

---

### Recent folder chips

- Every successful move adds the destination to **Recent folders**
- Chips persist across restarts in `_recent_folders.json`
- Clicking a chip fills the move box (does not auto-move)
- Use **Clear recents** to reset the list

---

### Trash

Click **Trash** to move the file into:

```
<root folder>/_trash/
```

Files are never permanently deleted.

---

## Command-line options

```bash
python pdf_sorter.py <folder> [options]
```

| Option | Description |
| --- | --- |
| --port 5055 | Port to run on |
| --host 127.0.0.1 | Host (local-only by default) |
| --dests "_sorted,_keep,_review" | Preset destination folders |

Example:

```bash
python pdf_sorter.py ~/Desktop/pdfs --dests "_sorted,Invoices,Reports,Archive"
```

---

## Files created by the app

| File / Folder | Purpose |
| --- | --- |
| _pdfjs/ | Local PDF.js viewer (auto-downloaded) |
| _recent_folders.json | Persistent recent-folder list |
| _trash/ | Safe trash folder |

All files are created next to `pdf_sorter.py`.

---

## Security notes

- Files are never uploaded
- The app binds to `127.0.0.1` by default
- All paths are sanitized
- Destination folders are restricted to the chosen root directory

---

## Known limitations

- Folder scanning is non-recursive by design
- Only PDF files are shown
- Single-user, single-folder workflow

---

## Roadmap / ideas

- Auto-advance after rename or move
- One-click chip auto-move
- Undo last move
- Optional recursive mode
- OCR-based filename suggestions

Pull requests welcome.

---

## License

MIT License.

---

## Why this exists

This tool was built to quickly sort large, unstructured collections of PDF documents where traditional file-manager workflows are slow or error-prone.

If it is useful to you, that is the goal.
