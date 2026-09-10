"""Layout selection and geometry resolution.

Three separate jobs, deliberately kept apart from rendering:
  LayoutLibrary   loads declarative templates from scripts/layouts/
  LayoutSelector  picks a template for one composition, given set context
  LayoutEngine    turns a template into absolute pixel geometry
  TypographyEngine sizes and wraps text against the template's text area
"""

import json
import math
from pathlib import Path

from devices import (
    DeviceFrameResolver,
    TargetDeviceResolver,
    PHONE_CLASS,
    TABLET_CLASS,
)


LAYOUT_ROOT = Path(__file__).resolve().parent / "layouts"

PROMOTIONAL_TAGS = {"hero", "bold", "dynamic", "depth"}
INFORMATIONAL_TAGS = {"feature", "calm", "editorial", "cards", "sequence"}


class LayoutLibrary:
    """Loads every template once and serves them by family."""

    def __init__(self, root: Path = LAYOUT_ROOT) -> None:
        self.root = Path(root)
        self._layouts: dict[str, dict] | None = None

    @property
    def layouts(self) -> dict[str, dict]:
        if self._layouts is None:
            found: dict[str, dict] = {}
            for path in sorted(self.root.rglob("*.json")):
                layout = json.loads(path.read_text())
                layout["path"] = str(path)
                if layout["id"] in found:
                    raise ValueError(f"duplicate layout id: {layout['id']}")
                found[layout["id"]] = layout
            if not found:
                raise ValueError(f"no layout templates under {self.root}")
            self._layouts = found
        return self._layouts

    def for_family(self, target: str) -> list[dict]:
        allowed = set(TargetDeviceResolver.family(target).layout_families)
        return [layout for layout in self.layouts.values() if layout["family"] in allowed]

    def get(self, layout_id: str) -> dict:
        try:
            return self.layouts[layout_id]
        except KeyError:
            raise ValueError(f"unknown layout: {layout_id}") from None


class TypographyEngine:
    """One type scale per set; per-layout sizing derived from it.

    Character-width estimation is intentionally conservative so a headline that
    passes here does not clip in the rendered PNG.
    """

    TITLE_RATIO = 0.058          # of canvas width
    SUBTITLE_RATIO = 0.028
    TITLE_CHAR_WIDTH = 0.54      # em, bold condensed-ish sans
    SUBTITLE_CHAR_WIDTH = 0.50
    TITLE_LINE_HEIGHT = 1.08
    SUBTITLE_LINE_HEIGHT = 1.35
    MIN_SCALE = 0.72

    @classmethod
    def scale_for(cls, canvas_width: int, device_class: str) -> float:
        # Tablets are viewed further away relative to their canvas: slightly tighter type.
        return 0.88 if device_class == TABLET_CLASS else 1.0

    @classmethod
    def fit(cls, title: str, subtitle: str, layout: dict, canvas: tuple[int, int],
            device_class: str) -> dict:
        canvas_width, canvas_height = canvas
        spec = layout["text"]
        x0, y0, x1, y1 = spec["area"]
        box_width = (x1 - x0) * canvas_width
        box_height = (y1 - y0) * canvas_height
        base = cls.scale_for(canvas_width, device_class) * spec.get("scale", 1.0)

        step = base
        while step >= cls.MIN_SCALE * base - 1e-9:
            title_size = cls.TITLE_RATIO * canvas_width * step
            subtitle_size = cls.SUBTITLE_RATIO * canvas_width * step
            title_lines = wrap(title, box_width / (title_size * cls.TITLE_CHAR_WIDTH))
            subtitle_lines = wrap(subtitle, box_width / (subtitle_size * cls.SUBTITLE_CHAR_WIDTH))
            height = len(title_lines) * title_size * cls.TITLE_LINE_HEIGHT
            if subtitle_lines:
                height += 0.42 * title_size + len(subtitle_lines) * subtitle_size * cls.SUBTITLE_LINE_HEIGHT
            if height <= box_height and len(title_lines) <= 3 and len(subtitle_lines) <= 3:
                return {
                    "title": title, "subtitle": subtitle,
                    "title_lines": title_lines, "subtitle_lines": subtitle_lines,
                    "title_size": round(title_size, 2), "subtitle_size": round(subtitle_size, 2),
                    "align": spec["align"], "scale": round(step, 4),
                    "box": [x0 * canvas_width, y0 * canvas_height, x1 * canvas_width, y1 * canvas_height],
                    "used_height": round(height, 2), "fits": True,
                }
            step -= 0.04
        return {
            "title": title, "subtitle": subtitle,
            "title_lines": wrap(title, max(1.0, box_width / (cls.TITLE_RATIO * canvas_width * cls.MIN_SCALE * cls.TITLE_CHAR_WIDTH))),
            "subtitle_lines": wrap(subtitle, 40),
            "title_size": round(cls.TITLE_RATIO * canvas_width * cls.MIN_SCALE * base, 2),
            "subtitle_size": round(cls.SUBTITLE_RATIO * canvas_width * cls.MIN_SCALE * base, 2),
            "align": spec["align"], "scale": round(cls.MIN_SCALE * base, 4),
            "box": [x0 * canvas_width, y0 * canvas_height, x1 * canvas_width, y1 * canvas_height],
            "used_height": None, "fits": False,
        }


