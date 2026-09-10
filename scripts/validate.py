"""OutputValidator: device correctness gate that runs before export.

Every rule here exists to make one of the non-negotiables unbreakable rather
than merely discouraged.
"""

import math
from pathlib import Path

from devices import PHONE_CLASS, TABLET_CLASS, TargetDeviceResolver


ASPECT_TOLERANCE = 0.005      # 0.5% — anything larger is visible distortion
PHONE_ON_TABLET_MAX_WIDTH = 0.45
OVERFLOW_SLACK = 0.02         # fraction of canvas height


class ValidationError(Exception):
    pass


def validate_plan(plan: dict, *, rendered: Path | None = None) -> list[dict]:
    issues: list[dict] = []
    canvas_width, canvas_height = plan["canvas"]
    family = TargetDeviceResolver.family(plan["target"])
    margin = plan["safe_margin"]
    promotional = "promotional" in plan.get("layout_tags", [])

    for index, device in enumerate(plan["devices"]):
        where = f"device[{index}]"
        frame_class = device["frame_class"]

        if family.device_class == TABLET_CLASS and frame_class == PHONE_CLASS and not promotional:
            issues.append(_error(where, "phone-frame-in-tablet-export",
                                 f"{plan['target']} export contains a phone-shaped frame; "
                                 "use a tablet capture or a declared promotional layout"))
        if family.device_class == PHONE_CLASS and frame_class == TABLET_CLASS:
            issues.append(_error(where, "tablet-frame-in-phone-export",
                                 f"{plan['target']} export contains a tablet-shaped frame"))
        if promotional and frame_class == PHONE_CLASS and device["width_fraction"] > PHONE_ON_TABLET_MAX_WIDTH:
            issues.append(_error(where, "phone-scaled-to-tablet",
                                 f"phone mockup occupies {device['width_fraction']:.0%} of a tablet canvas; "
                                 "that reads as a fake tablet"))

        frame = device["frame"]
        drawn = frame["screen_width"] / frame["screen_height"]
        if abs(drawn - frame["screen_aspect"]) / frame["screen_aspect"] > ASPECT_TOLERANCE:
            issues.append(_error(where, "distorted-screenshot",
                                 f"screen area {drawn:.4f} does not match source aspect {frame['screen_aspect']:.4f}"))

        half_w, half_h = _rotated_half_extents(device["width"], device["height"], device["rotate"])
        centre_x = device["left"] + device["width"] / 2
        centre_y = device["top"] + device["height"] / 2
        left, right = centre_x - half_w, centre_x + half_w
        top, bottom = centre_y - half_h, centre_y + half_h
        allow_bottom = canvas_height if device.get("crops") else canvas_height - margin
        slack = OVERFLOW_SLACK * canvas_height

        if top < margin - slack:
            issues.append(_error(where, "device-above-safe-area", f"device top {top:.0f}px is above the safe margin"))
        if bottom > allow_bottom + slack and not device.get("crops"):
            issues.append(_error(where, "device-below-safe-area",
                                 f"device bottom {bottom:.0f}px exceeds the safe area for a non-cropping layout"))
        if device["width"] <= canvas_width and (left < -slack or right > canvas_width + slack):
            issues.append(_error(where, "device-outside-canvas", "device extends horizontally past the canvas"))
        visible = _visible_fraction(left, right, top, bottom, canvas_width, canvas_height)
        if visible < 0.55:
            issues.append(_error(where, "device-mostly-cropped",
                                 f"only {visible:.0%} of the device is inside the canvas"))

    if promotional and not any(item["kind"] == "promo-note" for item in plan.get("decor", [])):
        issues.append(_error("layout", "missing-promo-disclosure",
                             "a promotional cross-class layout must carry its disclosure note"))

    text = plan["text"]
    if not text["fits"]:
        issues.append(_error("text", "text-overflow",
                             "headline and subtitle do not fit the reserved text area at the minimum type scale"))

    if rendered is not None:
        actual = _png_size(Path(rendered))
        if actual != (canvas_width, canvas_height):
            issues.append(_error("export", "wrong-export-dimensions",
                                 f"rendered {actual[0]}x{actual[1]}, expected {canvas_width}x{canvas_height}"))
    return issues


def validate_set(plans: list[dict], tokens: dict) -> list[dict]:
    """Set-level consistency: one design system, meaningful variation."""
    issues: list[dict] = []
    if not plans:
        return [_error("set", "empty-set", "no compositions to validate")]

    canvases = {tuple(plan["canvas"]) for plan in plans}
    if len(canvases) > 1:
        issues.append(_error("set", "mixed-canvas-sizes", f"one export size per platform expected, saw {sorted(canvases)}"))
    scales = {plan["text"]["scale"] for plan in plans}
    if len(scales) > 3:
        issues.append(_error("set", "unstable-typography",
                             "too many type scales in one set; headlines need rebalancing"))
    layouts = [plan["layout_id"] for plan in plans]
    if len(plans) >= 3 and len(set(layouts)) == 1:
        issues.append(_error("set", "static-template",
                             f"every composition uses '{layouts[0]}'; the set needs layout variation"))
    for previous, current in zip(layouts, layouts[1:]):
        if previous == current:
            issues.append(_warning("set", "adjacent-repeat",
                                   f"'{current}' repeats back to back"))
    if not tokens.get("code"):
        issues.append(_error("set", "missing-style", "no resolved style tokens for the set"))
    return issues


def errors(issues: list[dict]) -> list[dict]:
    return [issue for issue in issues if issue["severity"] == "error"]


def _error(where: str, code: str, message: str) -> dict:
    return {"severity": "error", "where": where, "code": code, "message": message}


def _warning(where: str, code: str, message: str) -> dict:
    return {"severity": "warning", "where": where, "code": code, "message": message}


def _rotated_half_extents(width: float, height: float, degrees: float) -> tuple[float, float]:
    radians = math.radians(abs(degrees))
    cos, sin = math.cos(radians), math.sin(radians)
    return (width * cos + height * sin) / 2, (width * sin + height * cos) / 2


def _visible_fraction(left, right, top, bottom, canvas_width, canvas_height) -> float:
    inner_w = max(0.0, min(right, canvas_width) - max(left, 0.0))
    inner_h = max(0.0, min(bottom, canvas_height) - max(top, 0.0))
    total = (right - left) * (bottom - top)
    return (inner_w * inner_h) / total if total else 0.0


def _png_size(path: Path) -> tuple[int, int]:
    import struct
    with path.open("rb") as image:
        if image.read(8) != b"\x89PNG\r\n\x1a\n":
            raise ValidationError(f"not a PNG: {path}")
        image.read(8)
        return struct.unpack(">II", image.read(8))
