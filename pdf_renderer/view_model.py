"""Build a validated PDF view-model from BioReport (gender-aware, disease_id keyed)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from modules.bioai_report.pdf_renderer import config as pdf_config
from modules.bioai_report.pdf_renderer.exceptions import PdfValidationError
from modules.bioai_report.report_engine import config as engine_config
from modules.bioai_report.report_engine.models.report import (
    AllergyCategory,
    AllergyInsight,
    AllergyNote,
    AllergyRecommendationCard,
    AllergySection,
    AllergySensitivity,
    BioReport,
    CancerDetail,
    CancerFollowupCard,
    CancerMarker,
    CancerSection,
    DiseaseSection,
    HealthTrends,
)


def _blank(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, str) and not value.strip():
        return "—"
    return str(value)


def _format_age(age: float | int | None) -> str:
    if age is None:
        return "—"
    if isinstance(age, float) and age.is_integer():
        return f"{int(age)} years"
    return f"{age} years"


def _format_assessment_date(raw: str | None) -> str:
    if not raw or not str(raw).strip():
        return "—"
    text = str(raw).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
    ):
        try:
            normalized = text.replace("Z", "+0000")
            if fmt.endswith("%z") and ":" == normalized[-3:-2]:
                normalized = normalized[:-3] + normalized[-2:]
            dt = datetime.strptime(normalized, fmt)
            return dt.strftime("%b %d, %Y")
        except ValueError:
            continue
    return text


def resolve_gender_variant(gender: str | None, sex: str | None) -> str:
    raw = (gender or sex or "").strip().lower()
    if raw in {"female", "f", "woman", "2"}:
        return "female"
    return "male"


def honorific_for_variant(variant: str) -> str:
    return "Ms." if variant == "female" else "Mr."


def disease_order_for_variant(variant: str) -> tuple[str, ...]:
    return (
        pdf_config.DISEASE_ORDER_FEMALE
        if variant == "female"
        else pdf_config.DISEASE_ORDER_MALE
    )


def index_order_for_variant(variant: str) -> tuple[str, ...]:
    return (
        pdf_config.INDEX_ORDER_FEMALE
        if variant == "female"
        else pdf_config.INDEX_ORDER_MALE
    )


def risk_color(risk: str | None, score: int | None = None) -> str:
    label = (risk or "").strip().lower()
    mapping = {
        "healthy": "#2ecc71",
        "increased": "#f1c40f",
        "increased risk": "#f1c40f",
        "high": "#e67e22",
        "high risk": "#e67e22",
        "very high": "#e74c3c",
        "very high risk": "#e74c3c",
    }
    if label in mapping:
        return mapping[label]
    if score is None:
        return "#95a5a6"
    for name, lo, hi, color in pdf_config.RISK_BANDS:
        if lo <= int(score) <= hi:
            return color
    return "#95a5a6"


def lifestyle_meter_index(value: float | int | None) -> int | None:
    """Map lifestyle_contribution to a 0–4 meter index; None if unknown."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return 0
    if number <= 25:
        return 1
    if number <= 50:
        return 2
    if number <= 75:
        return 3
    return 4


def _ordinal(n: float | int | None) -> str:
    if n is None:
        return "—"
    value = int(round(float(n)))
    if 10 <= value % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


@dataclass
class DiseaseCardVM:
    disease_id: str
    title: str
    overview: str
    score: int
    risk: str
    band: str
    percentile: float | int | None
    percentile_label: str
    lifestyle_contribution: float | int | None
    lifestyle_meter_index: int | None
    contributing_factors: list[str]
    risk_color: str
    insights: list[str] = field(default_factory=list)


@dataclass
class TrendPointVM:
    date_label: str
    score: float


@dataclass
class TrendSeriesVM:
    disease_id: str
    title: str
    points: list[TrendPointVM]


_DEFAULT_IGE_DESCRIPTION = (
    "Immunoglobulin E (IgE) are antibodies produced by the immune system. "
    "High levels indicate your body is overreacting to allergens, which can "
    "trigger asthma, eczema, or rhinitis."
)

_IGE_BANDS = ("LOW", "MODERATE", "INCREASED", "HIGH", "VERY HIGH")


@dataclass
class AllergyRowVM:
    name: str
    category: str
    value: str
    ref_range: str
    risk: str
    risk_tone: str


@dataclass
class AllergyOverviewVM:
    page_no: int
    ige_value: str
    ige_unit: str
    ige_band: str
    marker_pct: float
    marker_left: float
    recommendation: str
    ige_description: str
    ige_ref_low: str
    ige_ref_high: str
    total_tested: str
    sensitive_count: str
    normal_count: str
    rows: list[AllergyRowVM] = field(default_factory=list)


@dataclass
class AllergyCategoryVM:
    key: str
    name: str
    status: str
    status_tone: str
    items_text: str


@dataclass
class AllergyBreakdownVM:
    page_no: int
    subtitle: str
    intro: str
    node_id: str = "747:5335"
    categories: list[AllergyCategoryVM] = field(default_factory=list)


@dataclass
class AllergyInsightItemVM:
    name: str
    text: str


@dataclass
class AllergyRecoCardVM:
    title: str
    body: str


@dataclass
class AllergyNoteVM:
    title: str
    text: str


@dataclass
class AllergyInsightsVM:
    page_no: int
    insights: list[AllergyInsightItemVM] = field(default_factory=list)
    recommendations_title: str = "Actionable Recommendations"
    recommendations: list[AllergyRecoCardVM] = field(default_factory=list)
    notes: list[AllergyNoteVM] = field(default_factory=list)


@dataclass
class CancerMarkerVM:
    key: str
    name: str
    marker: str
    value: str
    ref: str
    unit: str
    status: str
    fill_pct: float
    icon: str
    highlight: bool


@dataclass
class CancerScreeningVM:
    page_no: int
    node_id: str = "747:5865"
    layout: str = "female"
    what_is_cancer: str = ""
    snapshot_title: str = "Your Cancer Marker Snapshot"
    in_range: int = 0
    total: int = 0
    donut_pct: float = 0.0
    highlight_name: str = ""
    highlight_marker: str = ""
    highlight_value: str = ""
    highlight_ref: str = ""
    insight_title: str = "Key Insights"
    insight_lead: str = ""
    insight_emphasis: str = ""
    insight_tail: str = ""
    markers: list[CancerMarkerVM] = field(default_factory=list)


@dataclass
class CancerFollowupVM:
    key: str
    title: str
    body: str
    icon: str
    tone: str


@dataclass
class CancerDetailVM:
    page_no: int
    node_id: str = "747:6246"
    detail_id: str = "breast"
    title: str = ""
    what_title: str = ""
    what_text: str = ""
    insights_title: str = ""
    insights: list[str] = field(default_factory=list)
    influences_title: str = ""
    influences: list[str] = field(default_factory=list)
    followup_title: str = "Recommended Follow-up"
    followup: list[CancerFollowupVM] = field(default_factory=list)


@dataclass
class PdfViewModel:
    variant: str
    honorific: str
    page_count: int
    disease_page_range: str
    patient_name: str
    patient_age: str
    patient_gender: str
    assessment_date: str
    metabolic_score: str
    metabolic_age: str
    overall_status: str
    bmi: str
    height: str
    weight: str
    record_id: str
    index_diseases: list[dict[str, Any]]
    glance_diseases: list[DiseaseCardVM]
    top_risks: list[DiseaseCardVM]
    disease_pages: list[DiseaseCardVM]
    tests_page1: dict[str, list[str]]
    tests_page2: dict[str, list[str]]
    template_version: str
    engine_version: str
    generated_at: str | None
    risk_bands: list[dict[str, Any]] = field(default_factory=list)
    lifestyle_levels: list[str] = field(default_factory=list)
    has_health_trends: bool = False
    health_trend_series: list[TrendSeriesVM] = field(default_factory=list)
    health_trends_page_range: str = ""
    health_trends_chart_page_count: int = 0
    has_allergy_cancer: bool = False
    has_allergy: bool = False
    has_cancer: bool = False
    allergy_cancer_page_range: str = ""
    allergy_cancer_page_count: int = 0
    allergy: AllergyOverviewVM | None = None
    allergy_breakdown: AllergyBreakdownVM | None = None
    allergy_breakdown_pages: list[AllergyBreakdownVM] = field(default_factory=list)
    allergy_insights: AllergyInsightsVM | None = None
    cancer_screening: CancerScreeningVM | None = None
    cancer_details: list[CancerDetailVM] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def canonicalize_disease_id(disease_id: str) -> str:
    """Map upstream aliases (e.g. pcos) to PDF catalog ids (pcos_pcod)."""
    return pdf_config.DISEASE_ID_ALIASES.get(disease_id, disease_id)


