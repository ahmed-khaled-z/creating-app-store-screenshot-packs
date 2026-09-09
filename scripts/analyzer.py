"""ScreenshotAnalyzer: reads image geometry and analyses the set as a whole.

Dimensions are parsed straight from the file header so the skill keeps its
zero-dependency promise, and each file is read once and cached.
"""

import struct
from pathlib import Path

from devices import DeviceClassifier, PHONE_CLASS, TABLET_CLASS


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Ordered: the first pattern matching a screen's filename or label wins.
SEQUENCE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("value", ("onboard", "welcome", "intro", "home", "landing", "splash", "hero", "start")),
    ("core", ("dashboard", "feed", "main", "overview", "browse", "search", "list", "map")),
    ("secondary", ("detail", "profile", "chat", "message", "calendar", "report", "stats", "chart")),
    ("management", ("manage", "admin", "settings", "account", "edit", "create", "form")),
    ("notification", ("notification", "alert", "reminder", "inbox", "push")),
    ("customization", ("language", "theme", "dark", "locale", "customi", "preference")),
)
SEQUENCE_ORDER = [name for name, _ in SEQUENCE_HINTS] + ["other"]

PROMOTIONAL_ROLES = {"value", "core"}


def image_size(path: Path) -> tuple[int, int]:
    """Width/height for PNG and JPEG without a third-party imaging library."""
    with path.open("rb") as image:
        head = image.read(8)
        if head == PNG_SIGNATURE:
            chunk = image.read(8)
            if len(chunk) != 8 or struct.unpack(">I4s", chunk)[1] != b"IHDR":
                raise ValueError(f"malformed PNG: {path}")
            return struct.unpack(">II", image.read(8))
        if head[:2] == b"\xff\xd8":
            image.seek(2)
            while True:
                marker = image.read(2)
                if len(marker) != 2 or marker[0] != 0xFF:
                    raise ValueError(f"malformed JPEG: {path}")
                length = struct.unpack(">H", image.read(2))[0]
                if 0xC0 <= marker[1] <= 0xCF and marker[1] not in (0xC4, 0xC8, 0xCC):
                    payload = image.read(5)
                    height, width = struct.unpack(">HH", payload[1:5])
                    return width, height
                image.seek(length - 2, 1)
        raise ValueError(f"unsupported image format: {path}")


class ScreenshotAnalyzer:
    """Per-file analysis, memoised by resolved path."""

    def __init__(self) -> None:
        self._cache: dict[Path, dict] = {}

    def analyze(self, path: Path, label: str | None = None) -> dict:
        resolved = Path(path).resolve()
        cached = self._cache.get(resolved)
        if cached is None:
            width, height = image_size(resolved)
            cached = DeviceClassifier.classify(width, height)
            cached["path"] = str(resolved)
            cached["filename"] = resolved.name
            self._cache[resolved] = cached
        analysis = dict(cached)
        analysis["label"] = label or resolved.stem
        analysis["role"] = classify_role(analysis["label"], analysis["filename"])
        analysis["intent"] = "promotional" if analysis["role"] in PROMOTIONAL_ROLES else "informational"
        return analysis


def classify_role(label: str, filename: str) -> str:
    haystack = f"{label} {filename}".lower()
    for role, keywords in SEQUENCE_HINTS:
        if any(keyword in haystack for keyword in keywords):
            return role
    return "other"


class SetAnalyzer:
    """Whole-set decisions: ordering, dominant shape, allowed variation."""

    @staticmethod
    def sequence(analyses: list[dict]) -> list[dict]:
        """Stable ordering by marketing role; ties keep the supplied order."""
        rank = {role: index for index, role in enumerate(SEQUENCE_ORDER)}
        ordered = sorted(
            enumerate(analyses),
            key=lambda pair: (rank.get(pair[1]["role"], len(rank)), pair[0]),
        )
        result: list[dict] = [{} for _ in ordered]
        for position, (original_index, analysis) in enumerate(ordered):
            item = dict(analysis)
            item["position"] = position
            item["is_lead"] = position == 0
            result[original_index] = item
        return result

    @staticmethod
    def summarize(analyses: list[dict]) -> dict:
        if not analyses:
            raise ValueError("no screenshots supplied")
        classes = {analysis["device_class"] for analysis in analyses}
        orientations = {analysis["orientation"] for analysis in analyses}
        aspects = sorted(analysis["aspect"] for analysis in analyses)
        return {
            "count": len(analyses),
            "classes": sorted(classes),
            "dominant_class": TABLET_CLASS if TABLET_CLASS in classes and PHONE_CLASS not in classes else (
                PHONE_CLASS if PHONE_CLASS in classes else next(iter(classes))
            ),
            "orientations": sorted(orientations),
            "mixed_shapes": len(classes) > 1 or (aspects[-1] - aspects[0]) > 0.05,
            "promotional": sum(1 for analysis in analyses if analysis["intent"] == "promotional"),
        }
