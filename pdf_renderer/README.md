# Bio-AI PDF Renderer

Figma-first HTML → PDF pipeline for finished BioReport JSON.

## Scope

This service does **not** fetch MetSights or assemble report content. The
upstream backend sends complete BioReport JSON; this package:

1. Validates JSON against `report_engine.models.report.BioReport`
2. Builds a gender-aware PDF view-model (`male` / `female`)
3. Renders Jinja HTML templates + SVG graphs to A4 pages
4. Prints PDF via Playwright/Chromium
5. Stores JSON + PDF once and serves a permanent link (`/r/{slug}`)

## Permanent link API

```bash
# Register (JSON from request payload → PDF once → permanent URL)
# CORS: https://api.supershyft.com
curl -X POST https://bio-ai-reports.supershyft.com/api/reports \
  -H "Content-Type: application/json" \
  -H "Origin: https://api.supershyft.com" \
  --data-binary @report.json

# Regenerate at an existing slug (archives prior JSON/PDF, same permanent URL)
curl -X POST https://bio-ai-reports.supershyft.com/api/reports/regenerate \
  -H "Content-Type: application/json" \
  --data-binary @report_with_slug.json

# Fetch stored PDF
# GET https://bio-ai-reports.supershyft.com/r/{slug}
```

Local server:

```bash
PYTHONPATH=. python test_engine/report_link_server.py
```

## Offline render

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements-pdf.txt
playwright install chromium

PYTHONPATH=. python test_engine/render_pdf.py test_engine/output_report_user1.json
PYTHONPATH=. python test_engine/render_pdf.py test_engine/output_report_user1.json --html-only
```

## Tests

```bash
PYTHONPATH=. pytest tests/test_pdf_mapping.py -v
```

## Layout source

- Slot inventory: `mapping/slot_inventory.yaml`
- Field matrix: `mapping/field_matrix.yaml`

## Optional Health Trends

When BioReport includes a non-empty `health_trends.series`, divider + chart
pages are inserted after Lifestyle Diseases Risk Analysis.

## Optional Allergy pages

When BioReport includes an `allergy` object, two pages are inserted after
Lifestyle Diseases Risk Analysis (before Health Trends):

1. Allergy / Cancer divider (Figma 747:1096)
2. Allergy Sensitivity Overview (Figma 747:5202) — IgE value, gauge, recommendation,
   ELISA summary counts, and detected-sensitivity rows all bind from JSON.
3. Detailed Allergy Breakdown (Figma 747:5335 / 747:5471) — normal-category
   cards from    `allergy.normal_categories` (name, status, items). First 8 cards
   on 747:5335, remaining on 747:5471. If omitted, the Figma ELISA panel is used.
4. Detailed Allergy Insights (Figma 747:5562) — clinical insights, recommendation
   cards, and interpretative notes from `allergy.insights`,
   `allergy.recommendations`, and `allergy.interpretative_notes`.

A `cancer` object inserts Cancer Screening Overview (Figma 747:5630) after the
allergy pages (or after the combined divider if there is no allergy). Detailed
Cancer Screening follows: female 747:5865 or male 741:881, with marker cards
from `cancer.markers` (gender-specific Figma defaults when omitted). Female
reports then add Breast (747:6246), Ovarian (747:6035), and Pancreatic
(747:6162) Cancer Screening pages from `cancer.details` (Figma female panels
when omitted).
`sensitivities` (or `items`) drives the allergy overview table; omit `allergy`
to skip allergy content pages.
