"""Greeting-card PDFs (gift / birthday / diwali) from a small JSON payload."""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import asyncio

from modules.bioai_report.pdf_renderer.exceptions import PdfValidationError

_PACKAGE_DIR = Path(__file__).resolve().parent
_STATIC_DIR = _PACKAGE_DIR / "static"

CARD_KIND = "greeting_card"
REQUIRED_FIELDS = ("sender_name", "receiver_name", "relation", "message", "occasion")

_OCCASION_ALIASES = {
    "gift": "gift",
    "gift card": "gift",
    "giftcard": "gift",
    "present": "gift",
    "birthday": "birthday",
    "bday": "birthday",
    "b-day": "birthday",
    "diwali": "diwali",
    "deepavali": "diwali",
    "deepawali": "diwali",
}

_TITLES = {
    "gift": "A Gift For You",
    "birthday": "Happy Birthday",
    "diwali": "Happy Diwali",
}

# Figma frames are landscape invitation cards (~400×260). Print at 7.5×5 in.
CARD_PAGE_WIDTH = "7.5in"
CARD_PAGE_HEIGHT = "5in"


def normalize_card_type(occasion: str) -> str:
    key = re.sub(r"\s+", " ", (occasion or "").strip().lower())
    card_type = _OCCASION_ALIASES.get(key)
    if not card_type:
        raise PdfValidationError(
            "occasion must be one of: gift, birthday, diwali "
            f"(got {occasion!r})"
        )
    return card_type


def _first_text(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = payload.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def validate_card_payload(payload: dict[str, Any]) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise PdfValidationError("JSON body must be an object")
    sender_name = _first_text(payload, "sender_name", "sender")
    receiver_name = _first_text(payload, "receiver_name", "receiver", "name")
    relation = _first_text(payload, "relation")
    message = _first_text(payload, "message")
    occasion = _first_text(payload, "occasion", "pdf", "card_type")
    missing = [
        label
        for label, value in (
            ("sender_name/sender", sender_name),
            ("receiver_name/name", receiver_name),
            ("relation", relation),
            ("message", message),
            ("occasion/pdf", occasion),
        )
        if not value
    ]
    if missing:
        raise PdfValidationError("Missing required fields: " + ", ".join(missing))
    card_type = normalize_card_type(occasion)
    return {
        "kind": CARD_KIND,
        "card_type": card_type,
        "sender_name": sender_name,
        "receiver_name": receiver_name,
        "relation": relation,
        "message": message,
        "occasion": occasion,
        "title": _TITLES[card_type],
    }


def is_card_payload(payload: dict[str, Any] | None) -> bool:
    return isinstance(payload, dict) and payload.get("kind") == CARD_KIND


def card_background_uri(card_type: str) -> str:
    path = _STATIC_DIR / "assets" / "greeting_cards" / f"{card_type}.png"
    if not path.is_file():
        raise PdfValidationError(f"Missing greeting-card background: {path.name}")
    return path.resolve().as_uri()


def build_card_html(card: dict[str, str]) -> str:
    bg = card_background_uri(card["card_type"])
    title = html.escape(card["title"])
    receiver = html.escape(card["receiver_name"])
    sender = html.escape(card["sender_name"])
    relation = html.escape(card["relation"])
    message = html.escape(card["message"]).replace("\n", "<br />")
    align = "center" if card["card_type"] == "gift" else "left"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=DM+Serif+Display:ital@0;1&family=Great+Vibes&display=swap" rel="stylesheet" />
  <style>
    @page {{ size: {CARD_PAGE_WIDTH} {CARD_PAGE_HEIGHT}; margin: 0; }}
    html, body {{
      margin: 0;
      padding: 0;
      width: {CARD_PAGE_WIDTH};
      height: {CARD_PAGE_HEIGHT};
      overflow: hidden;
      background: #f7f1e4;
    }}
    .card {{
      position: relative;
      width: {CARD_PAGE_WIDTH};
      height: {CARD_PAGE_HEIGHT};
      overflow: hidden;
      border-radius: 0;
    }}
    .card__bg {{
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }}
    .card__copy {{
      position: absolute;
      top: 50%;
      transform: translateY(-50%);
      z-index: 2;
      color: #3d2f1c;
      text-align: {align};
    }}
    .card--gift .card__copy {{
      left: 12%;
      right: 12%;
    }}
    .card--birthday .card__copy,
    .card--diwali .card__copy {{
      left: 8%;
      width: 48%;
    }}
    .card__kicker {{
      margin: 0 0 8px;
      font-family: "Cormorant Garamond", "Times New Roman", serif;
      font-size: 13px;
      letter-spacing: 0.28em;
      text-transform: uppercase;
      color: #8a7348;
    }}
    .card__title {{
      margin: 0 0 16px;
      font-family: "Great Vibes", "DM Serif Display", cursive;
      font-size: 46px;
      font-weight: 400;
      line-height: 1.05;
      color: #1f3a2e;
    }}
    .card--birthday .card__title,
    .card--diwali .card__title {{
      color: #6b4e16;
    }}
    .card__to {{
      margin: 0 0 12px;
      font-family: "Cormorant Garamond", "Times New Roman", serif;
      font-size: 18px;
      font-style: italic;
      color: #4a3b24;
    }}
    .card__message {{
      margin: 0 0 22px;
      font-family: "Cormorant Garamond", "Times New Roman", serif;
      font-size: 16px;
      line-height: 1.45;
      word-spacing: 0.06em;
      color: #3d2f1c;
    }}
    .card__from {{
      margin: 0;
      font-family: "DM Serif Display", "Times New Roman", serif;
      font-size: 18px;
      color: #1f3a2e;
    }}
    .card__relation {{
      margin: 4px 0 0;
      font-family: "Cormorant Garamond", "Times New Roman", serif;
      font-size: 13px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #8a7348;
    }}
  </style>
</head>
<body>
  <section class="card card--{html.escape(card['card_type'])}">
    <img class="card__bg" src="{bg}" alt="" />
    <div class="card__copy">
      <p class="card__kicker">{html.escape(card['card_type'])}</p>
      <h1 class="card__title">{title}</h1>
      <p class="card__to">Dear {receiver},</p>
      <p class="card__message">{message}</p>
      <p class="card__from">{sender}</p>
      <p class="card__relation">{relation}</p>
    </div>
  </section>
</body>
</html>
"""


def render_card_pdf(payload: dict[str, Any]) -> tuple[dict[str, str], bytes]:
    """Validate card JSON and return (normalized payload, PDF bytes)."""
    from modules.bioai_report.pdf_renderer.service import html_to_pdf_bytes

    card = validate_card_payload(payload)
    html_doc = build_card_html(card)
    pdf_bytes = asyncio.run(
        html_to_pdf_bytes(html_doc, width=CARD_PAGE_WIDTH, height=CARD_PAGE_HEIGHT)
    )
    return card, pdf_bytes