def _section_map(report: BioReport) -> dict[str, DiseaseSection]:
    return {
        canonicalize_disease_id(section.disease_id): section
        for section in report.disease_sections
    }


def _card_from_section(
    section: DiseaseSection,
    *,
    disease_id: str | None = None,
    insights: list[str] | None = None,
) -> DiseaseCardVM:
    score = int(section.current_status.score)
    canonical_id = disease_id or canonicalize_disease_id(section.disease_id)
    title = pdf_config.DISEASE_DISPLAY_NAMES.get(canonical_id) or section.title
    return DiseaseCardVM(
        disease_id=canonical_id,
        title=title,
        overview=section.overview or "",
        score=score,
        risk=section.current_status.risk,
        band=section.current_status.band,
        percentile=section.current_status.percentile,
        percentile_label=_ordinal(section.current_status.percentile),
        lifestyle_contribution=section.current_status.lifestyle_contribution,
        lifestyle_meter_index=lifestyle_meter_index(
            section.current_status.lifestyle_contribution
        ),
        contributing_factors=list(section.contributing_factors or []),
        risk_color=risk_color(section.current_status.risk, score),
        insights=list(insights or []),
    )


def validate_view_model(report: BioReport, vm: PdfViewModel) -> None:
    """Hard gate — raise if rendered values would disagree with BioReport JSON."""
    errors: list[str] = []
    by_id = _section_map(report)

    expected_variant = resolve_gender_variant(report.patient.gender, report.patient.sex)
    if vm.variant != expected_variant:
        errors.append(
            f"gender variant mismatch: view={vm.variant} patient={expected_variant}"
        )

    if len(vm.disease_pages) != len(
        [d for d in disease_order_for_variant(vm.variant) if d in by_id]
    ):
        errors.append(
            f"disease page count mismatch: rendered={len(vm.disease_pages)} "
            f"available_for_variant={len([d for d in disease_order_for_variant(vm.variant) if d in by_id])}"
        )

    seen_tips: dict[str, set[str]] = {}
    for page in vm.disease_pages:
        source = by_id.get(page.disease_id)
        if source is None:
            errors.append(f"unknown disease_id on page: {page.disease_id}")
            continue
        if page.score != int(source.current_status.score):
            errors.append(
                f"{page.disease_id}: score {page.score} != json {source.current_status.score}"
            )
        if page.title != source.title:
            display = pdf_config.DISEASE_DISPLAY_NAMES.get(page.disease_id)
            if display is None or page.title != display:
                errors.append(f"{page.disease_id}: title mismatch")
        if page.risk != source.current_status.risk:
            errors.append(f"{page.disease_id}: risk mismatch")
        tip_set = set(page.insights)
        for other_id, other_tips in seen_tips.items():
            leaked = tip_set & other_tips
            # Only flag if tip exists solely on another disease in JSON and not this one.
            if not leaked:
                continue
            source_tips = set(
                list(source.lifestyle.tips)
                + list(source.nutrition.recommendations)
                + list(source.lifestyle.exercise)
            )
            foreign = leaked - source_tips
            if foreign:
                errors.append(
                    f"cross-disease tip leakage on {page.disease_id} from {other_id}: {sorted(foreign)[:2]}"
                )
        seen_tips[page.disease_id] = tip_set

    for risk in vm.top_risks:
        source = by_id.get(risk.disease_id)
        if source is None:
            errors.append(f"top risk unknown disease_id: {risk.disease_id}")
            continue
        if risk.score != int(source.current_status.score):
            errors.append(f"top risk {risk.disease_id}: score mismatch")
        for tip in risk.insights:
            allowed = set(
                list(source.lifestyle.tips)
                + list(source.nutrition.recommendations)
                + list(source.lifestyle.exercise)
            )
            if tip not in allowed:
                errors.append(
                    f"top risk {risk.disease_id}: insight not from disease arrays: {tip!r}"
                )

    if "pcos_pcod" in {p.disease_id for p in vm.disease_pages} and vm.variant == "male":
        errors.append("male variant must not render pcos_pcod")

    if errors:
        raise PdfValidationError("; ".join(errors))


def _format_trend_date(raw: str | None) -> str:
    if not raw or not str(raw).strip():
        return "—"
    text = str(raw).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        "%d %b %Y",
        "%d %b '%y",
    ):
        try:
            normalized = text.replace("Z", "+0000")
            if fmt.endswith("%z") and len(normalized) > 5 and ":" == normalized[-3:-2]:
                normalized = normalized[:-3] + normalized[-2:]
            dt = datetime.strptime(normalized, fmt)
            return f"{dt.day} {dt.strftime('%b')} '{dt.strftime('%y')}"
        except ValueError:
            continue
    return text


def _trend_series_from_report(
    report: BioReport,
    *,
    variant: str,
) -> list[TrendSeriesVM]:
    """Build chart series when ``health_trends`` is present; otherwise empty."""
    block: HealthTrends | None = report.health_trends
    if block is None or not block.series:
        return []

    allowed = set(disease_order_for_variant(variant))
    out: list[TrendSeriesVM] = []
    for series in block.series:
        disease_id = canonicalize_disease_id(series.disease_id)
        if disease_id not in allowed:
            continue
        points_raw = list(series.points or [])
        if len(points_raw) < 2:
            continue
        title = (
            (series.title or "").strip()
            or (
                "PCOS"
                if disease_id == "pcos_pcod"
                else pdf_config.DISEASE_DISPLAY_NAMES.get(disease_id)
            )
            or disease_id.replace("_", " ").title()
        )
        points = [
            TrendPointVM(
                date_label=_format_trend_date(str(p.date)),
                score=float(p.score),
            )
            for p in points_raw
        ]
        out.append(TrendSeriesVM(disease_id=disease_id, title=title, points=points))
    return out


def _allergy_risk_tone(risk: str) -> str:
    label = (risk or "").strip().lower()
    if any(token in label for token in ("class 5", "class 6", "very high")):
        return "severe"
    if any(token in label for token in ("class 3", "class 4", "high", "moderate")):
        return "high"
    return "low"


# Figma 747:5225 — marker sits on the 496px track (offset 11px).
_IGE_TRACK_LEFT = 11.0
_IGE_TRACK_WIDTH = 496.0
_IGE_BAND_MARKERS = {
    "LOW": 0.0,
    "MODERATE": 25.0,
    "INCREASED": 50.0,
    "HIGH": 75.0,
    "VERY HIGH": 98.0,
}


def _ige_band_and_marker(
    value: float | None, ref_high: float, explicit_band: str | None
) -> tuple[str, float]:
    band = (explicit_band or "").strip().upper().replace("_", " ")
    if band in {"VERYHIGH"}:
        band = "VERY HIGH"
    if band in _IGE_BAND_MARKERS:
        return band, _IGE_BAND_MARKERS[band]
    if value is None:
        return "LOW", _IGE_BAND_MARKERS["LOW"]
    if value <= ref_high * 0.25:
        return "LOW", _IGE_BAND_MARKERS["LOW"]
    if value <= ref_high * 0.6:
        return "MODERATE", _IGE_BAND_MARKERS["MODERATE"]
    if value <= ref_high:
        return "INCREASED", _IGE_BAND_MARKERS["INCREASED"]
    if value <= ref_high * 3:
        return "HIGH", _IGE_BAND_MARKERS["HIGH"]
    return "VERY HIGH", _IGE_BAND_MARKERS["VERY HIGH"]


