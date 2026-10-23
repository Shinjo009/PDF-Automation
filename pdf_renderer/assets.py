"""Resolve static asset URLs for HTML/PDF rendering."""

from __future__ import annotations

from pathlib import Path

from modules.bioai_report.pdf_renderer import config as pdf_config


def _resolve(base_dir: Path, folder: str, name: str, *, for_http: bool, kind: str) -> str:
    path = base_dir / name
    if for_http:
        return f"/static/assets/{kind}/{folder}/{name}"
    return path.resolve().as_uri()


def cover_asset_urls(variant: str = "male", *, for_http: bool = False) -> dict[str, str]:
    """Return cover asset URLs for the given gender variant."""
    folder = "male" if variant != "female" else "male"  # female cover assets TBD
    base_dir = Path(pdf_config.STATIC_DIR) / "assets" / "cover" / folder

    def resolve(name: str) -> str:
        return _resolve(base_dir, folder, name, for_http=for_http, kind="cover")

    return {
        "cover_bg": resolve("green_bg.png"),
        "logo_group2": resolve("logo_group2.svg"),
        "logo_group3": resolve("logo_group3.svg"),
        "logo_group4": resolve("logo_group4.svg"),
        "logo_group5": resolve("logo_group5.svg"),
        "divider": resolve("divider.svg"),
    }


def welcome_asset_urls(variant: str = "male", *, for_http: bool = False) -> dict[str, str]:
    """Return welcome-page asset URLs for the given gender variant."""
    folder = "female" if variant == "female" else "male"
    base_dir = Path(pdf_config.STATIC_DIR) / "assets" / "welcome" / folder
    # Fall back to male shared chrome if a female file is missing.
    male_dir = Path(pdf_config.STATIC_DIR) / "assets" / "welcome" / "male"

    def resolve(name: str) -> str:
        path = base_dir / name
        use_folder = folder
        use_dir = base_dir
        if not path.exists():
            path = male_dir / name
            use_folder = "male"
            use_dir = male_dir
        return _resolve(use_dir, use_folder, name, for_http=for_http, kind="welcome")

    return {
        "welcome_bg": resolve("bg.png"),
        "welcome_hero": resolve("hero.png"),
        "welcome_metflux": resolve("metflux_logo.png"),
        "welcome_mark": resolve("metsights_mark.png"),
    }


def toc_asset_urls(*, for_http: bool = False) -> dict[str, str]:
    """Return Table of Contents page asset URLs."""
    folder = "toc"
    base_dir = Path(pdf_config.STATIC_DIR) / "assets" / folder

    def resolve(name: str) -> str:
        # toc assets live at /static/assets/toc/...
        path = base_dir / name
        if for_http:
            return f"/static/assets/toc/{name}"
        return path.resolve().as_uri()

    return {
        "toc_deco": resolve("deco_blob.svg"),
        "toc_title_line": resolve("title_line.svg"),
        "toc_row_line": resolve("row_line.svg"),
        "toc_footer_bg": resolve("footer_bg.svg"),
        "toc_footer_rule": resolve("footer_rule.svg"),
        "toc_metflux": resolve("metflux_logo.png"),
        "toc_mark": resolve("brand_mark.png"),
    }


