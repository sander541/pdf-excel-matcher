# Distribution — PDF ↔ Excel Annotator

## Overview

| Platform | Artifact | How it installs |
|----------|----------|-----------------|
| Windows  | `pdf-excel-annotator-setup.exe` | Inno Setup installer → `Program Files\PDF Excel Annotator` |
| macOS    | `pdf-excel-annotator-macos.zip` | Unzip → drag `.app` anywhere |
| Linux    | `pdf-excel-annotator-linux.tar.gz` | Extract → run the binary directly |

All three are built automatically by GitHub Actions and attached to every release.

---

## Releasing a new version

Everything is automated. You only need to trigger the workflow:

1. Go to **Actions → Release** in the GitHub repository.
2. Click **Run workflow**.
3. Enter the version number (e.g. `1.2.0`) and optional release notes.
4. Click **Run workflow**.

The workflow will:
- Bump `pdf_excel_annotator/version.py` and `pyproject.toml`.
- Commit the bump, create and push the `v1.2.0` tag.
- Create the GitHub Release.
- Build Windows, macOS, and Linux artifacts in parallel.
- Upload all artifacts to the release automatically.

The release page at `https://github.com/sander541/pdf-excel-matcher/releases/latest`
will show all three download links when the build finishes (~5–10 min).

---

## Local build (for development / testing)

### Prerequisites
- Python 3.11
- Virtual environment with dependencies: `pip install -r requirements.txt`
- PyInstaller: `pip install pyinstaller`

### Build steps

```bash
# Activate the virtual environment
source .venv/bin/activate          # macOS / Linux
.venv\Scripts\activate             # Windows

# Build the app bundle
pyinstaller pdf-excel-annotator.spec
```

Output:
- **Windows / Linux:** `dist/pdf-excel-annotator/` — a directory containing the exe and all dependencies under `_internal/`.
- **macOS:** `dist/pdf-excel-annotator.app` — a self-contained `.app` bundle.

### Build the Windows installer locally (requires Inno Setup)

```bash
# After running PyInstaller:
iscc /DVersion=1.2.0 pdf-excel-annotator.iss
# Output: dist/installer/pdf-excel-annotator-setup.exe
```

### Package macOS build

```bash
ditto -c -k --sequesterRsrc --keepParent dist/pdf-excel-annotator.app pdf-excel-annotator-macos.zip
```

### Package Linux build

```bash
tar -czf pdf-excel-annotator-linux.tar.gz -C dist pdf-excel-annotator
```

---

## Auto-update mechanism

1. On startup the app spawns a background thread that calls the GitHub Releases API (10 s timeout, non-blocking).
2. If a newer tag is found, a dialog asks the user whether to update.
3. The user clicks **Update** → a progress dialog appears while the installer/archive is downloaded.
4. **Windows:** The Inno Setup installer runs silently; it closes the old app and relaunches it automatically.
5. **macOS / Linux:** The user is directed to the releases page (auto-install is not supported on these platforms).

SSL certificates are bundled via `certifi` so the update check works in the frozen app without relying on the system CA store.

### Configuration

All update settings live in `pdf_excel_annotator/updater.py`:

| Constant | Value | Purpose |
|----------|-------|---------|
| `GITHUB_REPO` | `sander541/pdf-excel-matcher` | Repo to query for releases |
| `GITHUB_API_URL` | derived | GitHub Releases API endpoint |
| Timeout (fetch) | 10 s | Aborts silently if GitHub unreachable |
| Timeout (download) | 60 s | Download timeout |

---

## Distribution to users

Share the direct link to the latest release:

```
https://github.com/sander541/pdf-excel-matcher/releases/latest
```

Users download the installer/archive for their platform, install once, and receive all future updates automatically on app launch.

---

## Version management

| Location | Purpose |
|----------|---------|
| `pdf_excel_annotator/version.py` | Single source of truth (`__version__`) |
| `pyproject.toml` | Mirrors `version.py` |
| `pdf-excel-annotator.spec` | Reads `__version__` for macOS bundle metadata |
| GitHub tag | `v1.2.0` format, created by the release workflow |

---

## Troubleshooting

| Problem | Check |
|---------|-------|
| App won't update | Is GitHub reachable? Is `GITHUB_REPO` correct? Check `pdf-excel-annotator.log` next to the exe. |
| Windows SmartScreen warning | Download reputation builds over time. See **More info → Run anyway**. Code signing is a future improvement. |
| Update download fails | Check `pdf-excel-annotator.log` for SSL or network errors. |
| Manual fallback | Download the latest installer from the releases page and run it manually. |

---

## Future improvements

- [ ] Code signing certificate (removes SmartScreen warning on Windows)
- [ ] macOS notarization (removes Gatekeeper quarantine)
- [ ] Delta / patch updates (smaller downloads)
- [ ] Beta / canary release channel