def wrap(text: str, max_chars: float) -> list[str]:
    """Greedy wrap on a fractional character budget."""
    words = (text or "").split()
    if not words:
        return []
    budget = max(1, int(max_chars))
    lines, current = [], words[0]
    for word in words[1:]:
        if len(current) + 1 + len(word) <= budget:
            current = f"{current} {word}"
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


class LayoutSelector:
    """Deterministic, explainable layout choice.

    Hard requirements filter the candidate list; the remaining score decides.
    Set context (what came before) supplies the variation pressure, so the pack
    is varied without ever being random.
    """

    def __init__(self, library: LayoutLibrary) -> None:
        self.library = library

    def select(self, *, target: str, group: list[dict], copy: dict,
               canvas: tuple[int, int], presentation: str, used: list[str],
               exclude: set[str] | None = None) -> dict:
        lead = group[0]
        exclude = exclude or set()
        candidates = []
        for layout in sorted(self.library.for_family(target), key=lambda item: item["id"]):
            if layout["id"] in exclude or not self._eligible(layout, group, lead, presentation):
                continue
            score, reasons = self._score(layout, lead, group, copy, canvas, target, used)
            candidates.append((score, layout["id"], layout, reasons))
        if not candidates:
            raise ValueError(
                f"no layout available for target={target} presentation={presentation} "
                f"sources={len(group)} class={lead['device_class']}"
            )
        candidates.sort(key=lambda item: (-item[0], item[1]))
        score, _, layout, reasons = candidates[0]
        return {
            "layout": layout,
            "score": round(score, 3),
            "reasons": reasons,
            "considered": [item[1] for item in candidates[:5]],
        }

    @staticmethod
    def _eligible(layout: dict, group: list[dict], lead: dict, presentation: str) -> bool:
        needs = layout["requires"]
        if not needs["min_screenshots"] <= len(group) <= needs["max_screenshots"]:
            return False
        if presentation not in needs["presentation"]:
            return False
        return all(
            item["device_class"] in needs["source_class"] and item["orientation"] in needs["orientation"]
            for item in group
        )

    @staticmethod
    def _score(layout: dict, lead: dict, group: list[dict], copy: dict,
               canvas: tuple[int, int], target: str, used: list[str]) -> tuple[float, list[str]]:
        tags = set(layout.get("tags", ()))
        score = float(layout.get("weight", 1.0))
        reasons = []

        if lead.get("is_lead") and "hero" in tags:
            score += 0.40
            reasons.append("lead image gets a hero composition")
        if lead["intent"] == "promotional" and tags & PROMOTIONAL_TAGS:
            score += 0.22
            reasons.append("promotional screen suits a dynamic composition")
        if lead["intent"] == "informational" and tags & INFORMATIONAL_TAGS:
            score += 0.22
            reasons.append("informational screen suits a structured composition")
        if len(group) > 1 and tags & {"dual", "triple", "sequence"}:
            score += 0.30
            reasons.append(f"{len(group)} screenshots grouped in one composition")

        title_length = len(copy.get("title", ""))
        headroom = layout["text"]["title_max_chars"]
        if title_length <= headroom:
            score += 0.30 * (1 - title_length / max(headroom, 1))
            reasons.append("headline fits the reserved text area")
        else:
            score -= 1.30
            reasons.append("headline is longer than this layout reserves for it")
        if len(copy.get("subtitle", "")) > layout["text"]["subtitle_max_chars"]:
            score -= 0.60

        # Device presence: reward layouts that use the canvas the target deserves.
        family = TargetDeviceResolver.family(target)
        widest = max(device["width"] for device in layout["devices"])
        if family.device_class == TABLET_CLASS and widest < 0.5 and "promotional" not in tags:
            score -= 0.40
            reasons.append("small device presentation is weak on a tablet canvas")
        if title_length <= 18 and widest >= 0.6:
            score += 0.15
            reasons.append("short headline leaves room for a larger device")

        if used and layout["id"] == used[-1]:
            score -= 0.95
            reasons.append("avoids repeating the previous composition")
        elif layout["id"] in used:
            score -= 0.40
            reasons.append("varies from compositions already used in this set")
        return score, reasons


