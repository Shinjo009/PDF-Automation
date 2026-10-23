"""BioReport JSON contract consumed by the PDF renderer.

Nested disease sections are render-ready PDF blocks. Upstream backends send
finished BioReport JSON; this package only validates and renders it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PatientInfo(BaseModel):
    """Patient demographics and metabolic snapshot for the report."""

    model_config = ConfigDict(extra="ignore")

    record_id: str | None = None
    name: str | None = None
    age: float | int | None = None
    sex: str | None = None
    gender: str | None = None
    date_of_birth: str | None = None
    height: float | int | None = None
    weight: float | int | None = None
    bmi: float | int | None = None
    profile_id: str | None = None
    metabolic_age: float | int | None = None
    metabolic_score: float | int | None = None
    metabolic_health_status: str | None = None
    assessment_code: str | None = None
    assessment_date: str | None = None


class DiseaseHighlight(BaseModel):
    """Compact disease reference used in the executive summary / PDF page 10."""

    model_config = ConfigDict(extra="ignore")

    disease_id: str
    title: str
    score: int
    risk: str
    band: str
    percentile: float | int | None = None
    insights: list[str] = Field(default_factory=list)


class ExecutiveSummary(BaseModel):
    """Front-matter summary assembled before disease pages."""

    model_config = ConfigDict(extra="ignore")

    patient: PatientInfo
    assessment_date: str | None = None
    metabolic_score: float | int | None = None
    metabolic_age: float | int | None = None
    overall_status: str | None = None
    top_disease_risks: list[DiseaseHighlight] = Field(default_factory=list)
    top_health_strengths: list[DiseaseHighlight] = Field(default_factory=list)
    actionable_insights: list[str] = Field(default_factory=list)


class DiseaseCurrentStatus(BaseModel):
    """Score / risk block rendered at the top of a disease page."""

    model_config = ConfigDict(extra="ignore")

    score: int
    risk: str
    band: str
    percentile: float | int | None = None
    healthy_percentile: float | int | None = None
    lifestyle_contribution: float | int | None = None
    interpretation: str = ""
    clinical_warning: str = ""


class DiseaseLifestyle(BaseModel):
    """Lifestyle tips and exercise recommendations for a disease page."""

    model_config = ConfigDict(extra="ignore")

    tips: list[str] = Field(default_factory=list)
    exercise: list[str] = Field(default_factory=list)


class DiseaseNutrition(BaseModel):
    """Nutrition block for a disease page."""

    model_config = ConfigDict(extra="ignore")

    recommendations: list[str] = Field(default_factory=list)
    foods_to_include: list[str] = Field(default_factory=list)
    foods_to_avoid: list[str] = Field(default_factory=list)


class DiseaseMonitoring(BaseModel):
    """Monitoring recommendations for a disease page."""

    model_config = ConfigDict(extra="ignore")

    recommendations: list[str] = Field(default_factory=list)


class DiseaseSection(BaseModel):
    """Render-ready disease page — nested blocks match PDF sections."""

    model_config = ConfigDict(extra="ignore")

    disease_id: str
    title: str
    overview: str
    current_status: DiseaseCurrentStatus
    lifestyle: DiseaseLifestyle
    nutrition: DiseaseNutrition
    monitoring: DiseaseMonitoring
    positive_takeaway: str = ""
    contributing_factors: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_result_factors(cls, data: Any) -> Any:
        """Accept engine shape ``result_factors.factors`` as contributing_factors."""
        if not isinstance(data, dict):
            return data
        existing = data.get("contributing_factors")
        if isinstance(existing, list) and existing:
            return data
        result_factors = data.get("result_factors")
        if isinstance(result_factors, dict):
            factors = result_factors.get("factors")
            if isinstance(factors, list):
                data = {**data, "contributing_factors": factors}
        return data

    @property
    def score(self) -> int:
        """Convenience accessor used for sorting and executive-summary highlights."""
        return self.current_status.score

    @property
    def risk(self) -> str:
        return self.current_status.risk

    @property
    def band(self) -> str:
        return self.current_status.band


class ReportMetadata(BaseModel):
    """Engine provenance for the assembled report."""

    model_config = ConfigDict(extra="ignore")

    record_id: str
    engine_version: str
    kb_version: str | None = None
    template_version: str
    generated_at: str | None = None
    disease_count: int = 0
    source: str = "bioreport"


class TrendPoint(BaseModel):
    """One assessment point on a Health Trends chart."""

    model_config = ConfigDict(extra="ignore")

    date: str
    score: float | int


class TrendSeries(BaseModel):
    """Risk-score history for one disease / condition."""

    model_config = ConfigDict(extra="ignore")

    disease_id: str
    title: str | None = None
    points: list[TrendPoint] = Field(default_factory=list)


class HealthTrends(BaseModel):
    """Optional multi-assessment trends block for PDF Health Trends pages.

    When absent or ``series`` is empty, Health Trends pages are omitted.
    """

    model_config = ConfigDict(extra="ignore")

    series: list[TrendSeries] = Field(default_factory=list)


class AllergySensitivity(BaseModel):
    """One detected allergen row on the Allergy Sensitivity Overview page."""

    model_config = ConfigDict(extra="ignore")

    name: str
    category: str = ""
    value: float | str | None = None
    ref_range: str = "<0.35"
    risk: str = ""


class AllergyCategory(BaseModel):
    """One category card on Detailed Allergy Breakdown (Figma 747:5335)."""

    model_config = ConfigDict(extra="ignore")

    name: str
    id: str = ""
    status: str = "Normal"
    items: list[str] = Field(default_factory=list)

    @field_validator("items", mode="before")
    @classmethod
    def _coerce_items(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.replace(";", ",").split(",") if part.strip()]
        if isinstance(value, list):
            out: list[str] = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    out.append(item.strip())
                elif isinstance(item, dict) and item.get("name"):
                    out.append(str(item["name"]).strip())
            return out
        return []


class AllergyInsight(BaseModel):
    """One clinical-insight paragraph on Detailed Allergy Insights."""

    model_config = ConfigDict(extra="ignore")

    name: str
    text: str = ""

    @model_validator(mode="before")
    @classmethod
    def _alias_text(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data.get("text"):
            data = dict(data)
            data["text"] = data.get("insight") or data.get("description") or ""
        return data


class AllergyRecommendationCard(BaseModel):
    """One recommendation tile on Detailed Allergy Insights."""

    model_config = ConfigDict(extra="ignore")

    title: str
    body: str = ""


class AllergyNote(BaseModel):
    """One interpretative note on Detailed Allergy Insights."""

    model_config = ConfigDict(extra="ignore")

    title: str
    text: str = ""


class AllergySection(BaseModel):
    """Optional allergy block. Presence of this object inserts allergy pages."""

    model_config = ConfigDict(extra="allow")

    total_ige: float | None = None
    ige_unit: str = "IU/ml"
    ige_ref_low: float = 1.5
    ige_ref_high: float = 158.0
    ige_band: str | None = None
    recommendation: str | None = None
    ige_description: str | None = None
    total_allergens_tested: str | int | None = None
    sensitive_count: int | None = None
    normal_count: str | int | None = None
    sensitivities: list[AllergySensitivity] = Field(default_factory=list)
    normal_categories: list[AllergyCategory] = Field(default_factory=list)
    breakdown_subtitle: str | None = None
    breakdown_intro: str | None = None
    insights: list[AllergyInsight] = Field(default_factory=list)
    recommendations_title: str | None = None
    recommendations: list[AllergyRecommendationCard] = Field(default_factory=list)
    interpretative_notes: list[AllergyNote] = Field(default_factory=list)


class CancerMarker(BaseModel):
    """One cancer-marker card on Detailed Cancer Screening (female 747:5865)."""

    model_config = ConfigDict(extra="ignore")

    id: str = ""
    name: str
    marker: str = ""
    value: float | str | None = None
    unit: str = "ng/ml"
    ref: float | str | None = None
    status: str | None = None
    highlight: bool = False
    icon: str = ""

    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if not data.get("id"):
            data["id"] = data.get("marker_id") or data.get("key") or ""
        if data.get("ref") is None:
            data["ref"] = data.get("ref_range") or data.get("reference")
        if not data.get("marker"):
            data["marker"] = data.get("code") or data.get("test") or ""
        return data


class CancerFollowupCard(BaseModel):
    """One recommended-follow-up tile on a cancer detail page."""

    model_config = ConfigDict(extra="ignore")

    id: str = ""
    title: str
    body: str = ""
    icon: str = ""


class CancerDetail(BaseModel):
    """One condition page after Detailed Cancer Screening (female breast 747:6246)."""

    model_config = ConfigDict(extra="ignore")

    id: str = ""
    title: str = ""
    what_title: str = ""
    what_text: str = ""
    insights_title: str = ""
    insights: list[str] = Field(default_factory=list)
    influences_title: str = ""
    influences: list[str] = Field(default_factory=list)
    followup_title: str = ""
    followup: list[CancerFollowupCard] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if not data.get("what_text"):
            data["what_text"] = data.get("what_is") or data.get("description") or ""
        if not data.get("insights"):
            data["insights"] = data.get("actionable_insights") or data.get("tips") or []
        if not data.get("influences"):
            data["influences"] = data.get("factors") or data.get("chips") or []
        if not data.get("followup"):
            data["followup"] = data.get("follow_up") or data.get("recommendations") or []
        return data

    @field_validator("insights", "influences", mode="before")
    @classmethod
    def _coerce_strings(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split("\n") if part.strip()]
        if isinstance(value, list):
            out: list[str] = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    out.append(item.strip())
                elif isinstance(item, dict) and item.get("text"):
                    out.append(str(item["text"]).strip())
                elif isinstance(item, dict) and item.get("name"):
                    out.append(str(item["name"]).strip())
            return out
        return []


class CancerSection(BaseModel):
    """Optional cancer block. Presence of this object inserts cancer pages."""

    model_config = ConfigDict(extra="allow")

    what_is_cancer: str | None = None
    snapshot_title: str | None = None
    insight: str | None = None
    insight_title: str | None = None
    markers: list[CancerMarker] = Field(default_factory=list)
    details: list[CancerDetail] = Field(default_factory=list)


class BioReport(BaseModel):
    """Finished report JSON accepted by the PDF + permanent-link service."""

    model_config = ConfigDict(extra="ignore")

    patient: PatientInfo
    executive_summary: ExecutiveSummary
    disease_sections: list[DiseaseSection] = Field(default_factory=list)
    health_trends: HealthTrends | None = None
    allergy: AllergySection | None = None
    cancer: CancerSection | None = None
    report_metadata: ReportMetadata

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")
