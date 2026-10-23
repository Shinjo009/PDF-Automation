"""Render BioReport PDF view-model into print-ready HTML."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from modules.bioai_report.pdf_renderer import config as pdf_config
from modules.bioai_report.pdf_renderer.assets import page_asset_urls
from modules.bioai_report.pdf_renderer.graphs.svg import (
    disease_score_gauge_svg,
    percentile_marker_pct,
    score_ring_svg,
    trend_line_chart_svg,
)
from modules.bioai_report.pdf_renderer.view_model import PdfViewModel, risk_color


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(pdf_config.TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.globals["score_ring_svg"] = score_ring_svg
    env.globals["disease_score_gauge_svg"] = disease_score_gauge_svg
    env.globals["percentile_marker_pct"] = percentile_marker_pct
    return env


def _css_href(name: str, *, for_http: bool) -> str:
    if for_http:
        return f"/static/css/{name}"
    return (Path(pdf_config.STATIC_DIR) / "css" / name).resolve().as_uri()


_FIGMA_SCORE_COLORS = {
    "Healthy": "#6dde80",
    "Increased Risk": "#f8d232",
    "High Risk": "#eaa546",
    "Very High Risk": "#c6203b",
}

# Figma At A Glance card slots (node 379:120319) — page coords. Male: 5 left + 4 right.
_GLANCE_SLOTS_MALE: tuple[tuple[str, str, int, bool], ...] = (
    ("dyslipidemia", "left", 192, False),
    ("cardiac_health", "left", 292, False),
    ("hypertension", "left", 383, False),
    ("nafld", "left", 477, False),
    ("metabolic_syndrome", "left", 596, True),
    ("oxidative_stress", "right", 192, False),
    ("thyroid_health", "right", 293, False),
    ("obesity", "right", 390, False),
    ("type2_diabetes", "right", 526, False),
)

# Female At A Glance (Figma 451:2): 5 left + 5 right, includes metabolic_syndrome + PCOS/PCOD.
_GLANCE_SLOTS_FEMALE: tuple[tuple[str, str, int, bool], ...] = (
    ("dyslipidemia", "left", 192, False),
    ("cardiac_health", "left", 292, False),
    ("hypertension", "left", 382, False),
    ("nafld", "left", 476, False),
    ("metabolic_syndrome", "left", 596, True),
    ("oxidative_stress", "right", 192, False),
    ("thyroid_health", "right", 293, False),
    ("obesity", "right", 390, False),
    ("type2_diabetes", "right", 525, False),
    ("pcos_pcod", "right", 628, False),
)

# Exact Figma connector vectors (male 379:120319) as absolute page SVG path `d` + ring centers.
# Local vector paths were converted with each node's pageX/pageY.
_GLANCE_CONNECTORS_MALE: dict[str, dict[str, object]] = {
    # 379:121321 → ring 379:121327
    "dyslipidemia": {
        "d": "M 188 219 L 213.783 219 L 291 306",
        "dot": (295.65, 311.65),
    },
    # 379:121320 → ring 379:121324
    "cardiac_health": {
        "d": "M 188.491 321.927 L 219.596 321.927 L 312.753 384.595",
        "dot": (312.75, 384.60),
    },
    # 379:121336 → ring 379:121338
    "hypertension": {
        "d": "M 196.957 410.819 L 226.863 410.819 L 239 398.867 L 292.432 398.867",
        "dot": (295.65, 398.65),
    },
    # 379:121322 → ring 379:121330
    "nafld": {
        "d": "M 188.012 508.492 L 219.107 508.492 L 292.263 448.824",
        "dot": (295.98, 446.77),
    },
    # 379:121531 → ring 379:121532
    "metabolic_syndrome": {
        "d": "M 198 636 L 223.652 636 L 284 491",
        "dot": (283.65, 493.65),
    },
    # 379:121345 → ring 379:121349
    "oxidative_stress": {
        "d": "M 410 224 L 319.586 224 L 306 292",
        "dot": (303.65, 292.65),
    },
    # 379:121344 → ring 379:121346
    "thyroid_health": {
        "d": "M 409.927 322.527 L 315.072 322.527 L 300.818 343.38",
        "dot": (297.87, 348.70),
    },
    # 379:121337 → ring 379:121341
    "obesity": {
        "d": "M 454.476 419.93 L 294.131 419.93",
        "dot": (286.87, 419.93),
    },
    # 379:121323 → ring 379:121333
    "type2_diabetes": {
        "d": "M 420.372 554.757 L 376.263 554.757 L 316.111 459.045",
        "dot": (315.15, 457.23),
    },
}

# Female: same connector geometry as male for shared diseases; PCOS-only path added.
_GLANCE_CONNECTORS_FEMALE: dict[str, dict[str, object]] = {
    **_GLANCE_CONNECTORS_MALE,
    "pcos_pcod": {
        "d": "M 416.46 657.19 L 372.46 657.19 L 312.46 509.19",
        "dot": (312.46, 509.19),
    },
}

_GLANCE_TITLES: dict[str, str] = {
    "dyslipidemia": "Dyslipidemia",
    "cardiac_health": "Cardiac Health",
    "hypertension": "Hypertension",
    "nafld": "NAFLD",
    "metabolic_syndrome": "Metabolic\nSyndrome",
    "oxidative_stress": "Oxidative Stress",
    "thyroid_health": "Thyroid Health",
    "obesity": "Obesity",
    "type2_diabetes": "Type 2 Diabetes",
    "pcos_pcod": "PCOS / PCOD",
}

_RISK_SUMMARY_TITLES: dict[str, str] = {
    "dyslipidemia": "Dyslipidemia",
    "cardiac_health": "Cardiac Health",
    "hypertension": "Hypertension",
    "nafld": "NAFLD",
    "metabolic_syndrome": "Metabolic Syndrome",
    "oxidative_stress": "Oxidative Stress",
    "thyroid_health": "Thyroid Health",
    "obesity": "Obesity",
    "type2_diabetes": "Type 2 Diabetes",
    "pcos_pcod": "PCOS / PCOD",
}


def _parse_number(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace("years", "").replace("/100", "").strip()
    if not text or text == "—":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _format_intish(value: float | None) -> str:
    if value is None:
        return "—"
    if float(value).is_integer():
        return str(int(value))
    return f"{value:g}"


def _score_band_label(score: float | None) -> str:
    if score is None:
        return "Healthy"
    number = int(round(score))
    for name, lo, hi, _color in pdf_config.RISK_BANDS:
        if lo <= number <= hi:
            return name
    return "Healthy"


def _health_summary_context(vm: PdfViewModel, assets: dict[str, str]) -> dict[str, object]:
    score = _parse_number(vm.metabolic_score)
    age = _parse_number(vm.metabolic_age)
    chrono = _parse_number(vm.patient_age)
    band = _score_band_label(score)
    score_color = _FIGMA_SCORE_COLORS.get(band, "#f8d232")
    if age is not None and chrono is not None and age <= chrono:
        age_color = _FIGMA_SCORE_COLORS["Healthy"]
    elif age is not None and chrono is not None and age <= chrono + 5:
        age_color = _FIGMA_SCORE_COLORS["Increased Risk"]
    else:
        age_color = score_color
    # Thumbs up when metabolic age is equal to or lower than chronological age.
    thumb_up = age is not None and chrono is not None and age <= chrono
    return {
        "score_display": _format_intish(score),
        "age_display": _format_intish(age),
        "score_color": score_color,
        "age_color": age_color,
        "band": band,
        "thumb_up": thumb_up,
        "thumb_src": assets["hs_thumbs_up"] if thumb_up else assets["hs_thumbs_down"],
    }


def _normalize_risk_label(risk: str | None, score: int | None) -> str:
    text = (risk or "").strip()
    lowered = text.lower()
    aliases = {
        "healthy": "Healthy",
        "increased": "Increased Risk",
        "increased risk": "Increased Risk",
        "high": "High Risk",
        "high risk": "High Risk",
        "very high": "Very High Risk",
        "very high risk": "Very High Risk",
    }
    if lowered in aliases:
        return aliases[lowered]
    if score is not None:
        return _score_band_label(float(score))
    return text or "Healthy"


def _glance_slots_for_variant(variant: str) -> tuple[tuple[str, str, int, bool], ...]:
    if variant == "female":
        return _GLANCE_SLOTS_FEMALE
    return _GLANCE_SLOTS_MALE


def _glance_connectors_for_variant(variant: str) -> dict[str, dict[str, object]]:
    if variant == "female":
        return _GLANCE_CONNECTORS_FEMALE
    return _GLANCE_CONNECTORS_MALE


def _at_a_glance_context(vm: PdfViewModel) -> dict[str, object]:
    by_id = {d.disease_id: d for d in vm.glance_diseases}
    connectors = _glance_connectors_for_variant(vm.variant)
    cards: list[dict[str, object]] = []
    for disease_id, side, top, tall in _glance_slots_for_variant(vm.variant):
        disease = by_id.get(disease_id)
        if disease is None:
            continue
        risk = _normalize_risk_label(disease.risk, disease.score)
        accent = _FIGMA_SCORE_COLORS.get(risk, disease.risk_color or "#f8d232")
        connector = connectors.get(disease_id, {})
        dot = connector.get("dot")
        cards.append(
            {
                "disease_id": disease_id,
                "title": _GLANCE_TITLES.get(disease_id, disease.title),
                "side": side,
                "top": top,
                "tall": tall,
                "score": disease.score,
                "score_display": f"{disease.score}/100",
                "risk": risk,
                "accent": accent,
                "connector_d": connector.get("d") or "",
                "dot_x": round(float(dot[0]), 2) if dot else None,  # type: ignore[index]
                "dot_y": round(float(dot[1]), 2) if dot else None,  # type: ignore[index]
            }
        )
    return {"cards": cards}


def _band_key(risk: str) -> str:
    mapping = {
        "Healthy": "healthy",
        "Increased Risk": "increased",
        "High Risk": "high",
        "Very High Risk": "very_high",
    }
    return mapping.get(risk, "increased")


def _risk_summary_line(risk: str, percentile_label: str) -> str:
    # Figma: "High risk (61st percentile)"
    text = risk.strip()
    if text.lower().endswith(" risk"):
        head = text[: -len(" risk")].rstrip()
        label = f"{head} risk" if head else text
    else:
        label = text
    if label:
        label = label[0].upper() + label[1:]
    if percentile_label and percentile_label != "—":
        return f"{label} ({percentile_label} percentile)"
    return label


def _risk_summary_context(vm: PdfViewModel) -> dict[str, object]:
    cards: list[dict[str, object]] = []
    for risk in vm.top_risks[:3]:
        band = _normalize_risk_label(risk.risk, risk.score)
        bar_source = risk.percentile if risk.percentile is not None else risk.score
        try:
            bar_pct = max(0, min(100, int(round(float(bar_source)))))
        except (TypeError, ValueError):
            bar_pct = max(0, min(100, int(risk.score)))
        cards.append(
            {
                "disease_id": risk.disease_id,
                "title": _RISK_SUMMARY_TITLES.get(risk.disease_id, risk.title),
                "risk": band,
                "band_key": _band_key(band),
                "risk_line": _risk_summary_line(band, risk.percentile_label),
                "bar_pct": bar_pct,
                "insights": list(risk.insights)[:3],
            }
        )
    return {"cards": cards}


# Lifestyle meter marker centers (Figma 451:4652) — % along the gradient track.
_LIFESTYLE_MARKER_PCTS = (2.0, 28.0, 52.0, 76.0, 98.0)

# Progress-arc stroke colors (Figma disease gauges 451:4652 / 451:4799).
_GAUGE_COLORS = {
    "Healthy": "#063533",
    "Increased Risk": "#F8D232",
    "High Risk": "#EAA546",
    "Very High Risk": "#C6203B",
}


def _disease_detail_pages(vm: PdfViewModel) -> list[dict[str, object]]:
    pages: list[dict[str, object]] = []
    for index, card in enumerate(vm.disease_pages):
        band = _normalize_risk_label(card.risk, card.score)
        band_key = _band_key(band)
        life_idx = card.lifestyle_meter_index
        life_pct: float | None
        if life_idx is None:
            life_pct = None
        else:
            clamped = max(0, min(4, int(life_idx)))
            life_pct = _LIFESTYLE_MARKER_PCTS[clamped]
        try:
            pct_val = (
                max(0.0, min(100.0, float(card.percentile)))
                if card.percentile is not None
                else 0.0
            )
        except (TypeError, ValueError):
            pct_val = 0.0
        # Figma disease pages (e.g. 451:4799) show freeform factor chips as text-only pills.
        chips: list[dict[str, str]] = []
        for factor in card.contributing_factors:
            label = str(factor).strip()
            if not label:
                continue
            chips.append({"label": label, "icon_key": ""})
        pages.append(
            {
                "disease_id": card.disease_id,
                "title": card.title,
                "overview": card.overview,
                "score": card.score,
                "risk_label": band,
                "band_key": band_key,
                "gauge_color": _GAUGE_COLORS.get(band, "#063533"),
                "percentile_pct": pct_val,
                "percentile_label": card.percentile_label,
                "lifestyle_marker_pct": life_pct,
                "factor_chips": chips,
                "page_no": 8 + index + 1,
            }
        )
    return pages


_TRENDS_PER_PAGE = 6


def _health_trends_pages(vm: PdfViewModel) -> list[dict[str, object]]:
    """Chunk trend series into Figma-style 6-card chart pages (after disease section)."""
    if not vm.has_health_trends or not vm.health_trend_series:
        return []
    disease_end = 8 + len(vm.disease_pages)
    # Optional allergy/cancer pages sit between disease details and Health Trends.
    first_chart_page = disease_end + vm.allergy_cancer_page_count + 2
    pages: list[dict[str, object]] = []
    series = list(vm.health_trend_series)
    for page_index in range(0, len(series), _TRENDS_PER_PAGE):
        chunk = series[page_index : page_index + _TRENDS_PER_PAGE]
        cards = []
        for item in chunk:
            pts = [(p.date_label, float(p.score)) for p in item.points]
            cards.append(
                {
                    "disease_id": item.disease_id,
                    "title": item.title,
                    "chart_svg": trend_line_chart_svg(pts),
                }
            )
        pages.append(
            {
                "page_no": first_chart_page + (page_index // _TRENDS_PER_PAGE),
                "cards": cards,
            }
        )
    return pages


def build_report_html(
    vm: PdfViewModel,
    *,
    css_href: str | None = None,
    for_http: bool = False,
    page: str | None = None,
) -> str:
    """Return full HTML document for Chromium print-to-PDF or local preview.

    ``page`` can be a template id (e.g. ``CoverPage``) or page number string
    (e.g. ``1``) to render only that page for preview.
    """
    href = css_href or _css_href("report.css", for_http=for_http)
    toc_rows = [
        {
            "id": "diseases_index",
            "sr": "01",
            "section": "Lifestyle Diseases Covered",
            "page": "04",
            "dynamic_pages": False,
        },
        {
            "id": "health_summary",
            "sr": "02",
            "section": "Your Health Summary",
            "page": "05",
            "dynamic_pages": False,
        },
        {
            "id": "at_a_glance",
            "sr": "03",
            "section": "At A Glance",
            "page": "06",
            "dynamic_pages": False,
        },
        {
            "id": "risk_summary",
            "sr": "04",
            "section": "Risk Summary & Actionable Insights",
            "page": "07",
            "dynamic_pages": False,
        },
        {
            "id": "disease_analysis",
            "sr": "05",
            "section": "Lifestyle Diseases Risk Analysis",
            "page": vm.disease_page_range,
            "dynamic_pages": True,
        },
    ]
    if vm.has_allergy_cancer:
        toc_rows.append(
            {
                "id": "allergy_cancer",
                "sr": f"{len(toc_rows) + 1:02d}",
                "section": "Allergy & Cancer",
                "page": vm.allergy_cancer_page_range,
                "dynamic_pages": True,
            }
        )
    if vm.has_health_trends:
        toc_rows.append(
            {
                "id": "health_trends",
                "sr": f"{len(toc_rows) + 1:02d}",
                "section": "Health Trends",
                "page": vm.health_trends_page_range,
                "dynamic_pages": True,
            }
        )
    disease_end = 8 + len(vm.disease_pages)
    allergy_cancer_divider_page_no = (
        disease_end + 1 if vm.has_allergy_cancer else 0
    )
    cancer_content_pages = (1 if vm.cancer_screening else 0) + len(vm.cancer_details)
    cancer_divider_page_no = (
        disease_end + vm.allergy_cancer_page_count - cancer_content_pages
        if vm.has_cancer
        else 0
    )
    ht_divider_page_no = (
        disease_end + vm.allergy_cancer_page_count + 1 if vm.has_health_trends else 0
    )
    assets = page_asset_urls(vm.variant, for_http=for_http)
    template = _env().get_template("report.html")
    return template.render(
        vm=vm,
        css_href=href,
        cover_css_href=_css_href("cover.css", for_http=for_http),
        welcome_css_href=_css_href("welcome.css", for_http=for_http),
        toc_css_href=_css_href("toc.css", for_http=for_http),
        diseases_index_css_href=_css_href("diseases_index.css", for_http=for_http),
        health_summary_css_href=_css_href("health_summary.css", for_http=for_http),
        at_a_glance_css_href=_css_href("at_a_glance.css", for_http=for_http),
        risk_summary_css_href=_css_href("risk_summary.css", for_http=for_http),
        disease_divider_css_href=_css_href("disease_divider.css", for_http=for_http),
        disease_detail_css_href=_css_href("disease_detail.css", for_http=for_http),
        health_trends_divider_css_href=_css_href(
            "health_trends_divider.css", for_http=for_http
        ),
        health_trends_css_href=_css_href("health_trends.css", for_http=for_http),
        allergy_cancer_divider_css_href=_css_href(
            "allergy_cancer_divider.css", for_http=for_http
        ),
        allergy_overview_css_href=_css_href(
            "allergy_overview.css", for_http=for_http
        ),
        allergy_breakdown_css_href=_css_href(
            "allergy_breakdown.css", for_http=for_http
        ),
        allergy_insights_css_href=_css_href(
            "allergy_insights.css", for_http=for_http
        ),
        cancer_divider_css_href=_css_href("cancer_divider.css", for_http=for_http),
        cancer_screening_css_href=_css_href("cancer_screening.css", for_http=for_http),
        cancer_detail_css_href=_css_href("cancer_detail.css", for_http=for_http),
        back_cover_css_href=_css_href("back_cover.css", for_http=for_http),
        status_color=risk_color(vm.overall_status),
        assets=assets,
        hs=_health_summary_context(vm, assets),
        aag=_at_a_glance_context(vm),
        rs=_risk_summary_context(vm),
        disease_detail_pages=_disease_detail_pages(vm),
        health_trends_pages=_health_trends_pages(vm),
        ht_divider_page_no=ht_divider_page_no,
        allergy_cancer_divider_page_no=allergy_cancer_divider_page_no,
        cancer_divider_page_no=cancer_divider_page_no,
        toc_rows=toc_rows,
        preview_page=page,
        for_http=for_http,
    )
