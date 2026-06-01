"""Tests for the auto-update logic — runs on any platform, no network needed."""

from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pdf_excel_annotator.updater import (
    check_for_updates,
    fetch_latest_release,
    get_download_url_for_platform,
    is_newer_version,
    parse_version,
)


# ── Version parsing ───────────────────────────────────────────────────────────

def test_parse_version_basic():
    assert parse_version("1.2.3") == (1, 2, 3)

def test_parse_version_zeros():
    assert parse_version("0.0.0") == (0, 0, 0)

def test_parse_version_garbage():
    assert parse_version("not-a-version") == (0,)


# ── Version comparison ────────────────────────────────────────────────────────

def test_newer_version_detected():
    assert is_newer_version("1.0.1", "1.0.0") is True

def test_same_version_not_newer():
    assert is_newer_version("1.0.0", "1.0.0") is False

def test_older_version_not_newer():
    assert is_newer_version("0.9.9", "1.0.0") is False

def test_major_bump():
    assert is_newer_version("2.0.0", "1.9.9") is True


# ── Asset URL selection ───────────────────────────────────────────────────────

def _make_release(*asset_names: str) -> dict:
    return {
        "tag_name": "v1.2.3",
        "assets": [{"name": n, "browser_download_url": f"https://example.com/{n}"} for n in asset_names],
    }


def test_windows_picks_setup_exe():
    release = _make_release("pdf-excel-annotator-setup.exe", "pdf-excel-annotator-macos.zip")
    with patch.object(sys, "platform", "win32"):
        url = get_download_url_for_platform(release)
    assert url and url.endswith("pdf-excel-annotator-setup.exe")


def test_macos_picks_macos_zip():
    release = _make_release("pdf-excel-annotator-setup.exe", "pdf-excel-annotator-macos.zip")
    with patch.object(sys, "platform", "darwin"):
        url = get_download_url_for_platform(release)
    assert url and url.endswith("pdf-excel-annotator-macos.zip")


def test_linux_picks_tar_gz():
    release = _make_release("pdf-excel-annotator-linux.tar.gz", "pdf-excel-annotator-macos.zip")
    with patch.object(sys, "platform", "linux"):
        url = get_download_url_for_platform(release)
    assert url and url.endswith(".tar.gz")


def test_no_matching_asset_returns_none():
    release = _make_release("something-else.dmg")
    with patch.object(sys, "platform", "win32"):
        assert get_download_url_for_platform(release) is None


# ── fetch_latest_release (mocked network) ────────────────────────────────────

def _fake_response(payload: dict, status: int = 200):
    mock = MagicMock()
    mock.status = status
    mock.read.return_value = json.dumps(payload).encode()
    mock.__enter__ = lambda s: s
    mock.__exit__ = MagicMock(return_value=False)
    return mock


def test_fetch_latest_release_success():
    payload = {"tag_name": "v1.2.3", "assets": []}
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
        result = fetch_latest_release()
    assert result == payload


def test_fetch_latest_release_network_error():
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        assert fetch_latest_release() is None


def test_fetch_latest_release_non_200():
    with patch("urllib.request.urlopen", return_value=_fake_response({}, status=404)):
        assert fetch_latest_release() is None


# ── check_for_updates (end-to-end mocked) ────────────────────────────────────

def _release_payload(tag: str, *asset_names: str) -> dict:
    return {
        "tag_name": tag,
        "assets": [{"name": n, "browser_download_url": f"https://example.com/{n}"} for n in asset_names],
    }


def test_update_found_on_windows():
    payload = _release_payload("v1.0.1", "pdf-excel-annotator-setup.exe")
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)), \
         patch.object(sys, "platform", "win32"), \
         patch("pdf_excel_annotator.updater.__version__", "1.0.0"):
        result = check_for_updates(current_version="1.0.0")
    assert result is not None
    assert result["version"] == "1.0.1"
    assert "setup.exe" in result["url"]


def test_no_update_when_current(monkeypatch):
    payload = _release_payload("v1.0.0", "pdf-excel-annotator-setup.exe")
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)):
        result = check_for_updates(current_version="1.0.0")
    assert result is None


def test_no_update_when_network_fails():
    with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
        assert check_for_updates(current_version="1.0.0") is None


def test_no_update_when_no_matching_asset():
    payload = _release_payload("v1.0.1")  # no assets
    with patch("urllib.request.urlopen", return_value=_fake_response(payload)), \
         patch.object(sys, "platform", "win32"):
        assert check_for_updates(current_version="1.0.0") is None
