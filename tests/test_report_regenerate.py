"""Tests for slug-based report regeneration and archive behavior."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from modules.bioai_report.pdf_renderer.report_store import (
    archive_report_if_exists,
    exists,
    load_report_json,
    load_report_pdf,
    pdf_exists,
    report_exists,
    save_report_json,
    save_report_pdf,
)

ROOT = Path(__file__).resolve().parents[1]
USER1 = ROOT / "test_engine" / "output_report_user1.json"
FAKE_PDF = b"%PDF-1.4 test"
RESPONSE_KEYS = {"slug", "url", "record_id", "patient", "variant", "note"}


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    store = tmp_path / "bioreports"
    pdfs = tmp_path / "pdfs"
    archive = tmp_path / "archive"
    monkeypatch.setenv("BIOAI_REPORT_STORE", str(store))
    monkeypatch.setenv("BIOAI_PDF_STORE", str(pdfs))
    monkeypatch.setenv("BIOAI_ARCHIVE_DIR", str(archive))
    return {"store": store, "pdfs": pdfs, "archive": archive}


@pytest.fixture
def user1_payload() -> dict:
    return json.loads(USER1.read_text(encoding="utf-8"))


def test_archive_report_if_exists_noop(isolated_store):
    assert archive_report_if_exists("missing-slug") is None


def test_archive_report_if_exists_moves_json_and_pdf(isolated_store, user1_payload):
    slug = "A2Gp3Y2beG8i-4EjRaItnA"
    save_report_json(user1_payload, slug=slug)
    save_report_pdf(slug, FAKE_PDF)
    assert report_exists(slug)

    archive_path = archive_report_if_exists(slug)
    assert archive_path is not None
    assert (archive_path / "report.json").is_file()
    assert (archive_path / "report.pdf").read_bytes() == FAKE_PDF
    assert not exists(slug)
    assert not pdf_exists(slug)


def test_regenerate_overwrites_at_same_slug(isolated_store, user1_payload):
    slug = "A2Gp3Y2beG8i-4EjRaItnA"
    save_report_json(user1_payload, slug=slug)
    save_report_pdf(slug, b"old-pdf")

    updated = deepcopy(user1_payload)
    updated["patient"]["name"] = "Regenerated Patient"
    save_report_json(updated, slug=slug)
    save_report_pdf(slug, FAKE_PDF)

    stored = load_report_json(slug)
    assert stored is not None
    assert stored["patient"]["name"] == "Regenerated Patient"
    assert load_report_pdf(slug) == FAKE_PDF
    assert "slug" not in stored


def test_regenerate_archives_previous_version(isolated_store, user1_payload):
    slug = "test-archive-slug"
    save_report_json(user1_payload, slug=slug)
    save_report_pdf(slug, b"old-pdf")

    updated = deepcopy(user1_payload)
    updated["patient"]["name"] = "After Archive"
    archive_report_if_exists(slug)
    save_report_json(updated, slug=slug)
    save_report_pdf(slug, FAKE_PDF)

    archive_root = isolated_store["archive"] / slug
    assert archive_root.is_dir()
    archived_dirs = list(archive_root.iterdir())
    assert len(archived_dirs) == 1
    assert (archived_dirs[0] / "report.json").is_file()
    assert (archived_dirs[0] / "report.pdf").read_bytes() == b"old-pdf"
    assert load_report_json(slug)["patient"]["name"] == "After Archive"


def test_regenerate_response_keys():
    assert RESPONSE_KEYS == {
        "slug",
        "url",
        "record_id",
        "patient",
        "variant",
        "note",
    }


def test_slug_stripped_from_stored_json(isolated_store, user1_payload):
    slug = "strip-slug-test"
    payload = {"slug": slug, **user1_payload}
    payload.pop("slug")
    save_report_json(payload, slug=slug)
    stored = load_report_json(slug)
    assert stored is not None
    assert "slug" not in stored