def _format_ige_number(value: float | int | str | None) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    text = f"{number:.1f}"
    return text.rstrip("0").rstrip(".") if "." in text else text


def _format_allergen_value(value: float | int | str | None) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}"


def _allergy_payload_dict(section: AllergySection) -> dict[str, Any]:
    data = section.model_dump()
    extra = getattr(section, "model_extra", None) or {}
    if extra:
        data.update(extra)
    return data


def _allergy_overview_from_report(
    report: BioReport, *, page_no: int
) -> AllergyOverviewVM | None:
    section = report.allergy
    if section is None:
        return None
    data = _allergy_payload_dict(section)
    ige_raw = (
        data.get("total_ige")
        if data.get("total_ige") is not None
        else data.get("ige")
        if data.get("ige") is not None
        else data.get("total_ige_level")
    )
    try:
        ige_value = float(ige_raw) if ige_raw is not None and ige_raw != "" else None
    except (TypeError, ValueError):
        ige_value = None
    ref_low = float(data.get("ige_ref_low") or 1.5)
    ref_high = float(data.get("ige_ref_high") or 158.0)
    unit = str(data.get("ige_unit") or "IU/ml")
    band, marker_pct = _ige_band_and_marker(
        ige_value, ref_high, data.get("ige_band")
    )
    raw_rows = data.get("sensitivities") or data.get("items") or []
    rows: list[AllergyRowVM] = []
    for item in raw_rows:
        if isinstance(item, AllergySensitivity):
            row = item
        elif isinstance(item, dict):
            try:
                row = AllergySensitivity.model_validate(item)
            except Exception:  # noqa: BLE001
                continue
        else:
            continue
        rows.append(
            AllergyRowVM(
                name=row.name,
                category=row.category,
                value=_format_allergen_value(row.value),
                ref_range=row.ref_range or "<0.35",
                risk=row.risk,
                risk_tone=_allergy_risk_tone(row.risk),
            )
        )
    sensitive = data.get("sensitive_count")
    if sensitive is None:
        sensitive = len(rows)
    total_tested = data.get("total_allergens_tested")
    if total_tested is None:
        total_tested = f"{max(sensitive, 0)}+" if not rows else str(max(100, sensitive))
    normal = data.get("normal_count")
    if normal is None:
        try:
            total_n = int(str(total_tested).replace("+", "").strip() or 0)
            normal = f"{max(total_n - int(sensitive), 0)}+"
        except (TypeError, ValueError):
            normal = "—"
    recommendation = (data.get("recommendation") or "").strip()
    if not recommendation and ige_value is not None and ige_value > ref_high:
        multiple = ige_value / ref_high
        recommendation = (
            f"Your IgE level is {multiple:.0f}x above normal limits, indicating "
            f"severe systemic allergic sensitivity. Normal levels- ({_format_ige_number(ref_low)}-"
            f"{_format_ige_number(ref_high)} {unit})"
        )
    elif not recommendation:
        recommendation = (
            f"Normal levels- ({_format_ige_number(ref_low)}-"
            f"{_format_ige_number(ref_high)} {unit})"
        )
    description = (data.get("ige_description") or "").strip() or _DEFAULT_IGE_DESCRIPTION
    return AllergyOverviewVM(
        page_no=page_no,
        ige_value=_format_ige_number(ige_value),
        ige_unit=unit,
        ige_band=band,
        marker_pct=marker_pct,
        marker_left=_IGE_TRACK_LEFT + (marker_pct / 100.0) * _IGE_TRACK_WIDTH,
        recommendation=recommendation,
        ige_description=description,
        ige_ref_low=_format_ige_number(ref_low),
        ige_ref_high=_format_ige_number(ref_high),
        total_tested=str(total_tested),
        sensitive_count=str(sensitive),
        normal_count=str(normal),
        rows=rows,
    )


_DEFAULT_BREAKDOWN_SUBTITLE = "Normal Categories (No Significant Reaction)"
_DEFAULT_BREAKDOWN_INTRO = (
    "The following categories showed no significant allergic reaction "
    "(<0.35 IU/mL / Class 0)."
)

_CATEGORY_ICON_ALIASES = {
    "drugs": "drugs",
    "drug": "drugs",
    "pets": "pets",
    "pets/animals": "pets",
    "pets_animals": "pets",
    "animals": "pets",
    "insects": "insects",
    "insect": "insects",
    "non_veg": "non_veg",
    "non veg food": "non_veg",
    "non-veg": "non_veg",
    "nonveg": "non_veg",
    "dairy": "dairy",
    "dairy products": "dairy",
    "moulds": "moulds",
    "molds": "moulds",
    "moulds & yeast": "moulds",
    "moulds and yeast": "moulds",
    "occupational": "occupational",
    "occupational material": "occupational",
    "parasites": "parasites",
    "parasite": "parasites",
    "grass": "grass",
    "grasses": "grass",
    "weed_tree": "weed_tree",
    "weed & tree": "weed_tree",
    "weed and tree": "weed_tree",
    "weeds": "weed_tree",
    "nuts": "nuts",
    "seed /nuts/ legumes": "nuts",
    "seed/nuts/legumes": "nuts",
    "seeds": "nuts",
    "legumes": "nuts",
    "dust_mites": "dust_mites",
    "dust mites": "dust_mites",
    "dust mite": "dust_mites",
    "vegetables": "vegetables",
    "vegetables & fruits": "vegetables",
    "vegetables and fruits": "vegetables",
    "fruits": "vegetables",
    "spices": "spices",
    "spice": "spices",
}

