#!/usr/bin/env python3
"""Local page-by-page HTML preview (like frontend localhost).

Usage (from repo root):
    PYTHONPATH=. python -m modules.bioai_report.pdf_renderer.preview_server
    # or:
    PYTHONPATH=. python pdf_renderer/preview_server.py

Open:
    http://127.0.0.1:5174/preview?page=1&fixture=user1
"""

from __future__ import annotations

import argparse
import json
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from modules.bioai_report.pdf_renderer.html_builder import build_report_html  # noqa: E402
from modules.bioai_report.pdf_renderer.view_model import build_pdf_view_model  # noqa: E402
from modules.bioai_report.report_engine.models.report import BioReport  # noqa: E402

FIXTURES = {
    "user1": _REPO_ROOT / "test_engine" / "output_report_user1.json",
    "sample": _REPO_ROOT / "report_engine" / "sample_output.json",
    "harsh": _REPO_ROOT / "test_engine" / "preview_harsh.json",
    "glance_mixed": _REPO_ROOT / "test_engine" / "preview_glance_mixed.json",
}

_SAMPLE_ALLERGY = {
    "total_ige": 1481.9,
    "ige_unit": "IU/ml",
    "ige_ref_low": 1.5,
    "ige_ref_high": 158,
    "recommendation": (
        "Your IgE level is 14x above normal limits, indicating severe "
        "systemic allergic sensitivity. Normal levels- (1.5-158 IU/ml)"
    ),
    "total_allergens_tested": "100+",
    "sensitive_count": 2,
    "normal_count": "98+",
    "sensitivities": [
        {
            "name": "Tyrophagus Putrescentiae",
            "category": "Dust Mites",
            "value": 0.78,
            "ref_range": "<0.35",
            "risk": "Class 2 (Low)",
        },
        {
            "name": "Tobacco Dust",
            "category": "Dust Mites",
            "value": 0.52,
            "ref_range": "<0.35",
            "risk": "Class 1 (Very Low)",
        },
    ],
}


def _load_report(fixture: str, gender: str | None) -> BioReport:
    path = FIXTURES.get(
        fixture if fixture not in {"allergy", "cancer", "allergy_cancer"} else "user1",
        FIXTURES["user1"],
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    if fixture in {"allergy", "allergy_cancer"}:
        data["allergy"] = dict(_SAMPLE_ALLERGY)
    if fixture in {"cancer", "allergy_cancer"}:
        data["cancer"] = {}
        if not gender:
            gender = "female"
    if gender:
        data["patient"]["gender"] = gender
        data["patient"]["sex"] = gender
        if isinstance(data.get("executive_summary"), dict) and isinstance(
            data["executive_summary"].get("patient"), dict
        ):
            data["executive_summary"]["patient"]["gender"] = gender
            data["executive_summary"]["patient"]["sex"] = gender
    return BioReport.model_validate(data)


class PreviewHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(_REPO_ROOT / "pdf_renderer"), **kwargs)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/preview"}:
            return self._serve_preview(parsed)
        if parsed.path.startswith("/static/"):
            # Map /static/... → pdf_renderer/static/...
            self.path = parsed.path  # served from pdf_renderer root
            return SimpleHTTPRequestHandler.do_GET(self)
        self.send_error(404, "Not found")

    def _serve_preview(self, parsed) -> None:
        qs = parse_qs(parsed.query)
        page_raw = (qs.get("page") or ["1"])[0]
        page = None if page_raw in {"all", "*", ""} else page_raw
        fixture = (qs.get("fixture") or ["user1"])[0]
        gender = (qs.get("gender") or [None])[0]
        try:
            report = _load_report(fixture, gender)
            vm = build_pdf_view_model(report)
            body_html = build_report_html(vm, for_http=True, page=page)
        except Exception as exc:  # noqa: BLE001
            self.send_response(500)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"Preview error: {exc}".encode("utf-8"))
            return

        toolbar = f"""
        <div class="preview-toolbar">
          <strong>Bio-AI PDF Preview</strong>
          <span>page={page or "all"}</span>
          <span>fixture={fixture}</span>
          <span>variant={vm.variant}</span>
          <a href="/preview?page=1&fixture={fixture}">Cover (1)</a>
          <a href="/preview?page=2&fixture={fixture}">Welcome (2)</a>
          <a href="/preview?page=3&fixture={fixture}">TOC (3)</a>
          <a href="/preview?page=4&fixture={fixture}">Diseases (4)</a>
          <a href="/preview?page=5&fixture={fixture}">Health Summary (5)</a>
          <a href="/preview?page=6&fixture={fixture}">At A Glance (6)</a>
          <a href="/preview?page=7&fixture={fixture}">Risk Summary (7)</a>
          <a href="/preview?page=8&fixture={fixture}">Disease Divider (8)</a>
          <a href="/preview?page=9&fixture={fixture}">Disease Detail (9)</a>
          <a href="/preview?page=10&fixture={fixture}">Dyslipidemia (10)</a>
          <a href="/preview?page=11&fixture={fixture}">Cardiac Health (11)</a>
          <a href="/preview?page=12&fixture={fixture}">Oxidative Stress (12)</a>
          <a href="/preview?page=13&fixture={fixture}">NAFLD (13)</a>
          <a href="/preview?page=14&fixture={fixture}">Hypertension (14)</a>
          <a href="/preview?page=15&fixture={fixture}">Obesity (15)</a>
          <a href="/preview?page=16&fixture={fixture}">Thyroid (16)</a>
          <a href="/preview?page=17&fixture={fixture}">Type 2 Diabetes (17)</a>
          <a href="/preview?page=18&fixture={fixture}">Back Cover (18)</a>
          <a href="/preview?page=AllergyCancerDivider&fixture=allergy">Allergy Divider</a>
          <a href="/preview?page=AllergyOverview&fixture=allergy">Allergy Overview</a>
          <a href="/preview?page=AllergyBreakdown&fixture=allergy">Allergy Breakdown</a>
          <a href="/preview?page=747:5471&fixture=allergy">Allergy Breakdown 2</a>
          <a href="/preview?page=AllergyInsights&fixture=allergy">Allergy Insights</a>
          <a href="/preview?page=CancerScreeningDivider&fixture=cancer">Cancer Divider</a>
          <a href="/preview?page=CancerScreening&fixture=cancer&gender=female">Cancer Screening (F)</a>
          <a href="/preview?page=CancerScreening&fixture=cancer&gender=male">Cancer Screening (M)</a>
          <a href="/preview?page=747:6246&fixture=cancer&gender=female">Breast Screening (F)</a>
          <a href="/preview?page=747:6035&fixture=cancer&gender=female">Ovarian Screening (F)</a>
          <a href="/preview?page=747:6162&fixture=cancer&gender=female">Pancreatic Screening (F)</a>
          <a href="/preview?page=1&fixture={fixture}&gender=male">Male</a>
          <a href="/preview?page=1&fixture={fixture}&gender=female">Female</a>
          <a href="/preview?page=all&fixture={fixture}">All pages</a>
        </div>
        <div class="preview-stage">
        """
        # Inject toolbar after <body ...>
        html = body_html.replace(
            '<body class="preview-mode">',
            '<body class="preview-mode">' + toolbar,
            1,
        ).replace("</body>", "</div></body>", 1)

        payload = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write("%s - %s\n" % (self.address_string(), fmt % args))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bio-AI PDF local preview server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5174)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), PreviewHandler)
    print(f"Preview server: http://{args.host}:{args.port}/preview?page=1&fixture=user1")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
