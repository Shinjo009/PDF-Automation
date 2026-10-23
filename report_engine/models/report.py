"""BioReport JSON contract consumed by the PDF renderer.

Nested disease sections are render-ready PDF blocks. Upstream backends send
finished BioReport JSON; this package only validates and renders it.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


class AllergySection(BaseModel):
    """Optional allergy block. Presence of this object inserts allergy pages."""

    model_config = ConfigDict(extra="allow")


class CancerSection(BaseModel):
    """Optional cancer block. Presence of this object inserts cancer pages."""

    model_config = ConfigDict(extra="allow")


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