_DEFAULT_NORMAL_CATEGORIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "drugs",
        "Drugs",
        (
            "Penicilloyl V",
            "Penicilloyl G",
            "Prilocaine",
            "Thiamine (Vitamin B1)",
            "Ciprofloxacin",
            "Oxacillin",
            "Ofloxacin",
            "Metronidazole",
            "Paracetamol",
            "Ascorbic Acid (Vitamin C)",
            "Ampicillin",
            "Azithromycin",
            "Amoxicillin",
            "Tetracycline",
            "Cephalosporin",
            "Gentamycin",
            "Diclofenac",
            "Bromhexine",
            "Ibuprofen",
            "Chloramphenicol",
            "Aspirin",
            "Cobalamin (Vitamin B12)",
            "Benzocaine",
            "Sulfamethoxazole",
        ),
    ),
    (
        "pets",
        "Pets/Animals",
        (
            "Cat Epithelium",
            "Cat Dander",
            "Canarian Feathers",
            "Pigeon Feathers",
            "Pigeon Droppings",
            "Chicken Droppings",
            "Goose Feathers",
            "Cow Dander",
            "Budgerigar Dropping",
            "Dog Epithelium",
            "Budgerigar Feathers",
            "Dog Dander",
            "Budgerigar Serum Proteins",
            "Rabbit Epithelium",
            "Goat Epithelium",
            "Chicken Feathers",
            "Sheep Epithelium",
            "Duck Feathers",
            "Pig Epithelium",
            "Epithelium + Serum Proteins Mouse",
            "Turkey Feathers",
        ),
    ),
    (
        "insects",
        "Insects",
        (
            "Housefly (Musca Domestica)",
            "Apis Mellifera (Honey Bee)",
            "Vespula Germanica (Common Wasp / Yellow Jacket)",
            "Blattella Germanica (Cockroach)",
            "Heterocera Mix (Moth)",
            "Aedes Communis (Mosquito)",
        ),
    ),
    (
        "non_veg",
        "Non Veg food",
        (
            "Mackerel",
            "Carp Fish",
            "Crab",
            "Shrimp",
            "Lobster",
            "Sardine",
            "Salmon",
            "Mutton",
            "Fish (Cod)",
            "Chicken Meat",
            "Turkey",
            "Duck Meat",
            "Beef",
            "Pork",
            "Whole Egg (Hen)",
            "Egg Yolk ELISA",
            "Egg White ELISA",
        ),
    ),
    (
        "dairy",
        "Dairy products",
        (
            "Cheese (Cheddar Type)",
            "Chocolate",
            "Tea",
            "Curd",
            "Yogurt",
            "Mushrooms",
            "Coconut Milk",
            "Coffee",
            "Tofu (Bean Curd)",
            "Cow Milk",
            "Yeast",
            "Casein (Milk Protein)",
        ),
    ),
    (
        "moulds",
        "Moulds & yeast",
        (
            "Penicillium Notatum",
            "Cladosporium Herbarum",
            "Aspergillus Fumigatus",
            "Mucor Racemosus",
            "Candida Albicans",
            "Alternaria Alternata",
            "Curvularia Lunata",
            "Trichoderma Viride",
            "Phoma Betae",
            "Rhizopus Nigricans",
        ),
    ),
    (
        "occupational",
        "Occupational material",
        (
            "Cotton Linters",
            "Sheep Wool (Treated)",
            "Latex",
            "Jute",
            "Silk (Bombyx Mori)",
            "Henna",
        ),
    ),
    (
        "parasites",
        "Parasites",
        (
            "Ascaris Lumbricoides",
            "Anisakis",
            "Toxocara Canis",
        ),
    ),
    (
        "grass",
        "Grass",
        (
            "Cynodon Dactylon (Bermuda Grass)",
            "Lolium Perenne (Ryegrass)",
            "Agrostis Stolonifera (Bentgrass)",
            "Sorghum Halepense (Johnson Grass)",
            "Dactylis Glomerata (Cock’s Foot)",
            "Festuca Elatior (Meadow Fescue)",
            "Phleum Pratense (Timothy Grass)",
            "Phragmites Communis (Common Reed)",
        ),
    ),
    (
        "weed_tree",
        "Weed & tree",
        (
            "Eucalyptus spp (Gum Tree)",
            "Morus Alba (Red Mulberry)",
            "Prosopis Juliflora (Mesquite)",
            "Acacia spp (Acacia)",
            "Salix Caprea (Willow)",
            "Oak Wood",
            "Amaranthus Retroflexus (Common Pigweed)",
            "Xanthium Commune (Cocklebur)",
            "Artemisia Vulgaris (Mugwort)",
            "Chenopodium Album (Goosefoot)",
            "Brassica Napus (Rape)",
        ),
    ),
    (
        "nuts",
        "Seed /Nuts/ Legumes",
        (
            "Maize",
            "Walnut",
            "Raisin",
            "Pumpkin Seed",
            "Soya Bean",
            "Cashew Nut",
            "Lentil",
            "Sunflower Seed",
            "Sesame Seed",
            "Pea",
            "Peanut",
            "Semolina",
            "Pistachio Nut",
            "Coconut",
            "Wheat Flour",
            "Oats",
            "Almond",
            "Flaxseed",
            "Barley",
            "Hazelnut",
            "Poppy (Seed)",
        ),
    ),
    (
        "dust_mites",
        "Dust Mites",
        (
            "Books Dust",
            "Hay Dust",
            "Dermatophagoides Pteronyssinus",
            "Dermatophagoides Farinae",
            "Glycyphagus Domesticus",
            "Blomia Tropicalis",
            "Acarus Siro",
            "Dermatophagoides Microceras",
            "Lepidoglyphus Destructor",
            "House Dust (Ifci 1)",
            "Euroglyphus Maynei",
        ),
    ),
    (
        "vegetables",
        "Vegetables & fruits",
        (
            "Pumpkin",
            "Sweet Potato",
            "Spinach",
            "Cabbage",
            "Cucumber",
            "French Bean",
            "Tomato",
            "Red Radish",
            "Lemon",
            "Lettuce",
            "Carrot",
            "Broccoli",
            "Beet",
            "Potato",
            "Date",
            "Onion",
            "Garlic",
            "Pineapple",
            "Plum",
            "Grape",
            "Guava",
            "Egg Plant (Aubergine)",
            "Apricot",
            "Cherry",
            "Millet",
            "Chick Pea",
            "Cauliflower",
            "Fig",
            "Watermelon",
            "Orange",
            "Cranberry",
            "Lychee",
            "Apple",
            "Melon",
            "Mango",
            "Papaya",
            "Pomegranate",
            "Olive",
            "Strawberry",
            "Kiwi",
            "Rice",
            "Banana",
        ),
    ),
    (
        "spices",
        "Spices",
        (
            "Cardamom",
            "Cinnamon",
            "Mint",
            "Ginger",
            "Mustard",
            "Coriander",
            "Saffron",
            "Basil",
            "Sweet Pepper",
            "Vanilla",
            "Anise",
            "Thyme",
            "Fennel",
            "Curry",
            "Oregano",
            "Cloves",
            "Black Pepper",
            "Nutmeg",
            "Curcuma",
        ),
    ),
)

_BREAKDOWN_FIRST_PAGE_SIZE = 8
_BREAKDOWN_PAGE_NODES = ("747:5335", "747:5471")


def _category_icon_key(raw_id: str, name: str) -> str:
    for token in (raw_id, name):
        key = _CATEGORY_ICON_ALIASES.get((token or "").strip().lower())
        if key:
            return key
    return "drugs"


def _category_status_tone(status: str) -> str:
    label = (status or "").strip().lower()
    if any(token in label for token in ("class 5", "class 6", "very high", "severe", "high")):
        return "high"
    if any(token in label for token in ("class 1", "class 2", "class 3", "class 4", "sensitive", "low")):
        return "sensitive"
    return "normal"


def _allergy_breakdown_pages_from_report(
    report: BioReport, *, first_page_no: int
) -> list[AllergyBreakdownVM]:
    section = report.allergy
    if section is None:
        return []
    data = _allergy_payload_dict(section)
    raw_rows = (
        data.get("normal_categories")
        or data.get("categories")
        or data.get("normal_category_cards")
        or []
    )
    categories: list[AllergyCategoryVM] = []
    for item in raw_rows:
        if isinstance(item, AllergyCategory):
            row = item
        elif isinstance(item, dict):
            try:
                row = AllergyCategory.model_validate(item)
            except Exception:  # noqa: BLE001
                continue
        else:
            continue
        key = _category_icon_key(row.id, row.name)
        categories.append(
            AllergyCategoryVM(
                key=key,
                name=row.name,
                status=row.status or "Normal",
                status_tone=_category_status_tone(row.status),
                items_text=", ".join(row.items),
            )
        )
    if not categories:
        categories = [
            AllergyCategoryVM(
                key=key,
                name=title,
                status="Normal",
                status_tone="normal",
                items_text=", ".join(items),
            )
            for key, title, items in _DEFAULT_NORMAL_CATEGORIES
        ]
    if not categories:
        return []
    subtitle = (data.get("breakdown_subtitle") or "").strip() or _DEFAULT_BREAKDOWN_SUBTITLE
    intro = (data.get("breakdown_intro") or "").strip() or _DEFAULT_BREAKDOWN_INTRO
    chunks = [
        categories[:_BREAKDOWN_FIRST_PAGE_SIZE],
        categories[_BREAKDOWN_FIRST_PAGE_SIZE:],
    ]
    pages: list[AllergyBreakdownVM] = []
    for index, chunk in enumerate(chunks):
        if not chunk:
            continue
        pages.append(
            AllergyBreakdownVM(
                page_no=first_page_no + index,
                subtitle=subtitle,
                intro=intro,
                node_id=_BREAKDOWN_PAGE_NODES[min(index, len(_BREAKDOWN_PAGE_NODES) - 1)],
                categories=chunk,
            )
        )
    return pages


_DEFAULT_INSIGHTS: tuple[tuple[str, str], ...] = (
    (
        "Tyrophagus Putrescentiae",
        "You show low to moderate sensitivity to this storage mite, commonly "
        "found in stored food (grains, nuts) and can contribute to asthma or "
        "dermatitis. Ensure dry storage of pantry items.",
    ),
    (
        "Tobacco Dust",
        "Class 1 sensitivity detected. Avoid exposure to tobacco smoke or "
        "historical smoke residue as it may trigger inflammation or histamine "
        "release in your Bio-AI markers.",
    ),
)

