"""Bio-AI Report Automation — BioReport JSON → PDF → permanent link."""

from __future__ import annotations

from typing import Any

__all__ = ["BioReport", "PdfRenderService", "render_bioreport_pdf"]


def __getattr__(name: str) -> Any:
    if name in {"PdfRenderService", "render_bioreport_pdf"}:
        from modules.bioai_report.pdf_renderer.service import PdfRenderService, render_bioreport_pdf

        return PdfRenderService if name == "PdfRenderService" else render_bioreport_pdf
    if name == "BioReport":
        from modules.bioai_report.report_engine.models.report import BioReport

        return BioReport
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