class LayoutEngine:
    """Template plus sources plus canvas -> absolute geometry.

    Pure and deterministic: same inputs always produce the same plan, and the
    plan is the only thing the renderer and validator ever see.
    """

    MIN_BODY_WIDTH = 0.16        # fraction of canvas width
    MIN_DELIBERATE_CROP = 0.10   # smaller declared overflows are treated as "fit inside"
    TEXT_GAP = 0.025             # fraction of canvas height between a device and copy below it

    def resolve(self, *, layout: dict, group: list[dict], target: str,
                canvas: tuple[int, int], copy: dict, presentation: str) -> dict:
        canvas_width, canvas_height = canvas
        family = TargetDeviceResolver.family(target)
        margin = family.safe_margin * min(canvas_width, canvas_height)

        # When the copy sits below the devices, the text area is the floor -
        # otherwise a short canvas leaves a dead band under the device.
        text_top = layout["text"]["area"][1]
        floor = canvas_height - margin
        if text_top >= 0.5 and all(spec["top"] < text_top for spec in layout["devices"]):
            floor = text_top * canvas_height - self.TEXT_GAP * canvas_height

        devices = []
        for spec in layout["devices"]:
            analysis = group[min(spec["source"], len(group) - 1)]
            devices.append(self._place(spec, analysis, target, family, canvas, margin, floor))
        devices.sort(key=lambda item: item["z"])

        text = TypographyEngine.fit(
            copy.get("title", ""), copy.get("subtitle", ""), layout, canvas,
            family.device_class,
        )
        return {
            "layout_id": layout["id"],
            "layout_label": layout["label"],
            "layout_family": layout["family"],
            "layout_tags": layout.get("tags", []),
            "target": target,
            "target_class": family.device_class,
            "presentation": presentation,
            "canvas": [canvas_width, canvas_height],
            "safe_margin": round(margin, 2),
            "devices": devices,
            "decor": self._decor(layout, canvas, copy),
            "text": text,
            "sources": [item["path"] for item in group],
        }

    def _place(self, spec: dict, analysis: dict, target: str, family, canvas, margin, floor: float) -> dict:
        canvas_width, canvas_height = canvas
        body_width = min(spec["width"], family.max_device_width if spec["width"] <= 1.0 else spec["width"]) * canvas_width
        top = spec["top"] * canvas_height
        # A device that stops just short of the canvas edge reads as an accident.
        # Only a deliberate crop is allowed past the safe margin.
        crops = spec["fit"] == "crop-bottom" and spec.get("max_overflow", 0.0) >= self.MIN_DELIBERATE_CROP
        overflow = spec["max_overflow"] * canvas_height if crops else 0.0
        limit = floor + overflow

        for _ in range(48):
            screen_width = DeviceFrameResolver.screen_width_for_body(target, body_width)
            frame = DeviceFrameResolver.resolve(analysis, target, screen_width)
            half_w, half_h = _rotated_half_extents(frame["body_width"], frame["body_height"], spec["rotate"])
            bottom = top + frame["body_height"] / 2 + half_h
            if bottom <= limit or body_width <= self.MIN_BODY_WIDTH * canvas_width:
                break
            body_width *= max(0.90, (limit - top) / max(bottom - top, 1e-6))

        screen_width = DeviceFrameResolver.screen_width_for_body(target, body_width)
        frame = DeviceFrameResolver.resolve(analysis, target, screen_width)
        half_w, _ = _rotated_half_extents(frame["body_width"], frame["body_height"], spec["rotate"])
        centre_x = spec["cx"] * canvas_width
        if frame["body_width"] <= canvas_width - 2 * margin:
            centre_x = min(max(centre_x, margin + half_w), canvas_width - margin - half_w)

        return {
            "source": analysis["path"],
            "source_class": analysis["device_class"],
            "orientation": analysis["orientation"],
            "frame_class": frame["frame_class"],
            "frame": frame,
            "left": round(centre_x - frame["body_width"] / 2, 2),
            "top": round(top, 2),
            "width": round(frame["body_width"], 2),
            "height": round(frame["body_height"], 2),
            "rotate": spec["rotate"],
            "z": spec["z"],
            "fit": spec["fit"],
            "crops": crops,
            "shadow": spec["shadow"],
            "opacity": spec["opacity"],
            "dim": spec["dim"],
            "width_fraction": round(frame["body_width"] / canvas_width, 4),
        }

    @staticmethod
    def _decor(layout: dict, canvas: tuple[int, int], copy: dict) -> list[dict]:
        canvas_width, canvas_height = canvas
        resolved = []
        captions = copy.get("captions", [])
        for item in layout.get("decor", []):
            entry = dict(item)
            if "area" in entry:
                x0, y0, x1, y1 = entry["area"]
                entry["px"] = [x0 * canvas_width, y0 * canvas_height, x1 * canvas_width, y1 * canvas_height]
            if "cx" in entry:
                entry["px_cx"] = entry["cx"] * canvas_width
                entry["px_cy"] = entry["cy"] * canvas_height
            if "r" in entry:
                entry["px_r"] = entry["r"] * canvas_width
            for key in ("w", "h"):
                if key in entry:
                    entry[f"px_{key}"] = entry[key] * (canvas_width if key == "w" else canvas_height)
            if entry.get("kind") in ("caption", "card") and "slot" in entry:
                entry["text"] = captions[entry["slot"]] if entry["slot"] < len(captions) else ""
            if entry.get("kind") == "bullets":
                entry["items"] = copy.get("bullets", [])
            resolved.append(entry)
        return resolved


def _rotated_half_extents(width: float, height: float, degrees: float) -> tuple[float, float]:
    radians = math.radians(abs(degrees))
    cos, sin = math.cos(radians), math.sin(radians)
    return (width * cos + height * sin) / 2, (width * sin + height * cos) / 2
