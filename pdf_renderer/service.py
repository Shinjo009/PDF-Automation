"""BioReport → validated HTML → PDF bytes (Playwright/Chromium)."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from modules.bioai_report.pdf_renderer.exceptions import (
    PdfRenderDependencyError,
    PdfRendererError,
    PdfValidationError,
)
from modules.bioai_report.pdf_renderer.html_builder import build_report_html
from modules.bioai_report.pdf_renderer.view_model import PdfViewModel, build_pdf_view_model
from modules.bioai_report.report_engine.models.report import BioReport

logger = logging.getLogger(__name__)


def _as_bioreport(report: BioReport | dict[str, Any]) -> BioReport:
    if isinstance(report, BioReport):
        return report
    return BioReport.model_validate(report)


async def html_to_pdf_bytes(
    html: str,
    *,
    width: str | None = None,
    height: str | None = None,
) -> bytes:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise PdfRenderDependencyError(
            "Playwright is required for PDF generation. "
            "Install with: pip install playwright && playwright install chromium"
        ) from exc

    import tempfile

    # set_content(about:blank) cannot load file:// CSS/assets. Write HTML to disk
    # and navigate so relative/file asset URLs resolve correctly.
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".html",
        encoding="utf-8",
        delete=False,
    ) as tmp:
        tmp.write(html)
        html_path = Path(tmp.name)

    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            try:
                page = await browser.new_page()
                await page.goto(html_path.resolve().as_uri(), wait_until="networkidle")
                # Wait for webfonts so layout matches preview before printing.
                try:
                    await page.evaluate("() => document.fonts && document.fonts.ready")
                except Exception:  # noqa: BLE001
                    pass
                await page.emulate_media(media="print")
                pdf_kwargs: dict[str, Any] = {
                    "print_background": True,
                    "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
                    "scale": 1,
                }
                if width and height:
                    pdf_kwargs["width"] = width
                    pdf_kwargs["height"] = height
                    pdf_kwargs["prefer_css_page_size"] = True
                else:
                    pdf_kwargs["format"] = "A4"
                    pdf_kwargs["prefer_css_page_size"] = False
                pdf = await page.pdf(**pdf_kwargs)
                return pdf
            finally:
                await browser.close()
    finally:
        html_path.unlink(missing_ok=True)


class PdfRenderService:
    """Assemble HTML from BioReport and render PDF bytes."""

    def build_view_model(self, report: BioReport | dict[str, Any]) -> PdfViewModel:
        return build_pdf_view_model(_as_bioreport(report))

    def build_html(self, report: BioReport | dict[str, Any]) -> str:
        vm = self.build_view_model(report)
        return build_report_html(vm)

    async def render_pdf_async(self, report: BioReport | dict[str, Any]) -> bytes:
        try:
            html = self.build_html(report)
            return await html_to_pdf_bytes(html)
        except PdfValidationError:
            raise
        except PdfRenderDependencyError:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.exception("PDF render failed")
            raise PdfRendererError(str(exc)) from exc

    def render_pdf(self, report: BioReport | dict[str, Any]) -> bytes:
        return asyncio.run(self.render_pdf_async(report))

    def write_pdf(
        self,
        report: BioReport | dict[str, Any],
        output_path: str | Path,
    ) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(self.render_pdf(report))
        return path


def render_bioreport_pdf(report: BioReport | dict[str, Any]) -> bytes:
    """Convenience sync helper used by API / offline runners."""
    return PdfRenderService().render_pdf(report)