_DEFAULT_RECO_TITLE = "Actionable Recommendations (Dust Mite Control)"

_DEFAULT_RECOMMENDATIONS: tuple[tuple[str, str], ...] = (
    (
        "Bedding Protection",
        "Encase mattresses, box springs, and pillows in certified allergen-proof "
        "covers. Wash all bedding weekly in hot water (>130°F / 54°C).",
    ),
    (
        "Humidity Control",
        "Dust mites thrive in humidity. Maintain indoor humidity levels strictly "
        "below 50% using a dehumidifier or air conditioning.",
    ),
    (
        "Air Quality & Cleaning",
        "Vacuum carpets and fabric furniture weekly using a HEPA filter vacuum. "
        "Use a damp cloth or oiled rag for surface dusting.",
    ),
    (
        "Environment Optimization",
        "Minimize dust-collecting items like heavy drapes, upholstered furniture, "
        "and plush toys in the bedroom where possible.",
    ),
)

_DEFAULT_NOTES: tuple[tuple[str, str], ...] = (
    (
        "Cross-Reactivity:",
        "False positives can occur due to shared proteins between environmental "
        "allergens and certain food proteins.",
    ),
    (
        "Medication Influence:",
        "The intake of antihistamines prior to testing may lead to false-negative "
        "results.",
    ),
    (
        "Clinical Correlation:",
        "A normal IgE level for a specific allergen does not entirely eliminate "
        "the possibility of allergic disease; results must be correlated with "
        "your specific symptoms by a doctor.",
    ),
)


def _insight_text_from_item(item: AllergyInsight | dict[str, Any]) -> str:
    if isinstance(item, AllergyInsight):
        return item.text
    return str(
        item.get("text")
        or item.get("insight")
        or item.get("description")
        or ""
    ).strip()


def _allergy_insights_from_report(
    report: BioReport, *, page_no: int
) -> AllergyInsightsVM | None:
    section = report.allergy
    if section is None:
        return None
    data = _allergy_payload_dict(section)
    raw_insights = data.get("insights") or data.get("clinical_insights") or []
    insights: list[AllergyInsightItemVM] = []
    for item in raw_insights:
        if isinstance(item, AllergyInsight):
            name, text = item.name, item.text
        elif isinstance(item, dict) and item.get("name"):
            name, text = str(item["name"]), _insight_text_from_item(item)
        else:
            continue
        insights.append(AllergyInsightItemVM(name=name, text=text))
    if not insights:
        insights = [
            AllergyInsightItemVM(name=name, text=text)
            for name, text in _DEFAULT_INSIGHTS
        ]
    raw_recos = data.get("recommendations") or data.get("actionable_recommendations") or []
    recommendations: list[AllergyRecoCardVM] = []
    for item in raw_recos:
        if isinstance(item, AllergyRecommendationCard):
            title, body = item.title, item.body
        elif isinstance(item, dict) and item.get("title"):
            title = str(item["title"])
            body = str(item.get("body") or item.get("text") or item.get("description") or "")
        else:
            continue
        recommendations.append(AllergyRecoCardVM(title=title, body=body))
    if not recommendations:
        recommendations = [
            AllergyRecoCardVM(title=title, body=body)
            for title, body in _DEFAULT_RECOMMENDATIONS
        ]
    raw_notes = data.get("interpretative_notes") or data.get("notes") or []
    notes: list[AllergyNoteVM] = []
    for item in raw_notes:
        if isinstance(item, AllergyNote):
            title, text = item.title, item.text
        elif isinstance(item, dict) and item.get("title"):
            title = str(item["title"])
            text = str(item.get("text") or item.get("body") or "")
        else:
            continue
        notes.append(AllergyNoteVM(title=title, text=text))
    if not notes:
        notes = [AllergyNoteVM(title=title, text=text) for title, text in _DEFAULT_NOTES]
    reco_title = (
        (data.get("recommendations_title") or "").strip() or _DEFAULT_RECO_TITLE
    )
    return AllergyInsightsVM(
        page_no=page_no,
        insights=insights,
        recommendations_title=reco_title,
        recommendations=recommendations,
        notes=notes,
    )


_DEFAULT_CANCER_WHAT = (
    "Cancer occurs when cells in the body grow and divide uncontrollably, "
    "forming abnormal masses or tumors."
)
_DEFAULT_CANCER_SNAPSHOT_TITLE = "Your Cancer Marker Snapshot"
_DEFAULT_CANCER_INSIGHT_TITLE = "Key Insights"
_CANCER_FILL_PCT = {"optimal": 28.0, "marginal": 50.0, "critical": 100.0}
_CANCER_ICON_ALIASES = {
    "afp": "afp",
    "amniotic": "afp",
    "liver": "afp",
    "breast": "breast",
    "ca15": "breast",
    "ca_15": "breast",
    "ca153": "breast",
    "ovarian": "ovarian",
    "ovary": "ovarian",
    "prostate": "prostate",
    "psa": "prostate",
    "colorectal": "colorectal",
    "colon": "colorectal",
    "cea": "colorectal",
    "pancreatic": "pancreatic",
    "pancreas": "pancreatic",
}
_DEFAULT_FEMALE_CANCER_MARKERS: tuple[dict[str, Any], ...] = (
    {
        "id": "afp",
        "name": "AFP (Amniotic Fluid)",
        "value": 2.3,
        "unit": "ng/ml",
        "ref": 2.3,
        "status": "optimal",
    },
    {
        "id": "breast",
        "name": "Breast Cancer",
        "marker": "CA 15.3",
        "value": 5.2,
        "unit": "ng/ml",
        "ref": 2.3,
        "status": "critical",
        "highlight": True,
    },
    {
        "id": "ovarian",
        "name": "Ovarian Cancer",
        "value": 2.3,
        "unit": "ng/ml",
        "ref": 2.3,
        "status": "optimal",
    },
    {
        "id": "colorectal",
        "name": "Colorectal Cancer",
        "value": 2.3,
        "unit": "ng/ml",
        "ref": 2.3,
        "status": "marginal",
    },
    {
        "id": "pancreatic",
        "name": "Pancreatic Cancer",
        "value": 2.3,
        "unit": "ng/ml",
        "ref": 2.3,
        "status": "optimal",
    },
)
_DEFAULT_MALE_CANCER_MARKERS: tuple[dict[str, Any], ...] = (
    {
        "id": "liver",
        "name": "Liver Related Cancer",
        "value": 2.3,
        "unit": "ng/ml",
        "ref": 2.3,
        "status": "optimal",
    },
    {
        "id": "prostate",
        "name": "Prostate Cancer",
        "value": 2.3,
        "unit": "ng/ml",
        "ref": 2.3,
        "status": "optimal",
    },
    {
        "id": "colorectal",
        "name": "Colorectal Cancer",
        "marker": "CEA",
        "value": 5.2,
        "unit": "ng/ml",
        "ref": 2.3,
        "status": "marginal",
        "highlight": True,
    },
    {
        "id": "pancreatic",
        "name": "Pancreatic Cancer",
        "value": 2.3,
        "unit": "ng/ml",
        "ref": 2.3,
        "status": "optimal",
    },
)
_CANCER_NODE_IDS = {"female": "747:5865", "male": "741:881"}


def _cancer_payload_dict(section: CancerSection) -> dict[str, Any]:
    data = section.model_dump()
    extra = getattr(section, "model_extra", None) or {}
    if extra:
        data.update(extra)
    return data


def _format_cancer_number(value: float | int | str | None) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.1f}"


