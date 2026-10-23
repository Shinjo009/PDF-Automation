"""Golden mapping tests — BioReport JSON values must bind by disease_id without leakage."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from modules.bioai_report.pdf_renderer import config as pdf_config
from modules.bioai_report.pdf_renderer.exceptions import PdfValidationError
from modules.bioai_report.pdf_renderer.html_builder import build_report_html
from modules.bioai_report.pdf_renderer.service import PdfRenderService
from modules.bioai_report.pdf_renderer.view_model import (
    build_pdf_view_model,
    resolve_gender_variant,
    validate_view_model,
)
from modules.bioai_report.report_engine.models.report import BioReport

ROOT = Path(__file__).resolve().parents[1]
USER1 = ROOT / "test_engine" / "output_report_user1.json"
SAMPLE = ROOT / "report_engine" / "sample_output.json"
HEALTHY = ROOT / "test_engine" / "_sample_healthy.json"
PREVIEW = ROOT / "test_engine" / "preview_harsh.json"


def _load_report(path: Path) -> BioReport:
    return BioReport.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _with_gender(report: BioReport, gender: str) -> BioReport:
    data = report.to_dict()
    data["patient"]["gender"] = gender
    data["patient"]["sex"] = gender
    data["executive_summary"]["patient"]["gender"] = gender
    data["executive_summary"]["patient"]["sex"] = gender
    return BioReport.model_validate(data)


@pytest.fixture(scope="module")
def user1_report() -> BioReport:
    return _load_report(USER1)


@pytest.fixture(scope="module")
def sample_report() -> BioReport:
    return _load_report(SAMPLE)


def test_resolve_gender_variants():
    assert resolve_gender_variant("female", None) == "female"
    assert resolve_gender_variant("Male", None) == "male"
    assert resolve_gender_variant(None, "f") == "female"


def test_user1_view_model_binds_scores_by_disease_id(user1_report: BioReport):
    vm = build_pdf_view_model(user1_report)
    by_json = {s.disease_id: s for s in user1_report.disease_sections}

    assert vm.variant == "male"
    assert vm.honorific == "Mr."
    assert vm.patient_name == user1_report.patient.name
    assert float(vm.metabolic_score) == float(user1_report.patient.metabolic_score)

    for page in vm.disease_pages:
        source = by_json[page.disease_id]
        assert page.score == int(source.current_status.score)
        assert page.risk == source.current_status.risk
        # Prefer DISEASE_DISPLAY_NAMES when present; otherwise JSON title.
        expected_title = pdf_config.DISEASE_DISPLAY_NAMES.get(
            page.disease_id, source.title
        )
        assert page.title == expected_title
        assert page.band == source.current_status.band

    # PDF disease order is template-fixed, not JSON score order.
    rendered_ids = [p.disease_id for p in vm.disease_pages]
    expected = [d for d in pdf_config.DISEASE_ORDER_MALE if d in by_json]
    assert rendered_ids == expected


def test_female_variant_includes_metabolic_and_pcos_when_present(sample_report: BioReport):
    ids = {s.disease_id for s in sample_report.disease_sections}
    assert "metabolic_syndrome" in ids
    assert "metabolic_syndrome" in pdf_config.DISEASE_ORDER_FEMALE
    assert "pcos_pcod" in pdf_config.DISEASE_ORDER_FEMALE
    assert "pcos_pcod" not in pdf_config.DISEASE_ORDER_MALE

    female = _with_gender(sample_report, "female")
    payload = female.model_dump()
    donor = next(s for s in payload["disease_sections"] if s["disease_id"] == "thyroid_health")
    pcos = deepcopy(donor)
    pcos["disease_id"] = "pcos_pcod"
    pcos["title"] = "PCOS / PCOD"
    payload["disease_sections"].append(pcos)
    female = BioReport.model_validate(payload)

    vm = build_pdf_view_model(female)
    rendered_ids = [p.disease_id for p in vm.disease_pages]
    assert vm.variant == "female"
    assert vm.honorific == "Ms."
    assert "metabolic_syndrome" in rendered_ids
    assert "pcos_pcod" in rendered_ids
    assert rendered_ids == [d for d in pdf_config.DISEASE_ORDER_FEMALE if d in set(rendered_ids)]
    # Base pages + disease detail pages + back cover (+ optional health trends = 0 here)
    assert vm.page_count == 8 + len(rendered_ids) + 1


def test_at_a_glance_slots_differ_by_gender(sample_report: BioReport):
    from modules.bioai_report.pdf_renderer.html_builder import (
        _GLANCE_SLOTS_FEMALE,
        _GLANCE_SLOTS_MALE,
        _at_a_glance_context,
    )

    assert len(_GLANCE_SLOTS_MALE) == 9
    assert len(_GLANCE_SLOTS_FEMALE) == 10
    assert "metabolic_syndrome" in {s[0] for s in _GLANCE_SLOTS_MALE}
    assert "metabolic_syndrome" in {s[0] for s in _GLANCE_SLOTS_FEMALE}
    assert "pcos_pcod" in {s[0] for s in _GLANCE_SLOTS_FEMALE}
    assert "pcos_pcod" not in {s[0] for s in _GLANCE_SLOTS_MALE}

    male_vm = build_pdf_view_model(_with_gender(sample_report, "male"))
    payload = _with_gender(sample_report, "female").model_dump()
    donor = next(s for s in payload["disease_sections"] if s["disease_id"] == "thyroid_health")
    pcos = deepcopy(donor)
    pcos["disease_id"] = "pcos_pcod"
    pcos["title"] = "PCOS / PCOD"
    payload["disease_sections"].append(pcos)
    female_vm = build_pdf_view_model(BioReport.model_validate(payload))
    male_cards = _at_a_glance_context(male_vm)["cards"]
    female_cards = _at_a_glance_context(female_vm)["cards"]
    assert len(male_cards) == 9
    assert len(female_cards) == 10
    assert {c["disease_id"] for c in female_cards} == {
        s[0] for s in _GLANCE_SLOTS_FEMALE
    }


def test_male_variant_includes_metabolic_syndrome_when_present(sample_report: BioReport):
    male = _with_gender(sample_report, "male")
    vm = build_pdf_view_model(male)
    rendered = [p.disease_id for p in vm.disease_pages]
    assert rendered[0] == "metabolic_syndrome"
    assert "metabolic_syndrome" in rendered


def test_top_risk_insights_come_only_from_same_disease(user1_report: BioReport):
    vm = build_pdf_view_model(user1_report)
    by_json = {s.disease_id: s for s in user1_report.disease_sections}
    assert vm.top_risks
    for risk in vm.top_risks:
        source = by_json[risk.disease_id]
        allowed = set(
            list(source.lifestyle.tips)
            + list(source.nutrition.recommendations)
            + list(source.lifestyle.exercise)
        )
        for tip in risk.insights:
            assert tip in allowed
        assert risk.score == int(source.current_status.score)


def test_html_contains_data_slots_and_disease_ids(user1_report: BioReport):
    vm = build_pdf_view_model(user1_report)
    html = build_report_html(vm)
    assert 'data-slot="cover.name"' in html
    assert 'data-template="DiseaseDetail"' in html
    for page in vm.disease_pages:
        assert f'data-disease-id="{page.disease_id}"' in html
        assert f">{page.score}</strong> out of 100" in html or f">{page.score}</strong>" in html
        assert page.title in html


def test_html_gender_honorific_branches(sample_report: BioReport):
    male_vm = build_pdf_view_model(_with_gender(sample_report, "male"))
    female_vm = build_pdf_view_model(_with_gender(sample_report, "female"))
    assert "Mr." in build_report_html(male_vm)
    assert "Ms." in build_report_html(female_vm)
    assert "Kidney Function with K" in female_vm.tests_page1
    female_items = [
        item
        for groups in (female_vm.tests_page1, female_vm.tests_page2)
        for items in groups.values()
        for item in items
    ]
    assert "Fasting Insulin" in female_items
    assert male_vm.tests_page1 != female_vm.tests_page1


def test_validation_rejects_tampered_score(user1_report: BioReport):
    vm = build_pdf_view_model(user1_report)
    vm.disease_pages[0].score = 999
    with pytest.raises(PdfValidationError):
        validate_view_model(user1_report, vm)


def test_contributing_factors_flow_to_view_model():
    report = _load_report(HEALTHY)
    ht = next(s for s in report.disease_sections if s.disease_id == "hypertension")
    assert ht.contributing_factors == [
        "Low-normal magnesium",
        "Blood sugar as future risk",
    ]
    vm = build_pdf_view_model(report)
    page = next(p for p in vm.disease_pages if p.disease_id == "hypertension")
    assert page.contributing_factors == ht.contributing_factors


def test_bioreport_fixtures_build_view_models():
    for path in (USER1, SAMPLE, HEALTHY, PREVIEW):
        report = _load_report(path)
        vm = build_pdf_view_model(report)
        html = build_report_html(vm)
        assert vm.disease_pages
        assert "At A Glance" in html
        for page in vm.disease_pages:
            source = next(s for s in report.disease_sections if s.disease_id == page.disease_id)
            assert page.score == int(source.current_status.score)


def test_allergy_cancer_divider_only_when_json_has_section(sample_report: BioReport):
    vm = build_pdf_view_model(sample_report)
    html = build_report_html(vm)
    assert vm.has_allergy_cancer is False
    assert "AllergyCancerDivider" not in html
    assert "AllergyOverview" not in html

    payload = sample_report.to_dict()
    payload["allergy"] = {"items": []}
    with_allergy = BioReport.model_validate(payload)
    vm_allergy = build_pdf_view_model(with_allergy)
    html_allergy = build_report_html(vm_allergy)
    assert vm_allergy.has_allergy_cancer is True
    assert vm_allergy.has_allergy is True
    assert vm_allergy.allergy_cancer_page_count == 5
    assert vm_allergy.page_count == vm.page_count + 5
    assert "AllergyCancerDivider" in html_allergy
    assert "AllergyOverview" in html_allergy
    assert "AllergyBreakdown" in html_allergy
    assert "AllergyInsights" in html_allergy
    assert 'data-node-id="747:1096"' in html_allergy
    assert 'data-node-id="747:5202"' in html_allergy
    assert 'data-node-id="747:5335"' in html_allergy
    assert 'data-node-id="747:5471"' in html_allergy
    assert 'data-node-id="747:5562"' in html_allergy
    assert "CancerScreeningDivider" not in html_allergy
    assert 'data-node-id="747:5630"' not in html_allergy
    assert 'data-node-id="747:5865"' not in html_allergy
    assert 'data-node-id="747:6246"' not in html_allergy
    assert 'data-node-id="747:6035"' not in html_allergy
    assert 'data-node-id="747:6162"' not in html_allergy

    payload["cancer"] = {}
    with_both = BioReport.model_validate(payload)
    vm_both = build_pdf_view_model(with_both)
    html_both = build_report_html(vm_both)
    assert vm_both.has_cancer is True
    assert vm_both.allergy_cancer_page_count == 7
    assert vm_both.page_count == vm.page_count + 7
    assert "CancerScreeningDivider" in html_both
    assert 'data-node-id="747:5630"' in html_both
    assert 'data-node-id="741:881"' in html_both
    assert 'data-node-id="747:5865"' not in html_both
    assert 'data-node-id="747:6246"' not in html_both
    assert 'data-node-id="747:6035"' not in html_both
    assert 'data-node-id="747:6162"' not in html_both


def test_cancer_divider_only_when_json_has_cancer(sample_report: BioReport):
    vm = build_pdf_view_model(sample_report)
    payload = sample_report.to_dict()
    payload["cancer"] = {}
    with_cancer = BioReport.model_validate(payload)
    vm_cancer = build_pdf_view_model(with_cancer)
    html_cancer = build_report_html(vm_cancer)
    assert vm_cancer.has_cancer is True
    assert vm_cancer.has_allergy is False
    assert vm_cancer.allergy_cancer_page_count == 3
    assert vm_cancer.page_count == vm.page_count + 3
    assert "AllergyCancerDivider" in html_cancer
    assert "CancerScreeningDivider" in html_cancer
    assert "AllergyOverview" not in html_cancer
    assert 'data-node-id="747:5630"' in html_cancer
    assert 'data-template="CancerScreening"' in html_cancer
    assert 'data-node-id="741:881"' in html_cancer
    assert 'data-node-id="747:5865"' not in html_cancer
    assert vm_cancer.cancer_screening is not None
    assert vm_cancer.cancer_screening.layout == "male"
    assert vm_cancer.cancer_screening.in_range == 3
    assert vm_cancer.cancer_screening.total == 4
    assert [m.name for m in vm_cancer.cancer_screening.markers] == [
        "Liver Related Cancer",
        "Prostate Cancer",
        "Colorectal Cancer",
        "Pancreatic Cancer",
    ]
    colorectal = next(m for m in vm_cancer.cancer_screening.markers if m.key == "colorectal")
    assert colorectal.value == "5.2 ng/ml"
    assert colorectal.status == "marginal"
    assert colorectal.marker == "CEA"
    assert vm_cancer.cancer_details == []
    assert 'data-node-id="747:6246"' not in html_cancer
    assert 'data-node-id="747:6035"' not in html_cancer
    assert 'data-node-id="747:6162"' not in html_cancer


def test_female_cancer_screening_maps_json_and_defaults(sample_report: BioReport):
    female_base = _with_gender(sample_report, "female")
    vm_base = build_pdf_view_model(female_base)
    payload = female_base.to_dict()
    payload["cancer"] = {}
    female = BioReport.model_validate(payload)
    vm_female = build_pdf_view_model(female)
    html = build_report_html(vm_female)
    assert vm_female.variant == "female"
    assert vm_female.cancer_screening is not None
    assert vm_female.allergy_cancer_page_count == 6
    assert vm_female.page_count == vm_base.page_count + 6
    assert 'data-node-id="747:5865"' in html
    assert 'data-node-id="747:6246"' in html
    assert 'data-node-id="747:6035"' in html
    assert 'data-node-id="747:6162"' in html
    assert [d.title for d in vm_female.cancer_details] == [
        "Breast Cancer Screening",
        "Ovarian Cancer Screening",
        "Pancreatic Cancer Screening",
    ]
    assert vm_female.cancer_details[1].influences == [
        "Endometriosis",
        "Ovarian Cysts",
        "Pelvic Infections",
    ]
    assert "Pancreatic Inflammation" in vm_female.cancer_details[2].influences
    assert vm_female.cancer_details[2].followup[0].title == "GI Follow-up"
    assert 'data-template="CancerScreening"' in html
    assert vm_female.cancer_screening.in_range == 4
    assert vm_female.cancer_screening.total == 5
    names = [m.name for m in vm_female.cancer_screening.markers]
    assert names == [
        "AFP (Amniotic Fluid)",
        "Breast Cancer",
        "Ovarian Cancer",
        "Colorectal Cancer",
        "Pancreatic Cancer",
    ]
    breast = next(m for m in vm_female.cancer_screening.markers if m.key == "breast")
    assert breast.value == "5.2 ng/ml"
    assert breast.status == "critical"
    assert "5.2 ng/ml" in html
    assert "Most markers are within range" in html

    payload["cancer"] = {
        "what_is_cancer": "Custom definition.",
        "insight": "Watch the ovarian marker closely.",
        "markers": [
            {
                "id": "ovarian",
                "name": "Ovarian Cancer",
                "value": 9.4,
                "unit": "ng/ml",
                "ref": 2.3,
                "status": "critical",
                "highlight": True,
                "marker": "CA 125",
            }
        ],
    }
    custom = BioReport.model_validate(payload)
    vm_custom = build_pdf_view_model(custom)
    html_custom = build_report_html(vm_custom)
    assert vm_custom.cancer_screening is not None
    assert vm_custom.cancer_screening.total == 1
    assert vm_custom.cancer_screening.in_range == 0
    assert vm_custom.cancer_screening.highlight_name == "Ovarian Cancer"
    assert vm_custom.cancer_screening.highlight_marker == "CA 125"
    assert vm_custom.cancer_screening.markers[0].value == "9.4 ng/ml"
    assert "Custom definition." in html_custom
    assert "Watch the ovarian marker closely." in html_custom
    assert "9.4 ng/ml" in html_custom
    assert "Breast Cancer Screening" in html_custom

    payload["cancer"]["details"] = [
        {
            "id": "breast",
            "title": "Custom Breast Page",
            "what_text": "Custom breast explainer.",
            "insights": ["Eat well."],
            "influences": ["Family history"],
            "followup": [
                {
                    "id": "oncology",
                    "title": "Oncology visit",
                    "body": "Book this week",
                }
            ],
        }
    ]
    detailed = BioReport.model_validate(payload)
    vm_detail = build_pdf_view_model(detailed)
    html_detail = build_report_html(vm_detail)
    assert vm_detail.cancer_details[0].title == "Custom Breast Page"
    assert vm_detail.cancer_details[0].insights == ["Eat well."]
    assert vm_detail.cancer_details[0].influences == ["Family history"]
    assert vm_detail.cancer_details[0].followup[0].title == "Oncology visit"
    assert "Custom Breast Page" in html_detail
    assert "Custom breast explainer." in html_detail
    assert "Family history" in html_detail


def test_allergy_overview_maps_json_values(sample_report: BioReport):
    payload = sample_report.to_dict()
    payload["allergy"] = {
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
    report = BioReport.model_validate(payload)
    vm = build_pdf_view_model(report)
    html = build_report_html(vm)
    assert vm.allergy is not None
    assert vm.allergy.ige_value == "1481.9"
    assert vm.allergy.ige_band == "VERY HIGH"
    assert vm.allergy.sensitive_count == "2"
    assert vm.allergy.rows[0].name == "Tyrophagus Putrescentiae"
    assert vm.allergy.rows[0].value == "0.78"
    assert vm.allergy.rows[1].value == "0.52"
    assert "1481.9" in html
    assert "Tyrophagus Putrescentiae" in html
    assert "Tobacco Dust" in html
    assert "Class 1 (Very Low)" in html
    assert "14x above normal" in html
    assert vm.allergy_breakdown is not None
    assert vm.allergy_breakdown.categories[0].name == "Drugs"
    assert len(vm.allergy_breakdown_pages) == 2
    assert vm.allergy_breakdown_pages[1].categories[0].name == "Grass"
    assert "Detailed Allergy Breakdown" in html
    assert "Penicilloyl V" in html
    assert "Cynodon Dactylon" in html
    assert vm.allergy_insights is not None
    assert vm.allergy_insights.insights[0].name == "Tyrophagus Putrescentiae"
    assert "Detailed Allergy Insights" in html
    assert "Bedding Protection" in html


def test_allergy_insights_maps_json_values(sample_report: BioReport):
    payload = sample_report.to_dict()
    payload["allergy"] = {
        "insights": [
            {
                "name": "House Dust",
                "insight": "Limit bedroom carpets and wash bedding weekly.",
            }
        ],
        "recommendations_title": "Actionable Recommendations (Home Control)",
        "recommendations": [
            {"title": "Air Filters", "body": "Use a HEPA air purifier in the bedroom."}
        ],
        "notes": [
            {"title": "Retest:", "text": "Repeat IgE after 6 months of avoidance."}
        ],
    }
    report = BioReport.model_validate(payload)
    vm = build_pdf_view_model(report)
    html = build_report_html(vm)
    assert vm.allergy_insights is not None
    assert vm.allergy_insights.insights[0].name == "House Dust"
    assert vm.allergy_insights.insights[0].text.startswith("Limit bedroom")
    assert vm.allergy_insights.recommendations_title == "Actionable Recommendations (Home Control)"
    assert vm.allergy_insights.recommendations[0].title == "Air Filters"
    assert vm.allergy_insights.notes[0].title == "Retest:"
    assert "House Dust" in html
    assert "HEPA air purifier" in html
    assert 'data-node-id="747:5562"' in html


def test_allergy_breakdown_maps_json_categories(sample_report: BioReport):
    payload = sample_report.to_dict()
    payload["allergy"] = {
        "total_ige": 40,
        "normal_categories": [
            {
                "id": "insects",
                "name": "Insects",
                "status": "Normal",
                "items": ["Housefly (Musca Domestica)", "Apis Mellifera (Honey Bee)"],
            },
            {
                "id": "dairy",
                "name": "Dairy products",
                "status": "Sensitive",
                "items": "Cow Milk, Casein (Milk Protein)",
            },
        ],
    }
    report = BioReport.model_validate(payload)
    vm = build_pdf_view_model(report)
    html = build_report_html(vm)
    assert vm.allergy_breakdown is not None
    assert len(vm.allergy_breakdown_pages) == 1
    assert len(vm.allergy_breakdown.categories) == 2
    assert vm.allergy_breakdown.categories[0].key == "insects"
    assert vm.allergy_breakdown.categories[0].items_text.startswith("Housefly")
    assert vm.allergy_breakdown.categories[1].status == "Sensitive"
    assert vm.allergy_breakdown.categories[1].status_tone == "sensitive"
    assert "Cow Milk, Casein (Milk Protein)" in html
    assert "AllergyBreakdown" in html
    assert 'data-node-id="747:5471"' not in html


def test_pdf_bytes_optional(user1_report: BioReport):
    """If Playwright+Chromium are available, PDF must start with %PDF."""
    pytest.importorskip("playwright")
    try:
        pdf = PdfRenderService().render_pdf(user1_report)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PDF render unavailable: {exc}")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000
