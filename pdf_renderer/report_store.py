"""Persist BioReport JSON and PDF under a secret public slug.

Public URLs use a random slug (not the MetSights record_id):
  https://bio-ai-reports.example/r/{slug}

Files on disk:
  storage/bioreports/{slug}.json
  storage/pdfs/{slug}.pdf

Internal record_id stays inside the JSON for your own tracking.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORE_DIR = _REPO_ROOT / "storage" / "bioreports"
DEFAULT_PDF_DIR = _REPO_ROOT / "storage" / "pdfs"
DEFAULT_ARCHIVE_DIR = _REPO_ROOT / "storage" / "archive"

# URL-safe chars only (matches /r/{slug} route)
_SAFE_ID = re.compile(r"[^A-Za-z0-9._-]+")
_SLUG_BYTES = 16  # token_urlsafe(16) ≈ 22 chars — hard to guess


def store_dir() -> Path:
    path = Path(os.environ.get("BIOAI_REPORT_STORE", str(DEFAULT_STORE_DIR)))
    path.mkdir(parents=True, exist_ok=True)
    return path


def pdf_dir() -> Path:
    override = os.environ.get("BIOAI_PDF_STORE")
    if override:
        path = Path(override)
    else:
        path = DEFAULT_PDF_DIR
    path.mkdir(parents=True, exist_ok=True)
    return path


def archive_dir() -> Path:
    path = Path(os.environ.get("BIOAI_ARCHIVE_DIR", str(DEFAULT_ARCHIVE_DIR)))
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_id(raw: str) -> str:
    cleaned = _SAFE_ID.sub("_", (raw or "").strip())
    return cleaned[:120] or uuid.uuid4().hex


def new_public_slug() -> str:
    """Cryptographically random slug for permanent public links."""
    for _ in range(8):
        slug = secrets.token_urlsafe(_SLUG_BYTES)
        slug = sanitize_id(slug)
        if slug and not exists(slug) and not pdf_exists(slug):
            return slug
    return sanitize_id(secrets.token_urlsafe(_SLUG_BYTES + 8))


def extract_internal_record_id(payload: dict[str, Any]) -> str | None:
    """MetSights / patient record id from JSON (not used in the public URL)."""
    patient = payload.get("patient") or {}
    meta = payload.get("report_metadata") or {}
    for candidate in (
        patient.get("record_id"),
        meta.get("record_id"),
        patient.get("profile_id"),
    ):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return None


def json_path(slug: str) -> Path:
    return store_dir() / f"{sanitize_id(slug)}.json"


def pdf_path(slug: str) -> Path:
    return pdf_dir() / f"{sanitize_id(slug)}.pdf"


def save_report_json(payload: dict[str, Any], *, slug: str | None = None) -> str:
    """Save JSON under a secret slug. Generates a new slug when not provided."""
    public_slug = sanitize_id(slug) if slug else new_public_slug()
    path = json_path(public_slug)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return public_slug


def load_report_json(slug: str) -> dict[str, Any] | None:
    path = json_path(slug)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_report_pdf(slug: str, pdf_bytes: bytes) -> Path:
    path = pdf_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(pdf_bytes)
    return path


def load_report_pdf(slug: str) -> bytes | None:
    path = pdf_path(slug)
    if not path.is_file():
        return None
    return path.read_bytes()


def pdf_exists(slug: str) -> bool:
    return pdf_path(slug).is_file()


def exists(slug: str) -> bool:
    return json_path(slug).is_file()


def report_exists(slug: str) -> bool:
    return exists(slug) or pdf_exists(slug)


def archive_report_if_exists(slug: str) -> Path | None:
    """Move existing JSON/PDF for slug into storage/archive/{slug}/{timestamp}/."""
    public_slug = sanitize_id(slug)
    json_src = json_path(public_slug)
    pdf_src = pdf_path(public_slug)
    if not json_src.is_file() and not pdf_src.is_file():
        return None

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest_dir = archive_dir() / public_slug / timestamp
    dest_dir.mkdir(parents=True, exist_ok=True)

    if json_src.is_file():
        json_src.replace(dest_dir / "report.json")
    if pdf_src.is_file():
        pdf_src.replace(dest_dir / "report.pdf")
    return dest_dir


# Back-compat aliases (older call sites used record_id naming)
sanitize_record_id = sanitize_id
resolve_record_id = extract_internal_record_id