def diseases_index_asset_urls(*, for_http: bool = False) -> dict[str, str]:
    """Return Lifestyle Diseases Covered page asset URLs."""
    base_dir = Path(pdf_config.STATIC_DIR) / "assets" / "diseases_index"

    def resolve(name: str) -> str:
        path = base_dir / name
        if for_http:
            return f"/static/assets/diseases_index/{name}"
        return path.resolve().as_uri()

    icon_ids = (
        "metabolic_syndrome",
        "dyslipidemia",
        "cardiac_health",
        "oxidative_stress",
        "nafld",
        "hypertension",
        "obesity",
        "thyroid_health",
        "type2_diabetes",
        "pcos_pcod",
    )
    icons = {f"icon_{disease_id}": resolve(f"icon_{disease_id}.png") for disease_id in icon_ids}
    # Inline SVG for PCOS — <img src=".svg"> is rasterized at 56px in Chromium PDF
    # and looks soft; inlined markup stays vector-sharp.
    out: dict[str, str] = {
        "ldi_deco": resolve("deco_blob.svg"),
        "ldi_title_line": resolve("title_line.svg"),
        "ldi_connector": resolve("connector.svg"),
        "ldi_footer_bg": resolve("footer_bg.svg"),
        "ldi_footer_rule": resolve("footer_rule.svg"),
        "ldi_metflux": resolve("metflux_logo.png"),
        "ldi_mark": resolve("brand_mark.png"),
        **icons,
    }
    pcos_svg = base_dir / "icon_pcos_pcod.svg"
    if pcos_svg.exists():
        markup = pcos_svg.read_text(encoding="utf-8")
        markup = markup.replace('width="64"', 'width="56"', 1).replace(
            'height="64"', 'height="56"', 1
        )
        out["icon_pcos_pcod_inline"] = markup
    return out


def health_summary_asset_urls(*, for_http: bool = False) -> dict[str, str]:
    """Return Your Health Summary page asset URLs."""
    base_dir = Path(pdf_config.STATIC_DIR) / "assets" / "health_summary"

    def resolve(name: str) -> str:
        path = base_dir / name
        if for_http:
            return f"/static/assets/health_summary/{name}"
        return path.resolve().as_uri()

    return {
        "hs_bg": resolve("bg.svg"),
        "hs_rings": resolve("rings.svg"),
        "hs_title_line": resolve("title_line.svg"),
        "hs_score_card": resolve("score_card.svg"),
        "hs_gauge": resolve("gauge.svg"),
        "hs_thumbs_down": resolve("thumbs_down.png"),
        "hs_thumbs_up": resolve("thumbs_up.png"),
        "hs_legend_healthy": resolve("legend_healthy.svg"),
        "hs_legend_increased": resolve("legend_increased.svg"),
        "hs_legend_high": resolve("legend_high.svg"),
        "hs_legend_very_high": resolve("legend_very_high.svg"),
        "hs_metflux": resolve("metflux_logo.png"),
        "hs_mark": resolve("brand_mark.png"),
    }


def risk_summary_asset_urls(*, for_http: bool = False) -> dict[str, str]:
    """Return Risk Summary & Actionable Insights page asset URLs."""
    base_dir = Path(pdf_config.STATIC_DIR) / "assets" / "risk_summary"

    def resolve(name: str) -> str:
        path = base_dir / name
        if for_http:
            return f"/static/assets/risk_summary/{name}"
        return path.resolve().as_uri()

    icon_ids = (
        "metabolic_syndrome",
        "dyslipidemia",
        "cardiac_health",
        "oxidative_stress",
        "nafld",
        "hypertension",
        "obesity",
        "thyroid_health",
        "type2_diabetes",
        "pcos_pcod",
    )
    icons = {f"rs_icon_{disease_id}": resolve(f"icon_{disease_id}.png") for disease_id in icon_ids}
    return {
        "rs_title_line": resolve("title_line.svg"),
        "rs_footer_bar": resolve("footer_bar.svg"),
        "rs_footer_rule": resolve("footer_rule.svg"),
        "rs_metflux": resolve("metflux_logo.png"),
        "rs_mark": resolve("brand_mark.png"),
        **icons,
    }


