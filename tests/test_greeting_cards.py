"""Greeting-card payload validation and occasion mapping."""

from __future__ import annotations

import pytest

from modules.bioai_report.pdf_renderer.exceptions import PdfValidationError
from modules.bioai_report.pdf_renderer.greeting_cards import (
    CARD_KIND,
    build_card_html,
    is_card_payload,
    normalize_card_type,
    validate_card_payload,
)

SAMPLE = {
    "sender_name": "Aanya",
    "receiver_name": "Rohan",
    "relation": "Sister",
    "message": "Wishing you a beautiful celebration.",
    "occasion": "birthday",
}


def test_validate_card_payload_normalizes_occasion():
    card = validate_card_payload({**SAMPLE, "occasion": "Deepavali"})
    assert card["kind"] == CARD_KIND
    assert card["card_type"] == "diwali"
    assert card["title"] == "Happy Diwali"
    assert card["sender_name"] == "Aanya"


@pytest.mark.parametrize(
    "occasion,expected",
    [
        ("gift", "gift"),
        ("Gift Card", "gift"),
        ("birthday", "birthday"),
        ("bday", "birthday"),
        ("diwali", "diwali"),
        ("deepavali", "diwali"),
    ],
)
def test_normalize_card_type(occasion: str, expected: str):
    assert normalize_card_type(occasion) == expected


def test_validate_card_payload_requires_fields():
    with pytest.raises(PdfValidationError, match="Missing required fields"):
        validate_card_payload({"sender_name": "Aanya", "occasion": "gift"})


def test_unknown_occasion_rejected():
    with pytest.raises(PdfValidationError, match="occasion must be one of"):
        validate_card_payload({**SAMPLE, "occasion": "holi"})


def test_build_card_html_uses_local_background():
    card = validate_card_payload(SAMPLE)
    html = build_card_html(card)
    assert "Dear Rohan" in html
    assert "Wishing you a beautiful celebration." in html
    assert "birthday.png" in html
    assert "figma.com" not in html


def test_is_card_payload():
    assert is_card_payload(validate_card_payload(SAMPLE))
    assert not is_card_payload({"patient": {"name": "X"}})


def test_accepts_name_sender_pdf_aliases():
    card = validate_card_payload(
        {
            "name": "Nigel Bedre",
            "relation": "Wifey",
            "pdf": "gift",
            "message": "Happy wedding anniversary honey",
            "sender": "Pratheek Nunes",
        }
    )
    assert card["receiver_name"] == "Nigel Bedre"
    assert card["sender_name"] == "Pratheek Nunes"
    assert card["card_type"] == "gift"
