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
        "body_width": 194,
        "name_width": 338,
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
        "body_width": 194,
        "name_width": 250,
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
        "body_width": 194,
        "name_width": 250,
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


def _print_layout(card_type: str) -> dict[str, float | str]:
    """Scale Figma px to print size. Avoid CSS transform:scale — Chromium
    PDF wraps text against the unscaled box and the printed card diverges
    from the website preview."""
    src = _LAYOUTS[card_type]
    scale = min(_PAGE_CSS_WIDTH / src["width"], _PAGE_CSS_HEIGHT / src["height"])
    return {
        "greeting": src["greeting"],
        "scale": scale,
        "width": src["width"] * scale,
        "height": src["height"] * scale,
        "radius": 20 * scale,
        "copy_left": src["copy_left"] * scale,
        "copy_top": src["copy_top"] * scale,
        "copy_width": src["copy_width"] * scale,
        "header_width": src["header_width"] * scale,
        "body_width": src["body_width"] * scale,
        "name_width": src["name_width"] * scale,
        "body_height": src["body_height"] * scale,
        "gap": 8 * scale,
        "logo": 37.143 * scale,
        "greeting_size": 10 * scale,
        "greeting_tracking": 4 * scale,
        "greeting_lh": 18 * scale,
        "for_size": 10 * scale,
        "for_tracking": 2.5 * scale,
        "for_lh": 18 * scale,
        "name_size": 30 * scale,
        "name_tracking": 0.9 * scale,
        "name_lh": 34 * scale,
        "msg_size": 15 * scale,
        "msg_tracking": 0.3 * scale,
        "msg_lh": 20 * scale,
    }


def build_card_html(card: dict[str, str]) -> str:
    card_type = card["card_type"]
    layout = _print_layout(card_type)
    bg = card_background_uri(card_type)
    logo_ring = _card_asset_uri("logo_ring.svg")
    logo_ring2 = _card_asset_uri("logo_ring2.svg")
    logo_word = _card_asset_uri("logo_word.svg")
    logo_mark = _card_asset_uri("logo_mark.svg")
    title = html.escape(card["title"])
    receiver = html.escape(card["receiver_name"])
    sender = html.escape(card["sender_name"])
    greeting = html.escape(str(layout["greeting"]))
    for_label = html.escape(_for_label(card["relation"]))
    message = html.escape(card["message"]).replace("\r\n", "\n").replace("\r", "\n")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{title}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;700&family=Lato:wght@400&display=swap" rel="stylesheet" />
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
      width: {layout["width"]:.2f}px;
      height: {layout["height"]:.2f}px;
      overflow: hidden;
      border-radius: {layout["radius"]:.2f}px;
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
      left: {layout["copy_left"]:.2f}px;
      top: {layout["copy_top"]:.2f}px;
      width: {layout["copy_width"]:.2f}px;
      z-index: 2;
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: {layout["gap"]:.2f}px;
    }}
    .card__header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      width: {layout["header_width"]:.2f}px;
    }}
    .card__logo {{
      width: {layout["logo"]:.2f}px;
      height: {layout["logo"]:.2f}px;
      overflow: hidden;
      flex-shrink: 0;
    }}
    .card__logo-inner {{
      position: relative;
      width: 37.143px;
      height: 37.048px;
      transform: scale({float(layout["logo"]) / 37.143:.4f});
      transform-origin: top left;
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
      font-family: "DM Sans", "Helvetica Neue", sans-serif;
      font-size: {layout["greeting_size"]:.2f}px;
      font-weight: 400;
      letter-spacing: {layout["greeting_tracking"]:.2f}px;
      line-height: {layout["greeting_lh"]:.2f}px;
      color: #720b0b;
      white-space: nowrap;
    }}
    .card__body {{
      display: flex;
      flex-direction: column;
      width: {layout["name_width"]:.2f}px;
      min-height: {layout["body_height"]:.2f}px;
    }}
    .card__top {{
      display: flex;
      flex-direction: column;
      align-items: flex-start;
    }}
    .card__for {{
      margin: 0;
      font-family: "DM Sans", "Helvetica Neue", sans-serif;
      font-size: {layout["for_size"]:.2f}px;
      font-weight: 700;
      letter-spacing: {layout["for_tracking"]:.2f}px;
      line-height: {layout["for_lh"]:.2f}px;
      color: #720b0b;
      white-space: nowrap;
    }}
    .card__name {{
      margin: 0;
      width: {layout["name_width"]:.2f}px;
      font-family: "DM Sans", "Helvetica Neue", sans-serif;
      font-size: {layout["name_size"]:.2f}px;
      font-weight: 700;
      letter-spacing: {layout["name_tracking"]:.2f}px;
      line-height: {layout["name_lh"]:.2f}px;
      color: #000000;
      white-space: nowrap;
    }}
    .card__message {{
      margin: 4px 0 0;
      width: {layout["body_width"]:.2f}px;
      font-family: "Lato", "Helvetica Neue", sans-serif;
      font-size: {layout["msg_size"]:.2f}px;
      font-weight: 400;
      letter-spacing: {layout["msg_tracking"]:.2f}px;
      line-height: {layout["msg_lh"]:.2f}px;
      color: #424242;
      white-space: pre-wrap;
      overflow-wrap: break-word;
      word-wrap: break-word;
    }}
    .card__sender {{
      margin: 0;
      padding-top: {layout["gap"]:.2f}px;
      margin-top: auto;
      font-family: "Lato", "Helvetica Neue", sans-serif;
      font-size: {layout["msg_size"]:.2f}px;
      font-weight: 400;
      letter-spacing: {layout["msg_tracking"]:.2f}px;
      line-height: {layout["msg_lh"]:.2f}px;
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
            <div class="card__logo-inner">
              <img class="card__logo-ring" src="{logo_ring}" alt="" />
              <img class="card__logo-word" src="{logo_word}" alt="" />
              <img class="card__logo-ring" src="{logo_ring2}" alt="" />
              <img class="card__logo-word" src="{logo_word}" alt="" />
              <img class="card__logo-mark" src="{logo_mark}" alt="" />
            </div>
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
