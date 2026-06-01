"""Auto-update checker for GitHub releases."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional

from .version import __version__

logger = logging.getLogger(__name__)

GITHUB_REPO = "sander541/pdf-excel-matcher"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _ssl_context():
    """Return an SSL context with certifi's CA bundle.

    In a PyInstaller frozen build the certifi data file is bundled into
    _MEIPASS/certifi/cacert.pem. Outside a frozen build, certifi.where()
    returns the correct path on its own.
    """
    import ssl
    import certifi

    if getattr(sys, "_MEIPASS", None):
        cafile = Path(sys._MEIPASS) / "certifi" / "cacert.pem"
    else:
        cafile = Path(certifi.where())
    return ssl.create_default_context(cafile=str(cafile))


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse version string (e.g., '0.1.0') into comparable tuple."""
    try:
        return tuple(int(x) for x in version_str.split('.'))
    except (ValueError, AttributeError):
        return (0,)


def is_newer_version(remote_version: str, current_version: str = __version__) -> bool:
    """Check if remote version is newer than current version."""
    return parse_version(remote_version) > parse_version(current_version)


def fetch_latest_release() -> Optional[dict]:
    """
    Fetch latest release info from GitHub API.

    Returns release dict with keys: tag_name, name, assets, etc.
    Returns None if fetch fails or no releases found.
    """
    try:
        ctx = _ssl_context()
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={"User-Agent": f"pdf-excel-annotator/{__version__}"},
        )
        with urllib.request.urlopen(req, timeout=10, context=ctx) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data
    except Exception as exc:
        logger.warning("Failed to fetch latest release: %s", exc, exc_info=True)

    return None


def get_download_url_for_platform(release: dict) -> Optional[str]:
    """
    Extract download URL for the current platform from release assets.

    Windows  → first -setup.exe asset (Inno Setup installer)
    macOS    → first -macos.zip asset
    Linux    → first .tar.gz asset
    """
    assets = release.get("assets", [])

    if sys.platform == "win32":
        suffixes = ("-setup.exe",)
    elif sys.platform == "darwin":
        suffixes = ("-macos.zip",)
    else:
        suffixes = (".tar.gz",)

    for suffix in suffixes:
        for asset in assets:
            if asset["name"].endswith(suffix):
                return asset["browser_download_url"]

    return None


def download_file(url: str, dest_path: Path) -> bool:
    """Download file from URL to destination path."""
    try:
        logger.info("Downloading %s", url)
        ctx = _ssl_context()
        req = urllib.request.Request(
            url,
            headers={"User-Agent": f"pdf-excel-annotator/{__version__}"},
        )
        with urllib.request.urlopen(req, timeout=60, context=ctx) as response:
            dest_path.write_bytes(response.read())
        return True
    except Exception as exc:
        logger.error("Failed to download update: %s", exc, exc_info=True)
        return False



def restart_application(exe_path: Path) -> None:
    """Exit the current process after an update.

    On Windows the Inno Setup installer re-launches the app automatically,
    so we just close this instance. On other platforms we attempt to relaunch.
    """
    try:
        if sys.platform != "win32":
            subprocess.Popen([str(exe_path)])
        sys.exit(0)
    except Exception as exc:
        logger.error("Failed to exit after update: %s", exc)


def check_for_updates(
    current_version: str = __version__,
) -> Optional[dict]:
    """
    Check if a new version is available.

    Returns update info dict with:
    - version: new version string
    - url: download URL
    - release: full release info from GitHub

    Returns None if no update available or check fails.
    """
    release = fetch_latest_release()
    if not release:
        return None

    remote_version = release.get("tag_name", "").lstrip("v")

    if not remote_version or not is_newer_version(remote_version, current_version):
        logger.debug(f"No update available. Current: {current_version}, Remote: {remote_version}")
        return None

    download_url = get_download_url_for_platform(release)
    if not download_url:
        logger.warning(f"No suitable download URL found for platform {sys.platform}")
        return None

    return {
        "version": remote_version,
        "url": download_url,
        "release": release,
    }


def perform_update(update_info: dict, current_exe_path: Path) -> bool:
    """
    Download and install update.

    Windows: downloads the Inno Setup installer and launches it silently.
             The installer handles replacing the app; this process exits afterward.
    macOS / Linux: not supported — user is directed to the releases page.

    Returns True if the installer was launched successfully, False otherwise.
    """
    if sys.platform != "win32":
        logger.warning(
            "Auto-install is not supported on this platform (%s). "
            "Please download the latest release manually from: "
            "https://github.com/%s/releases",
            sys.platform,
            GITHUB_REPO,
        )
        return False

    download_url = update_info["url"]
    # Use mkdtemp (not TemporaryDirectory) so the file persists after this
    # function returns — the installer process outlives this Python process.
    temp_dir = Path(tempfile.mkdtemp(prefix="pdf_annotator_upd_"))
    temp_installer = temp_dir / "pdf-excel-annotator-setup.exe"

    if not download_file(download_url, temp_installer):
        return False

    try:
        logger.info("Launching installer: %s", temp_installer)
        subprocess.Popen(
            [str(temp_installer), "/SILENT", "/NORESTART"],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        return True
    except Exception as exc:
        logger.error("Failed to launch installer: %s", exc)
        return False