def at_a_glance_asset_urls(variant: str = "male", *, for_http: bool = False) -> dict[str, str]:
    """Return At A Glance page asset URLs (body scene is gender-specific)."""
    base_dir = Path(pdf_config.STATIC_DIR) / "assets" / "at_a_glance"

    def resolve(name: str) -> str:
        path = base_dir / name
        if for_http:
            return f"/static/assets/at_a_glance/{name}"
        return path.resolve().as_uri()

    icon_ids = (
        "metabolic_syndrome",
        "dyslipidemia",
        "cardiac_health",
        "oxidative_stress",
        "nafld",
        "hypertension",
        "obesity",
        "thyroid_health",
        "type2_diabetes",
        "pcos_pcod",
    )
    icons: dict[str, str] = {}
    for disease_id in icon_ids:
        svg = base_dir / f"icon_{disease_id}.svg"
        png = base_dir / f"icon_{disease_id}.png"
        if svg.exists():
            icons[f"aag_icon_{disease_id}"] = resolve(f"icon_{disease_id}.svg")
        elif png.exists():
            icons[f"aag_icon_{disease_id}"] = resolve(f"icon_{disease_id}.png")
        else:
            raise FileNotFoundError(f"Missing At A Glance icon for {disease_id}")
    scene_name = "scene_female.png" if variant == "female" else "scene.png"
    if not (base_dir / scene_name).exists():
        scene_name = "scene.png"
    return {
        "aag_scene": resolve(scene_name),
        "aag_title_line": resolve("title_line.svg"),
        "aag_legend_healthy": resolve("legend_healthy.svg"),
        "aag_legend_increased": resolve("legend_increased.svg"),
        "aag_legend_high": resolve("legend_high.svg"),
        "aag_legend_very_high": resolve("legend_very_high.svg"),
        "aag_metflux": resolve("metflux_logo.png"),
        "aag_mark": resolve("brand_mark.png"),
        "aag_cover_left": resolve("cover_left.png"),
        "aag_cover_right": resolve("cover_right.png"),
        "aag_cover_metabolic_syndrome": resolve("cover_metabolic_syndrome.png"),
        **icons,
    }


def disease_divider_asset_urls(*, for_http: bool = False) -> dict[str, str]:
    """Return Lifestyle Diseases Risk Analysis divider page asset URLs."""
    base_dir = Path(pdf_config.STATIC_DIR) / "assets" / "disease_divider"

    def resolve(name: str) -> str:
        path = base_dir / name
        if for_http:
            return f"/static/assets/disease_divider/{name}"
        return path.resolve().as_uri()

    return {
        "dd_bg": resolve("green_bg.png"),
        "dd_deco": resolve("deco.svg"),
        "dd_leaves": resolve("leaves.png"),
        "dd_metflux": resolve("metflux_logo.png"),
        "dd_mark": resolve("brand_mark.png"),
    }


def disease_detail_asset_urls(*, for_http: bool = False) -> dict[str, str]:
    """Return Disease Detail page asset URLs."""
    base_dir = Path(pdf_config.STATIC_DIR) / "assets" / "disease_detail"

    def resolve(name: str) -> str:
        path = base_dir / name
        if for_http:
            return f"/static/assets/disease_detail/{name}"
        return path.resolve().as_uri()

    icon_ids = (
        "metabolic_syndrome",
        "dyslipidemia",
        "cardiac_health",
        "oxidative_stress",
        "nafld",
        "hypertension",
        "obesity",
        "thyroid_health",
        "type2_diabetes",
        "pcos_pcod",
    )
    icons = {f"ddt_icon_{disease_id}": resolve(f"icon_{disease_id}.png") for disease_id in icon_ids}
    return {
        "ddt_title_line": resolve("title_line.svg"),
        "ddt_bullet": resolve("bullet.svg"),
        # PNG — Chromium PDF often fails to paint SVG linearGradients (green-only bar).
        "ddt_life_bar": resolve("life_bar_fill.png"),
        "ddt_life_track": resolve("life_bar_track.png"),
        "ddt_icon_lifestyle": resolve("icon_lifestyle.svg"),
        "ddt_icon_fitness": resolve("icon_fitness.svg"),
        "ddt_icon_nutrition": resolve("icon_nutrition.svg"),
        "ddt_legend_healthy": resolve("legend_healthy.svg"),
        "ddt_legend_increased": resolve("legend_increased.svg"),
        "ddt_legend_high": resolve("legend_high.svg"),
        "ddt_legend_very_high": resolve("legend_very_high.svg"),
        "ddt_footer_bar": resolve("footer_bar.svg"),
        "ddt_footer_rule": resolve("footer_rule.svg"),
        "ddt_metflux": resolve("metflux_logo.png"),
        "ddt_mark": resolve("brand_mark.png"),
        **icons,
    }


