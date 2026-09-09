"""BrandStyleResolver: one design system for the whole pack.

Layouts vary; these tokens never do inside a set. That is what keeps a pack
reading as one campaign.
"""

from dataclasses import dataclass, asdict


STYLE_CODES = ("S1", "S2", "S3")


@dataclass(frozen=True)
class StyleTokens:
    code: str
    label: str
    background: str
    ink: str
    muted: str
    title_color: str
    subtitle_color: str
    card_surface: str
    card_ink: str
    accent_soft: str
    device_body: str
    device_edge: str
    shadow_soft: str
    shadow_lifted: str
    shadow_flat: str
    blob_opacity: float


def resolve(code: str, brand: str = "#5b4bdb", brand_strong: str = "#2f246f",
            accent: str = "#ffb35c", cream: str = "#fffaf0", ink: str = "#19172b") -> dict:
    """Style code plus brand colours -> the token set used by every composition."""
    if code not in STYLE_CODES:
        raise ValueError(f"unknown style code: {code}")
    shared = {
        "shadow_soft": "0 34px 70px rgba(20,18,39,0.22)",
        "shadow_lifted": "0 52px 110px rgba(20,18,39,0.32)",
        "shadow_flat": "0 14px 30px rgba(20,18,39,0.14)",
    }
    presets = {
        "S1": StyleTokens(code="S1", label="Clean Cream", background=cream, ink=ink,
                          muted="#6f6a7d", title_color=ink, subtitle_color="#6f6a7d",
                          card_surface="#ffffff", card_ink=ink,
                          accent_soft=f"color-mix(in srgb, {accent} 42%, white)",
                          device_body="#141227", device_edge="rgba(255,255,255,0.16)",
                          blob_opacity=0.18, **shared),
        "S2": StyleTokens(code="S2", label="Bold Brand", background=brand_strong, ink="#ffffff",
                          muted="rgba(255,255,255,0.74)", title_color="#ffffff",
                          subtitle_color="rgba(255,255,255,0.78)",
                          card_surface="rgba(255,255,255,0.12)", card_ink="#ffffff",
                          accent_soft=accent,
                          # A dark device on a dark ground needs a real edge to read as a device.
                          device_body="#0e0c1c", device_edge="rgba(255,255,255,0.38)",
                          blob_opacity=0.26, **shared),
        "S3": StyleTokens(code="S3", label="Soft Gradient",
                          background=(f"linear-gradient(150deg, color-mix(in srgb, {brand} 26%, white) 0%, "
                                      f"color-mix(in srgb, {accent} 40%, white) 100%)"),
                          ink=ink, muted="#5c5670", title_color=ink, subtitle_color="#5c5670",
                          card_surface="rgba(255,255,255,0.82)", card_ink=ink,
                          accent_soft=f"color-mix(in srgb, {brand} 40%, white)",
                          device_body="#141227", device_edge="rgba(255,255,255,0.20)",
                          blob_opacity=0.20, **shared),
    }
    tokens = asdict(presets[code])
    tokens.update({"brand": brand, "brand_strong": brand_strong, "accent": accent})
    return tokens
