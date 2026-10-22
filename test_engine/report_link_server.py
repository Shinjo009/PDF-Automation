#!/usr/bin/env python3
"""Permanent report links: store JSON + PDF once, serve via secret slug URL.

Public URL shape:
  https://bio-ai-reports.supershyft.com/r/{secret_slug}

The MetSights record_id stays inside the JSON / API response for tracking;
it is never used as the public path.

Usage (from repo root):
    source .venv/bin/activate
    unset PLAYWRIGHT_BROWSERS_PATH
    export BIOAI_PUBLIC_BASE_URL=http://127.0.0.1:8790
    # prod: export BIOAI_PUBLIC_BASE_URL=https://bio-ai-reports.supershyft.com
    PYTHONPATH=. python test_engine/report_link_server.py

API:
    POST /api/reports              JSON body (payload) → { slug, url, record_id, patient, variant }
    POST /api/reports/regenerate   JSON body with slug + BioReport → same response, overwrites slug
    POST /api/cards                greeting-card JSON → { slug, url, card_type, receiver, sender }
    POST /api/cards/regenerate     slug + greeting-card JSON → same url, overwrites slug
    GET  /r/{slug}             application/pdf (inline)
    GET  /r/{slug}?dl=1        force download
    GET  /                     status page

CORS:
    Allowed origin (default): https://api.supershyft.com
    Override with BIOAI_CORS_ORIGINS (comma-separated).
    JSON is always taken from the POST body — never fetched from storage for register.
"""

from __future__ import annotations

import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

os.environ.pop("PLAYWRIGHT_BROWSERS_PATH", None)

from modules.bioai_report.pdf_renderer.exceptions import (  # noqa: E402
    PdfRenderDependencyError,
    PdfRendererError,
    PdfValidationError,
)
from modules.bioai_report.pdf_renderer.report_store import (  # noqa: E402
    archive_report_if_exists,
    extract_internal_record_id,
    load_report_json,
    load_report_pdf,
    pdf_dir,
    pdf_exists,
    sanitize_id,
    save_report_json,
    save_report_pdf,
    store_dir,
)
from modules.bioai_report.pdf_renderer.greeting_cards import (  # noqa: E402
    is_card_payload,
    render_card_pdf,
)
from modules.bioai_report.pdf_renderer.service import PdfRenderService  # noqa: E402
from modules.bioai_report.pdf_renderer.view_model import resolve_gender_variant  # noqa: E402
from modules.bioai_report.report_engine.models.report import BioReport  # noqa: E402

HOST = os.environ.get("BIOAI_LINK_HOST", "127.0.0.1")
PORT = int(os.environ.get("BIOAI_LINK_PORT", "8790"))
PUBLIC_BASE = os.environ.get("BIOAI_PUBLIC_BASE_URL", f"http://{HOST}:{PORT}").rstrip("/")

# Browser Origin never includes a trailing slash.
_DEFAULT_CORS_ORIGINS = ("https://api.supershyft.com",)
_CORS_ORIGINS = tuple(
    o.strip().rstrip("/")
    for o in os.environ.get("BIOAI_CORS_ORIGINS", ",".join(_DEFAULT_CORS_ORIGINS)).split(",")
    if o.strip()
)

_SLUG_RE = re.compile(r"^/r/([A-Za-z0-9._-]+)/?$")
_CORS_POST_PATHS = frozenset({
    "/api/reports",
    "/api/reports/regenerate",
    "/api/cards",
    "/api/cards/regenerate",
})
_CARD_POST_PATHS = frozenset({"/api/cards", "/api/cards/regenerate"})


def _cors_origin(request_origin: str | None) -> str | None:
    if not request_origin:
        return None
    origin = request_origin.strip().rstrip("/")
    if origin in _CORS_ORIGINS:
        return origin
    return None


def _public_url(slug: str) -> str:
    return f"{PUBLIC_BASE}/r/{quote(slug)}"


def _safe_filename(name: str, *, prefix: str = "BIO-AI-report") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "report").strip()) or "report"
    return f"{prefix}-{cleaned}.pdf"


def _patient_bits(payload: dict) -> tuple[str, str]:
    patient = payload.get("patient") or {}
    name = (patient.get("name") or "report").strip() or "report"
    variant = resolve_gender_variant(patient.get("gender"), patient.get("sex"))
    return name, variant


def _register_report(payload: dict, *, slug: str | None = None) -> dict:
    """Validate BioReport JSON, render PDF, persist, and return API response body."""
    report = BioReport.model_validate(payload)
    internal_id = extract_internal_record_id(payload)
    public_slug = save_report_json(payload, slug=slug)
    pdf_bytes = PdfRenderService().render_pdf(report)
    save_report_pdf(public_slug, pdf_bytes)
    name, variant = _patient_bits(payload)
    return {
        "slug": public_slug,
        "url": _public_url(public_slug),
        "record_id": internal_id,
        "patient": name,
        "variant": variant,
        "note": (
            "Permanent secret link. PDF stored once; "
            "public path uses slug only (not record_id)."
        ),
    }


def _register_card(payload: dict, *, slug: str | None = None) -> dict:
    """Validate greeting-card JSON, render PDF, persist, return API response."""
    card, pdf_bytes = render_card_pdf(payload)
    public_slug = save_report_json(card, slug=slug)
    save_report_pdf(public_slug, pdf_bytes)
    return {
        "slug": public_slug,
        "url": _public_url(public_slug),
        "card_type": card["card_type"],
        "receiver": card["receiver_name"],
        "sender": card["sender_name"],
        "occasion": card["occasion"],
        "note": (
            "Permanent secret link. Greeting-card PDF stored once; "
            "public path uses slug only."
        ),
    }


class ReportLinkHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _set_cors_headers(self) -> None:
        allowed = _cors_origin(self.headers.get("Origin"))
        if not allowed:
            return
        self.send_header("Access-Control-Allow-Origin", allowed)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, Accept",
        )
        self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self) -> None:  # noqa: N802
        """CORS preflight for POST /api/reports from https://api.supershyft.com."""
        if self.path.rstrip("/") not in _CORS_POST_PATHS:
            self.send_error(404, "Not found")
            return
        if not _cors_origin(self.headers.get("Origin")):
            self.send_error(403, "Origin not allowed")
            return
        self.send_response(204)
        self._set_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/health"}:
            return self._health()
        match = _SLUG_RE.match(parsed.path)
        if match:
            force_dl = (parse_qs(parsed.query).get("dl") or ["0"])[0] in {"1", "true", "yes"}
            return self._serve_pdf(match.group(1), force_download=force_dl)
        self.send_error(404, "Not found")

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.rstrip("/")
        if path not in _CORS_POST_PATHS:
            self.send_error(404, "Not found")
            return
        # Reject disallowed browser origins; server-to-server (no Origin) is allowed.
        origin = self.headers.get("Origin")
        if origin and not _cors_origin(origin):
            return self._text(403, "Origin not allowed")

        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        try:
            # JSON always comes from this request payload — not from stored files.
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("JSON body must be an object")

            if path in _CARD_POST_PATHS:
                if path == "/api/cards/regenerate":
                    raw_slug = payload.pop("slug", None)
                    if not isinstance(raw_slug, str) or not raw_slug.strip():
                        raise ValueError("slug is required for regenerate")
                    slug = sanitize_id(raw_slug)
                    if not slug:
                        raise ValueError("slug is required for regenerate")
                    archive_report_if_exists(slug)
                    body = _register_card(payload, slug=slug)
                else:
                    body = _register_card(payload)
            elif path == "/api/reports/regenerate":
                raw_slug = payload.pop("slug", None)
                if not isinstance(raw_slug, str) or not raw_slug.strip():
                    raise ValueError("slug is required for regenerate")
                slug = sanitize_id(raw_slug)
                if not slug:
                    raise ValueError("slug is required for regenerate")
                archive_report_if_exists(slug)
                body = _register_report(payload, slug=slug)
            else:
                body = _register_report(payload)

            return self._json(200, body)
        except (json.JSONDecodeError, ValueError, PdfValidationError) as exc:
            return self._text(400, str(exc))
        except (PdfRenderDependencyError, PdfRendererError) as exc:
            return self._text(503, f"PDF render failed: {exc}")
        except Exception as exc:  # noqa: BLE001
            return self._text(500, f"Failed to register report: {exc}")

    def _health(self) -> None:
        html = f"""<!doctype html>
<html><head><meta charset="utf-8"/><title>Bio-AI report links</title>
<style>
  body{{font-family:system-ui,sans-serif;max-width:640px;margin:48px auto;padding:0 16px;color:#102826}}
  code{{background:#f2f5f4;padding:2px 6px;border-radius:6px}}
  li{{margin:8px 0}}
</style></head><body>
<h1>Bio-AI + greeting-card links</h1>
<p>Register once: we store the PDF and return a permanent secret link.</p>
<ul>
  <li><code>POST {PUBLIC_BASE}/api/reports</code> — BioReport JSON payload → <code>url</code></li>
  <li><code>POST {PUBLIC_BASE}/api/reports/regenerate</code> — slug + BioReport JSON → same <code>url</code></li>
  <li><code>POST {PUBLIC_BASE}/api/cards</code> — greeting-card JSON → <code>url</code></li>
  <li><code>POST {PUBLIC_BASE}/api/cards/regenerate</code> — slug + greeting-card JSON → same <code>url</code></li>
  <li>CORS origin: <code>https://api.supershyft.com</code></li>
  <li><code>GET {PUBLIC_BASE}/r/&lt;slug&gt;</code> — view stored PDF</li>
  <li><code>GET …/r/&lt;slug&gt;?dl=1</code> — force download</li>
</ul>
</body></html>"""
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_pdf(self, slug: str, *, force_download: bool) -> None:
        pdf_bytes = load_report_pdf(slug)
        if pdf_bytes is None:
            if not pdf_exists(slug) and not load_report_json(slug):
                return self._text(404, "Unknown report")
            return self._text(404, "PDF missing for report")

        payload = load_report_json(slug) or {}
        if is_card_payload(payload):
            filename = _safe_filename(
                payload.get("receiver_name") or "card",
                prefix=f"{payload.get('card_type') or 'greeting'}-card",
            )
        else:
            name, _variant = _patient_bits(payload) if payload else ("report", "male")
            filename = _safe_filename(name)

        disposition = "attachment" if force_download else "inline"
        self.send_response(200)
        self.send_header("Content-Type", "application/pdf")
        self.send_header(
            "Content-Disposition",
            f'{disposition}; filename="{filename}"; filename*=UTF-8\'\'{quote(filename)}',
        )
        self.send_header("Content-Length", str(len(pdf_bytes)))
        self.send_header("Cache-Control", "private, max-age=86400")
        self.end_headers()
        self.wfile.write(pdf_bytes)

    def _json(self, code: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._set_cors_headers()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _text(self, code: int, message: str) -> None:
        data = message.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self._set_cors_headers()
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    print(f"JSON store:  {store_dir()}")
    print(f"PDF store:   {pdf_dir()}")
    print(f"Public base: {PUBLIC_BASE}")
    print(f"CORS allow:  {', '.join(_CORS_ORIGINS) or '(none)'}")
    print(f"Listening:   http://{HOST}:{PORT}/")
    server = ThreadingHTTPServer((HOST, PORT), ReportLinkHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