def back_cover_asset_urls(*, for_http: bool = False) -> dict[str, str]:
    """Return static back-cover asset URLs (same for every PDF)."""
    base_dir = Path(pdf_config.STATIC_DIR) / "assets" / "back_cover"

    def resolve(name: str) -> str:
        path = base_dir / name
        if for_http:
            return f"/static/assets/back_cover/{name}"
        return path.resolve().as_uri()

    return {
        "bc_bg": resolve("green_bg.png"),
        "bc_deco": resolve("deco.svg"),
        "bc_logo_group": resolve("logo_group.svg"),
        "bc_logo_ring": resolve("logo_ring.svg"),
        "bc_logo_inner": resolve("logo_inner.svg"),
        "bc_logo_text": resolve("logo_text.svg"),
        "bc_icon_web": resolve("icon_web.svg"),
        "bc_icon_phone": resolve("icon_phone.svg"),
        "bc_icon_email": resolve("icon_email.svg"),
        "bc_icon_linkedin": resolve("icon_linkedin.svg"),
        "bc_icon_instagram": resolve("icon_instagram.svg"),
        "bc_metflux": resolve("metflux_logo.png"),
        "bc_mark": resolve("brand_mark.png"),
    }


def allergy_cancer_asset_urls(*, for_http: bool = False) -> dict[str, str]:
    """Return optional allergy/cancer divider asset URLs (Figma 747:1096)."""
    base_dir = Path(pdf_config.STATIC_DIR) / "assets" / "allergy_cancer"

    def resolve(name: str) -> str:
        path = base_dir / name
        if for_http:
            return f"/static/assets/allergy_cancer/{name}"
        return path.resolve().as_uri()

    return {
        "ac_page_bg": resolve("page_bg.png"),
    }


def health_trends_asset_urls(*, for_http: bool = False) -> dict[str, str]:
    """Return Health Trends divider + chart page asset URLs (Figma 373:97955 / 373:97792)."""
    base_dir = Path(pdf_config.STATIC_DIR) / "assets" / "health_trends"

    def resolve(name: str) -> str:
        path = base_dir / name
        if for_http:
            return f"/static/assets/health_trends/{name}"
        return path.resolve().as_uri()

    return {
        "ht_bg": resolve("green_bg.png"),
        "ht_page_bg": resolve("page_bg.png"),
        "ht_deco": resolve("deco.svg"),
        "ht_circles": resolve("circles.png"),
        "ht_title_line": resolve("title_line.svg"),
        "ht_metflux": resolve("metflux_logo.png"),
        "ht_mark": resolve("brand_mark.png"),
    }


def page_asset_urls(variant: str = "male", *, for_http: bool = False) -> dict[str, str]:
    """Merged asset map for all implemented pages."""
    return {
        **cover_asset_urls(variant, for_http=for_http),
        **welcome_asset_urls(variant, for_http=for_http),
        **toc_asset_urls(for_http=for_http),
        **diseases_index_asset_urls(for_http=for_http),
        **health_summary_asset_urls(for_http=for_http),
        **at_a_glance_asset_urls(variant, for_http=for_http),
        **risk_summary_asset_urls(for_http=for_http),
        **disease_divider_asset_urls(for_http=for_http),
        **disease_detail_asset_urls(for_http=for_http),
        **health_trends_asset_urls(for_http=for_http),
        **allergy_cancer_asset_urls(for_http=for_http),
        **back_cover_asset_urls(for_http=for_http),
    }
