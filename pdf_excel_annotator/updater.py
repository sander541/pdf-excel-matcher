"""Auto-update checker for GitHub releases."""

from __future__ import annotations

import json
import logging
import os
import shutil
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
        with urllib.request.urlopen(GITHUB_API_URL, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data
    except Exception as exc:
        logger.debug(f"Failed to fetch latest release: {exc}")

    return None


def get_download_url_for_platform(release: dict) -> Optional[str]:
    """
    Extract download URL for the current platform from release assets.

    Windows  → first .exe asset
    macOS    → first .dmg asset, falling back to .zip
    Linux    → first .AppImage asset, falling back to .tar.gz
    """
    assets = release.get("assets", [])

    if sys.platform == "win32":
        suffixes = (".exe",)
    elif sys.platform == "darwin":
        suffixes = (".dmg", ".zip")
    else:
        suffixes = (".AppImage", ".tar.gz")

    for suffix in suffixes:
        for asset in assets:
            if asset["name"].endswith(suffix):
                return asset["browser_download_url"]

    return None


def download_file(url: str, dest_path: Path) -> bool:
    """Download file from URL to destination path."""
    try:
        logger.info(f"Downloading {url}")
        urllib.request.urlretrieve(url, dest_path)
        return True
    except Exception as exc:
        logger.error(f"Failed to download update: {exc}")
        return False


def replace_executable(new_exe_path: Path, current_exe_path: Path) -> bool:
    """
    Replace current executable with new one.

    On Windows, this requires the current process to not have the file locked.
    The caller should ensure the app is closed properly before calling this.
    """
    try:
        # Ensure paths are absolute
        new_exe = Path(new_exe_path).resolve()
        current_exe = Path(current_exe_path).resolve()

        if not new_exe.exists():
            logger.error(f"New executable not found: {new_exe}")
            return False

        # On Windows, we need to copy to a temp location first, then replace
        if sys.platform == "win32":
            # Copy new exe over current exe
            # This may fail if the file is still in use
            shutil.copy2(new_exe, current_exe)
        else:
            # On Unix-like systems, atomic replace is safer
            new_exe.replace(current_exe)

        # Clean up temp file
        try:
            new_exe.unlink()
        except Exception:
            pass

        logger.info(f"Successfully replaced executable: {current_exe}")
        return True
    except Exception as exc:
        logger.error(f"Failed to replace executable: {exc}")
        return False


def restart_application(exe_path: Path) -> None:
    """Restart the application with the new executable."""
    try:
        if sys.platform == "win32":
            # On Windows, use os.startfile or subprocess
            os.startfile(str(exe_path))
        else:
            # On Unix-like systems
            subprocess.Popen([str(exe_path)])

        # Exit current process
        sys.exit(0)
    except Exception as exc:
        logger.error(f"Failed to restart application: {exc}")


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

    Auto-install is currently Windows-only: the release asset is a self-contained
    .exe that can be swapped in-place. On macOS the asset is a .zip and on Linux
    a .tar.gz — extracting those archives and locating the correct binary inside
    requires knowledge of the archive layout that may vary between releases.
    Users on those platforms are directed to the releases page instead.

    Returns True if successful, False otherwise.
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
    suffix = Path(download_url.split("?")[0]).suffix or ".exe"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_asset = Path(temp_dir) / f"pdf_annotator_update{suffix}"

        if not download_file(download_url, temp_asset):
            return False

        if not replace_executable(temp_asset, current_exe_path):
            return False

    return True
