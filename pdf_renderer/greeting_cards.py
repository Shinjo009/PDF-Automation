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

# Figma groups 864:14085 / 864:14037 / 856:12325. Print at 7.5×5 in.
CARD_PAGE_WIDTH = "7.5in"
CARD_PAGE_HEIGHT = "5in"
_PAGE_CSS_WIDTH = 720  # 7.5in at 96px/in
_PAGE_CSS_HEIGHT = 480  # 5in at 96px/in

# Pixel layout from the Figma card groups (background + text overlay).
_LAYOUTS = {
    "gift": {
        "width": 396,
        "height": 254,
        "greeting": "THANK YOU",
        "copy_left": 37,
        "copy_top": 13,
        "copy_width": 338,
        "header_width": 338,
        "body_width": 270,
        "body_height": 168,
    },
    "birthday": {
        "width": 400,
        "height": 267,
        "greeting": "MANY HAPPY RETURNS",
        "copy_left": 28,
        "copy_top": 21,
        "copy_width": 310,
        "header_width": 288,
        "body_width": 210,
        "body_height": 168,
    },
    "diwali": {
        "width": 391,
        "height": 260,
        "greeting": "SHUBH DEEPAVALI",
        "copy_left": 28,
        "copy_top": 15,
        "copy_width": 310,
        "header_width": 310,
        "body_width": 205,
        "body_height": 168,
    },
}


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


def _card_asset_uri(name: str) -> str:
    path = _STATIC_DIR / "assets" / "greeting_cards" / name
    if not path.is_file():
        raise PdfValidationError(f"Missing greeting-card asset: {name}")
    return path.resolve().as_uri()


def card_background_uri(card_type: str) -> str:
    return _card_asset_uri(f"{card_type}.png")


def _for_label(relation: str) -> str:
    text = (relation or "").strip()
    if text.upper().startswith("FOR "):
        return text.upper()
    return f"FOR {text.upper()}"


def build_card_html(card: dict[str, str]) -> str:
    card_type = card["card_type"]
    layout = _LAYOUTS[card_type]
    scale = min(_PAGE_CSS_WIDTH / layout["width"], _PAGE_CSS_HEIGHT / layout["height"])
    bg = card_background_uri(card_type)
    logo_ring = _card_asset_uri("logo_ring.svg")
    logo_ring2 = _card_asset_uri("logo_ring2.svg")
    logo_word = _card_asset_uri("logo_word.svg")
    logo_mark = _card_asset_uri("logo_mark.svg")
    title = html.escape(card["title"])
    receiver = html.escape(card["receiver_name"])
    sender = html.escape(card["sender_name"])
    greeting = html.escape(layout["greeting"])
    for_label = html.escape(_for_label(card["relation"]))
    message = html.escape(card["message"]).replace("\n", "<br />")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:opsz,wght@9..40,400;9..40,700&family=Lato:wght@400&display=swap" rel="stylesheet" />
  <style>
    @page {{ size: {CARD_PAGE_WIDTH} {CARD_PAGE_HEIGHT}; margin: 0; }}
    html, body {{
      margin: 0;
      padding: 0;
      width: {CARD_PAGE_WIDTH};
      height: {CARD_PAGE_HEIGHT};
      overflow: hidden;
      background: #fffaf2;
    }}
    .stage {{
      width: {CARD_PAGE_WIDTH};
      height: {CARD_PAGE_HEIGHT};
      display: flex;
      align-items: center;
      justify-content: center;
    }}
    .card {{
      position: relative;
      width: {layout["width"]}px;
      height: {layout["height"]}px;
      transform: scale({scale:.4f});
      transform-origin: center center;
      overflow: hidden;
      border-radius: 20px;
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
      left: {layout["copy_left"]}px;
      top: {layout["copy_top"]}px;
      width: {layout["copy_width"]}px;
      z-index: 2;
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
    }}
    .card__header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: {layout["header_width"]}px;
    }}
    .card__logo {{
      position: relative;
      width: 37.143px;
      height: 37.048px;
      overflow: hidden;
      flex-shrink: 0;
    }}
    .card__logo img {{
      position: absolute;
      display: block;
    }}
    .card__logo-ring {{
      top: 0.26px;
      left: 0.23px;
    }}
    .card__logo-word {{
      top: 13.89px;
      left: 5.54px;
    }}
    .card__logo-mark {{
      top: 1.67px;
      left: 0.81px;
    }}
    .card__greeting {{
      margin: 0;
      padding: 10px;
      font-family: "DM Sans", "Helvetica Neue", sans-serif;
      font-size: 10px;
      font-weight: 400;
      font-variation-settings: "opsz" 14;
      letter-spacing: 4px;
      line-height: 30px;
      color: #720b0b;
      white-space: nowrap;
    }}
    .card__body {{
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      width: {layout["body_width"]}px;
      min-height: {layout["body_height"]}px;
    }}
    .card__top {{
      display: flex;
      flex-direction: column;
      align-items: flex-start;
    }}
    .card__for {{
      margin: 0;
      font-family: "DM Sans", "Helvetica Neue", sans-serif;
      font-size: 10px;
      font-weight: 700;
      font-variation-settings: "opsz" 14;
      letter-spacing: 2.5px;
      line-height: 30px;
      color: #720b0b;
      white-space: nowrap;
    }}
    .card__name {{
      margin: 0;
      font-family: "DM Sans", "Helvetica Neue", sans-serif;
      font-size: 30px;
      font-weight: 700;
      font-variation-settings: "opsz" 14;
      letter-spacing: 0.9px;
      line-height: 30px;
      color: #000000;
    }}
    .card__message {{
      margin: 0;
      font-family: "Lato", "Helvetica Neue", sans-serif;
      font-size: 15px;
      font-weight: 400;
      letter-spacing: 0.3px;
      line-height: 30px;
      color: #424242;
    }}
    .card__sender {{
      margin: 0;
      font-family: "Lato", "Helvetica Neue", sans-serif;
      font-size: 15px;
      font-weight: 400;
      letter-spacing: 0.3px;
      line-height: 30px;
      color: #424242;
    }}
  </style>
</head>
<body>
  <div class="stage">
    <section class="card card--{html.escape(card_type)}">
      <img class="card__bg" src="{bg}" alt="" />
      <div class="card__copy">
        <header class="card__header">
          <div class="card__logo" aria-hidden="true">
            <img class="card__logo-ring" src="{logo_ring}" alt="" />
            <img class="card__logo-word" src="{logo_word}" alt="" />
            <img class="card__logo-ring" src="{logo_ring2}" alt="" />
            <img class="card__logo-word" src="{logo_word}" alt="" />
            <img class="card__logo-mark" src="{logo_mark}" alt="" />
          </div>
          <p class="card__greeting">{greeting}</p>
        </header>
        <div class="card__body">
          <div class="card__top">
            <p class="card__for">{for_label}</p>
            <h1 class="card__name">{receiver}</h1>
            <p class="card__message">{message}</p>
          </div>
          <p class="card__sender">{sender}</p>
        </div>
      </div>
    </section>
  </div>
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