def _cancer_status(raw: str | None, value: Any, ref: Any, *, highlight: bool) -> str:
    label = (raw or "").strip().lower()
    aliases = {
        "optimal": "optimal",
        "normal": "optimal",
        "in range": "optimal",
        "low": "optimal",
        "marginal": "marginal",
        "borderline": "marginal",
        "increased": "marginal",
        "critical": "critical",
        "high": "critical",
        "elevated": "critical",
        "out of range": "critical",
    }
    if label in aliases:
        return aliases[label]
    if highlight:
        return "critical"
    try:
        number = float(value)
        ceiling = float(ref)
    except (TypeError, ValueError):
        return "optimal"
    if number <= ceiling:
        return "optimal"
    if number <= ceiling * 1.5:
        return "marginal"
    return "critical"


def _cancer_icon_key(marker_id: str, name: str, icon: str) -> str:
    raw = (icon or marker_id or name or "").strip().lower().replace(" ", "_")
    compact = raw.replace("-", "_")
    for alias, key in _CANCER_ICON_ALIASES.items():
        if alias in compact:
            return key
    return "afp"


def _split_insight(text: str, emphasis: str) -> tuple[str, str, str]:
    if emphasis:
        idx = text.lower().find(emphasis.lower())
        if idx >= 0:
            end = idx + len(emphasis)
            return text[:idx], text[idx:end], text[end:]
    return text, "", ""


def _cancer_screening_from_report(
    report: BioReport, *, variant: str, page_no: int
) -> CancerScreeningVM | None:
    section = report.cancer
    if section is None or variant not in {"female", "male"}:
        return None
    data = _cancer_payload_dict(section)
    raw_markers = data.get("markers") or data.get("items") or data.get("screening") or []
    parsed: list[CancerMarker] = []
    for item in raw_markers:
        if isinstance(item, CancerMarker):
            parsed.append(item)
        elif isinstance(item, dict) and item.get("name"):
            try:
                parsed.append(CancerMarker.model_validate(item))
            except Exception:  # noqa: BLE001
                continue
    if not parsed:
        catalog = (
            _DEFAULT_FEMALE_CANCER_MARKERS
            if variant == "female"
            else _DEFAULT_MALE_CANCER_MARKERS
        )
        parsed = [CancerMarker.model_validate(item) for item in catalog]

    markers: list[CancerMarkerVM] = []
    for item in parsed:
        unit = (item.unit or "ng/ml").strip() or "ng/ml"
        status = _cancer_status(
            item.status, item.value, item.ref, highlight=item.highlight
        )
        value_num = _format_cancer_number(item.value)
        ref_raw = item.ref
        if isinstance(ref_raw, str) and any(ch.isalpha() for ch in ref_raw):
            ref_label = ref_raw if ref_raw.lower().startswith("ref") else f"Ref : {ref_raw}"
        else:
            ref_label = f"Ref : {_format_cancer_number(ref_raw)} {unit}"
        key = (item.id or _cancer_icon_key(item.id, item.name, item.icon)).strip().lower()
        icon = _cancer_icon_key(item.id, item.name, item.icon)
        markers.append(
            CancerMarkerVM(
                key=key or icon,
                name=item.name,
                marker=(item.marker or "").strip(),
                value=f"{value_num} {unit}".strip(),
                ref=ref_label,
                unit=unit,
                status=status,
                fill_pct=_CANCER_FILL_PCT.get(status, 28.0),
                icon=icon,
                highlight=bool(item.highlight) or status == "critical",
            )
        )

    highlighted = next((m for m in markers if m.highlight), None)
    if highlighted is None and markers:
        highlighted = next((m for m in markers if m.status != "optimal"), markers[0])
    in_range = sum(1 for m in markers if not m.highlight)
    total = len(markers)
    donut_pct = (in_range / total * 100.0) if total else 0.0

    default_emphasis = (highlighted.name if highlighted else "").strip()
    if variant == "male" and highlighted and highlighted.key == "colorectal":
        default_emphasis = "Colorectal"
    insight = (data.get("insight") or "").strip()
    if not insight and default_emphasis:
        insight = (
            f"Most markers are within range, with an elevated "
            f"{default_emphasis.lower() if variant == 'female' else default_emphasis} "
            f"requiring further evaluation."
        )
    lead, emphasis, tail = _split_insight(insight, default_emphasis)

    return CancerScreeningVM(
        page_no=page_no,
        node_id=_CANCER_NODE_IDS.get(variant, "747:5865"),
        layout=variant,
        what_is_cancer=(data.get("what_is_cancer") or "").strip() or _DEFAULT_CANCER_WHAT,
        snapshot_title=(
            (data.get("snapshot_title") or "").strip() or _DEFAULT_CANCER_SNAPSHOT_TITLE
        ),
        in_range=in_range,
        total=total,
        donut_pct=donut_pct,
        highlight_name=highlighted.name if highlighted else "",
        highlight_marker=highlighted.marker if highlighted else "",
        highlight_value=highlighted.value if highlighted else "",
        highlight_ref=highlighted.ref if highlighted else "",
        insight_title=(
            (data.get("insight_title") or "").strip() or _DEFAULT_CANCER_INSIGHT_TITLE
        ),
        insight_lead=lead,
        insight_emphasis=emphasis,
        insight_tail=tail,
        markers=markers,
    )


