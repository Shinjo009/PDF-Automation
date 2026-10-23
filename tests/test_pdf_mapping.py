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

    payload = sample_report.to_dict()
    payload["allergy"] = {"items": []}
    with_allergy = BioReport.model_validate(payload)
    vm_allergy = build_pdf_view_model(with_allergy)
    html_allergy = build_report_html(vm_allergy)
    assert vm_allergy.has_allergy_cancer is True
    assert vm_allergy.allergy_cancer_page_count == 1
    assert vm_allergy.page_count == vm.page_count + 1
    assert "AllergyCancerDivider" in html_allergy
    assert 'data-node-id="747:1096"' in html_allergy


def test_pdf_bytes_optional(user1_report: BioReport):
    """If Playwright+Chromium are available, PDF must start with %PDF."""
    pytest.importorskip("playwright")
    try:
        pdf = PdfRenderService().render_pdf(user1_report)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PDF render unavailable: {exc}")
    assert pdf[:4] == b"%PDF"
    assert len(pdf) > 1000