_DEFAULT_BREAST_DETAIL: dict[str, Any] = {
    "id": "breast",
    "title": "Breast Cancer Screening",
    "what_title": "What is Breast cancer?",
    "what_text": (
        "It is a disease in which abnormal cells in the breast grow uncontrollably "
        "and form a malignant tumor. These cancer cells can invade nearby tissues "
        "and, in some cases, spread to other parts of the body through the blood."
    ),
    "insights_title": "Actionable Insights for your health",
    "insights": [
        "Prioritize vegetables, fruits, whole grains, legumes, nuts and other nutrient-dense foods.",
        "Reduce prolonged sitting and incorporate movement into your routine.",
        (
            "Know your normal breast health : Report a new lump, unusual nipple "
            "discharge, skin changes or other persistent breast changes to a "
            "healthcare professional."
        ),
    ],
    "influences_title": "What may influence Breast Cancer?",
    "influences": [
        "Benign Breast Conditions like Fibroadenoma or Cysts",
        "Hormonal Factors",
    ],
    "followup_title": "Recommended Follow-up",
    "followup": [
        {
            "id": "oncology",
            "title": "Oncology follow-up",
            "body": "Review symptoms & treatment",
            "icon": "oncology",
        },
        {
            "id": "imaging",
            "title": "Breast Imaging",
            "body": "Mammogram or ultrasound",
            "icon": "imaging",
        },
        {
            "id": "clinical",
            "title": "Clinical Evaluation",
            "body": "Breast & lymph-node check",
            "icon": "clinic",
        },
        {
            "id": "diagnostic",
            "title": "Diagnostic Imaging",
            "body": "MRI if needed",
            "icon": "diagnosis",
        },
        {
            "id": "tests",
            "title": "Additional Tests",
            "body": "Biopsy or blood tests if needed",
            "icon": "labs",
        },
    ],
}
_DEFAULT_OVARIAN_DETAIL: dict[str, Any] = {
    "id": "ovarian",
    "title": "Ovarian Cancer Screening",
    "what_title": "What is Ovarian cancer?",
    "what_text": (
        "A cancer that begins when abnormal cells in the ovaries grow and divide "
        "uncontrollably, potentially invading nearby tissues or spreading to other "
        "parts of the body."
    ),
    "insights_title": "Actionable Insights for your health",
    "insights": [
        "Maintain a balanced diet rich in vegetables, fruits, whole grains and legumes.",
        (
            "Pay attention to persistent bloating, pelvic or abdominal discomfort, "
            "or changes in bowel or bladder habits."
        ),
        (
            "Discuss persistent or unusual symptoms with a healthcare professional "
            "for appropriate evaluation."
        ),
    ],
    "influences_title": "What may influence Ovarian Cancer?",
    "influences": ["Endometriosis", "Ovarian Cysts", "Pelvic Infections"],
    "followup_title": "Recommended Follow-up",
    "followup": [
        {
            "id": "gynecological",
            "title": "Gynecological Follow-up",
            "body": "Review symptoms, history & risk factors",
            "icon": "oncology",
        },
        {
            "id": "pelvic_exam",
            "title": "Pelvic Examination",
            "body": "Clinical evaluation of pelvic health",
            "icon": "imaging",
        },
        {
            "id": "ultrasound",
            "title": "Pelvic Ultrasound",
            "body": "Transvaginal or abdominal ultrasound",
            "icon": "clinic",
        },
        {
            "id": "diagnostic",
            "title": "Diagnostic Imaging",
            "body": "CT/MRI if clinically indicated",
            "icon": "diagnosis",
        },
        {
            "id": "tests",
            "title": "Additional Tests",
            "body": "Biopsy or blood tests if needed",
            "icon": "labs",
        },
    ],
}
_DEFAULT_PANCREATIC_DETAIL: dict[str, Any] = {
    "id": "pancreatic",
    "title": "Pancreatic Cancer Screening",
    "what_title": "What is Pancreatic cancer?",
    "what_text": (
        "A cancer that begins when abnormal cells in the pancreas grow and divide "
        "uncontrollably, potentially invading nearby tissues or spreading to other "
        "parts of the body."
    ),
    "insights_title": "Actionable Insights for your health",
    "insights": [
        "Maintain a balanced diet rich in vegetables, fruits, whole grains and legumes.",
        "Stay physically active and maintain a healthy weight.",
        (
            "Discuss persistent abdominal or back pain, unexplained weight loss, "
            "jaundice or digestive changes with a healthcare professional."
        ),
    ],
    "influences_title": "What may influence Pancreatic Cancer?",
    "influences": [
        "Pancreatic Inflammation",
        "Gallstones & Bile Duct Conditions",
        "Pancreatitis",
        "Individual Variation",
    ],
    "followup_title": "Recommended Follow-up",
    "followup": [
        {
            "id": "gi",
            "title": "GI Follow-up",
            "body": "Review symptoms & medical history",
            "icon": "oncology",
        },
        {
            "id": "pancreatic_imaging",
            "title": "Pancreatic Imaging",
            "body": "CT or MRI if indicated",
            "icon": "imaging",
        },
        {
            "id": "clinical",
            "title": "Clinical Evaluation",
            "body": "Abdominal & general examination",
            "icon": "clinic",
        },
        {
            "id": "specialist",
            "title": "Specialist Imaging",
            "body": "MRCP or EUS if needed",
            "icon": "diagnosis",
        },
        {
            "id": "tests",
            "title": "Additional Tests",
            "body": "Biopsy or blood tests if needed",
            "icon": "labs",
        },
    ],
}
_DEFAULT_FEMALE_CANCER_DETAILS: tuple[dict[str, Any], ...] = (
    _DEFAULT_BREAST_DETAIL,
    _DEFAULT_OVARIAN_DETAIL,
    _DEFAULT_PANCREATIC_DETAIL,
)
_CANCER_DETAIL_NODE_IDS = {
    "breast": "747:6246",
    "ovarian": "747:6035",
    "pancreatic": "747:6162",
}
_DEFAULT_DETAILS_BY_ID = {
    "breast": _DEFAULT_BREAST_DETAIL,
    "ovarian": _DEFAULT_OVARIAN_DETAIL,
    "pancreatic": _DEFAULT_PANCREATIC_DETAIL,
}
_FOLLOWUP_ICON_ALIASES = {
    "oncology": "oncology",
    "ribbon": "oncology",
    "gynecological": "oncology",
    "gyne": "oncology",
    "gi": "oncology",
    "imaging": "imaging",
    "breast_imaging": "imaging",
    "mammogram": "imaging",
    "mri": "imaging",
    "clinic": "clinic",
    "clinical": "clinic",
    "evaluation": "clinic",
    "ultrasound": "clinic",
    "pelvic": "imaging",
    "examination": "imaging",
    "diagnosis": "diagnosis",
    "diagnostic": "diagnosis",
    "search": "diagnosis",
    "specialist": "diagnosis",
    "labs": "labs",
    "tests": "labs",
    "additional": "labs",
    "biopsy": "labs",
}


_FOLLOWUP_ICON_KEYS = {"oncology", "imaging", "clinic", "diagnosis", "labs"}


def _followup_icon_key(card_id: str, title: str, icon: str) -> str:
    explicit = (icon or "").strip().lower()
    if explicit in _FOLLOWUP_ICON_KEYS:
        return explicit
    raw = (icon or card_id or title or "").strip().lower().replace(" ", "_")
    compact = raw.replace("-", "_")
    for alias, key in sorted(
        _FOLLOWUP_ICON_ALIASES.items(), key=lambda item: len(item[0]), reverse=True
    ):
        if alias in compact:
            return key
    return "oncology"


def _cancer_details_from_report(
    report: BioReport, *, variant: str, first_page_no: int
) -> list[CancerDetailVM]:
    section = report.cancer
    if section is None or variant != "female":
        return []
    data = _cancer_payload_dict(section)
    raw_details = data.get("details") or data.get("conditions") or []
    if not raw_details:
        extras: list[Any] = []
        if isinstance(data.get("breast"), dict):
            extras.append(data["breast"])
        if isinstance(data.get("ovarian"), dict):
            extras.append(data["ovarian"])
        if isinstance(data.get("pancreatic"), dict):
            extras.append(data["pancreatic"])
        raw_details = extras
    parsed: list[CancerDetail] = []
    for item in raw_details:
        if isinstance(item, CancerDetail):
            parsed.append(item)
        elif isinstance(item, dict):
            try:
                parsed.append(CancerDetail.model_validate(item))
            except Exception:  # noqa: BLE001
                continue
    if not parsed:
        parsed = [
            CancerDetail.model_validate(item) for item in _DEFAULT_FEMALE_CANCER_DETAILS
        ]

    pages: list[CancerDetailVM] = []
    for index, item in enumerate(parsed):
        detail_id = (item.id or "").strip().lower() or "breast"
        catalog = _DEFAULT_DETAILS_BY_ID.get(detail_id, _DEFAULT_BREAST_DETAIL)
        followup: list[CancerFollowupVM] = []
        for card_index, card in enumerate(item.followup):
            if isinstance(card, CancerFollowupCard):
                row = card
            elif isinstance(card, dict) and card.get("title"):
                try:
                    row = CancerFollowupCard.model_validate(card)
                except Exception:  # noqa: BLE001
                    continue
            else:
                continue
            icon = _followup_icon_key(row.id, row.title, row.icon)
            followup.append(
                CancerFollowupVM(
                    key=(row.id or icon).strip().lower() or icon,
                    title=row.title,
                    body=row.body,
                    icon=icon,
                    tone="pink" if card_index % 2 == 0 else "teal",
                )
            )
        if not followup:
            followup = [
                CancerFollowupVM(
                    key=str(card["id"]),
                    title=str(card["title"]),
                    body=str(card["body"]),
                    icon=str(card["icon"]),
                    tone="pink" if i % 2 == 0 else "teal",
                )
                for i, card in enumerate(catalog["followup"])
            ]
        pages.append(
            CancerDetailVM(
                page_no=first_page_no + index,
                node_id=_CANCER_DETAIL_NODE_IDS.get(detail_id, "747:6246"),
                detail_id=detail_id,
                title=(item.title or "").strip() or str(catalog["title"]),
                what_title=(item.what_title or "").strip() or str(catalog["what_title"]),
                what_text=(item.what_text or "").strip() or str(catalog["what_text"]),
                insights_title=(item.insights_title or "").strip()
                or str(catalog["insights_title"]),
                insights=list(item.insights) or list(catalog["insights"]),
                influences_title=(item.influences_title or "").strip()
                or str(catalog["influences_title"]),
                influences=list(item.influences) or list(catalog["influences"]),
                followup_title=(item.followup_title or "").strip()
                or str(catalog["followup_title"]),
                followup=followup,
            )
        )
    return pages


def build_pdf_view_model(report: BioReport) -> PdfViewModel:
    """Assemble gender-aware PDF view-model and validate against BioReport."""
    patient = report.patient
    variant = resolve_gender_variant(patient.gender, patient.sex)
    by_id = _section_map(report)
    order = disease_order_for_variant(variant)
    index_order = index_order_for_variant(variant)

    disease_pages = [
        _card_from_section(by_id[disease_id], disease_id=disease_id)
        for disease_id in order
        if disease_id in by_id
    ]

    glance = list(disease_pages)

    # Catalog page lists the variant's full covered set (Figma timeline), not only scored ones.
    index_diseases: list[dict[str, Any]] = []
    for disease_id in index_order:
        title = pdf_config.DISEASE_DISPLAY_NAMES.get(disease_id)
        if title is None and disease_id in by_id:
            title = by_id[disease_id].title
        if not title:
            continue
        index_diseases.append({"disease_id": disease_id, "title": title})

    allowed_ids = set(order)
    top_risks: list[DiseaseCardVM] = []
    for highlight in report.executive_summary.top_disease_risks:
        highlight_id = canonicalize_disease_id(highlight.disease_id)
        if highlight_id not in allowed_ids:
            continue
        section = by_id.get(highlight_id)
        if section is None:
            continue
        insights = list(highlight.insights) if highlight.insights else []
        if not insights:
            insights = list(
                list(section.lifestyle.tips)
                + list(section.nutrition.recommendations)
                + list(section.lifestyle.exercise)
            )[: engine_config.TOP_INSIGHTS_PER_RISK]
        card = _card_from_section(section, disease_id=highlight_id, insights=insights)
        # Prefer highlight percentile when present.
        if highlight.percentile is not None:
            card.percentile = highlight.percentile
            card.percentile_label = _ordinal(highlight.percentile)
        top_risks.append(card)

    gender_label = (patient.gender or patient.sex or "—").strip()
    if gender_label and gender_label != "—":
        gender_label = gender_label[:1].upper() + gender_label[1:].lower()

    trend_series = _trend_series_from_report(report, variant=variant)
    has_trends = bool(trend_series)
    # Figma 373:97792 — up to 6 chart cards per page
    charts_per_page = 6
    trend_chart_pages = (
        (len(trend_series) + charts_per_page - 1) // charts_per_page if has_trends else 0
    )
    # Divider (1) + chart pages when trends exist
    trend_extra = (1 + trend_chart_pages) if has_trends else 0
    has_allergy = report.allergy is not None
    has_cancer = report.cancer is not None
    has_allergy_cancer = has_allergy or has_cancer
    allergy_page_no = (8 + len(disease_pages) + 2) if has_allergy else 0
    breakdown_first_page_no = (8 + len(disease_pages) + 3) if has_allergy else 0
    allergy_vm = (
        _allergy_overview_from_report(report, page_no=allergy_page_no)
        if has_allergy
        else None
    )
    allergy_breakdown_pages = (
        _allergy_breakdown_pages_from_report(report, first_page_no=breakdown_first_page_no)
        if has_allergy
        else []
    )
    insights_page_no = (
        breakdown_first_page_no + len(allergy_breakdown_pages) if has_allergy else 0
    )
    allergy_insights_vm = (
        _allergy_insights_from_report(report, page_no=insights_page_no)
        if has_allergy
        else None
    )
    # Combined divider + allergy pages + Cancer Screening Overview + female detail.
    screening_page_no = (
        8
        + len(disease_pages)
        + (1 if has_allergy_cancer else 0)
        + (1 if has_allergy else 0)
        + len(allergy_breakdown_pages)
        + (1 if allergy_insights_vm else 0)
        + (1 if has_cancer else 0)
        + 1
    )
    cancer_screening_vm = (
        _cancer_screening_from_report(
            report, variant=variant, page_no=screening_page_no
        )
        if has_cancer
        else None
    )
    detail_first_page_no = screening_page_no + (1 if cancer_screening_vm else 0)
    cancer_detail_pages = (
        _cancer_details_from_report(
            report, variant=variant, first_page_no=detail_first_page_no
        )
        if has_cancer
        else []
    )
    allergy_cancer_extra = (
        (1 if has_allergy_cancer else 0)
        + (1 if has_allergy else 0)
        + len(allergy_breakdown_pages)
        + (1 if allergy_insights_vm else 0)
        + (1 if has_cancer else 0)
        + (1 if cancer_screening_vm else 0)
        + len(cancer_detail_pages)
    )
    allergy_breakdown_vm = allergy_breakdown_pages[0] if allergy_breakdown_pages else None

    # Front matter: cover, welcome, TOC, index, health, glance, risks, divider (8),
    # then disease details, optional allergy/cancer, optional Health Trends, then back cover.
    page_count = 8 + len(disease_pages) + allergy_cancer_extra + trend_extra + 1
    disease_start = 9
    disease_end = 8 + len(disease_pages)
    allergy_cancer_start = disease_end + 1 if has_allergy_cancer else 0
    allergy_cancer_end = disease_end + allergy_cancer_extra if has_allergy_cancer else 0
    allergy_cancer_range = (
        f"{allergy_cancer_start}"
        if allergy_cancer_start == allergy_cancer_end
        else f"{allergy_cancer_start}-{allergy_cancer_end}"
    )
    trends_start = (disease_end + allergy_cancer_extra + 1) if has_trends else 0
    trends_end = (disease_end + allergy_cancer_extra + trend_extra) if has_trends else 0
    trends_range = (
        f"{trends_start}"
        if trends_start == trends_end
        else f"{trends_start}-{trends_end}"
    )

    if variant == "female":
        tests1 = pdf_config.TESTS_COVERED_FEMALE_PAGE1
        tests2 = pdf_config.TESTS_COVERED_FEMALE_PAGE2
    else:
        tests1 = pdf_config.TESTS_COVERED_MALE_PAGE1
        tests2 = pdf_config.TESTS_COVERED_MALE_PAGE2

    vm = PdfViewModel(
        variant=variant,
        honorific=honorific_for_variant(variant),
        page_count=page_count,
        disease_page_range=f"{disease_start}-{disease_end}",
        patient_name=_blank(patient.name),
        patient_age=_format_age(patient.age),
        patient_gender=_blank(gender_label),
        assessment_date=_format_assessment_date(patient.assessment_date),
        metabolic_score=_blank(patient.metabolic_score),
        metabolic_age=_blank(patient.metabolic_age),
        overall_status=_blank(patient.metabolic_health_status),
        bmi=_blank(patient.bmi),
        height=_blank(patient.height),
        weight=_blank(patient.weight),
        record_id=_blank(report.report_metadata.record_id or patient.record_id),
        index_diseases=index_diseases,
        glance_diseases=glance,
        top_risks=top_risks,
        disease_pages=disease_pages,
        tests_page1=tests1,
        tests_page2=tests2,
        template_version=pdf_config.PDF_TEMPLATE_VERSION,
        engine_version=report.report_metadata.engine_version,
        generated_at=report.report_metadata.generated_at,
        risk_bands=[
            {"label": name, "lo": lo, "hi": hi, "color": color}
            for name, lo, hi, color in pdf_config.RISK_BANDS
        ],
        lifestyle_levels=list(pdf_config.LIFESTYLE_METER_LEVELS),
        has_health_trends=has_trends,
        health_trend_series=trend_series,
        health_trends_page_range=trends_range,
        health_trends_chart_page_count=trend_chart_pages,
        has_allergy_cancer=has_allergy_cancer,
        has_allergy=has_allergy,
        has_cancer=has_cancer,
        allergy_cancer_page_range=allergy_cancer_range,
        allergy_cancer_page_count=allergy_cancer_extra,
        allergy=allergy_vm,
        allergy_breakdown=allergy_breakdown_vm,
        allergy_breakdown_pages=allergy_breakdown_pages,
        allergy_insights=allergy_insights_vm,
        cancer_screening=cancer_screening_vm,
        cancer_details=cancer_detail_pages,
    )
    validate_view_model(report, vm)
    return vm
