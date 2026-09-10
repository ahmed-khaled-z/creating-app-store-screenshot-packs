"""Device families, source classification, and frame geometry.

Single source of truth for anything device-shaped. Nothing else in the pipeline
is allowed to hardcode a bezel, an aspect ratio, or an export size.
"""

from dataclasses import dataclass, field


PHONE_CLASS = "phone"
TABLET_CLASS = "tablet"
UNKNOWN_CLASS = "unknown"

PORTRAIT = "portrait"
LANDSCAPE = "landscape"


@dataclass(frozen=True)
class FrameStyle:
    """Bezel geometry, expressed as fractions of the screen (not the canvas).

    Fractions keep a frame correct at any render size and make it impossible to
    reuse a phone bezel on a tablet: the family owns these numbers.
    """

    side_bezel: float          # fraction of screen width
    top_bezel: float           # fraction of screen width
    bottom_bezel: float        # fraction of screen width
    screen_radius: float       # fraction of screen width
    body_radius: float         # fraction of screen width
    cutout: str                # "island" | "punch-hole" | "camera-dot" | "none"
    home_indicator: bool


@dataclass(frozen=True)
class DeviceFamily:
    key: str
    label: str
    device_class: str          # PHONE_CLASS | TABLET_CLASS
    platform: str              # "apple" | "android"
    # Accepted short/long ratios for a *source* screenshot of this family.
    source_ratio_range: tuple[float, float]
    frame: FrameStyle
    # Fraction of canvas width a single hero device may occupy, per orientation.
    hero_width: dict[str, float]
    max_device_width: float
    safe_margin: float         # fraction of the shorter canvas edge
    layout_families: tuple[str, ...]
    export_sizes: tuple[tuple[int, int], ...]   # documented defaults, verified at runtime


PHONE_FRAME_APPLE = FrameStyle(0.030, 0.030, 0.030, 0.085, 0.105, "island", True)
PHONE_FRAME_ANDROID = FrameStyle(0.026, 0.030, 0.038, 0.055, 0.070, "punch-hole", False)
TABLET_FRAME_APPLE = FrameStyle(0.038, 0.038, 0.038, 0.030, 0.046, "camera-dot", True)
TABLET_FRAME_ANDROID = FrameStyle(0.034, 0.034, 0.034, 0.018, 0.030, "camera-dot", False)


DEVICE_FAMILIES: dict[str, DeviceFamily] = {
    "iphone": DeviceFamily(
        key="iphone",
        label="iPhone",
        device_class=PHONE_CLASS,
        platform="apple",
        source_ratio_range=(0.42, 0.58),
        frame=PHONE_FRAME_APPLE,
        hero_width={PORTRAIT: 0.60, LANDSCAPE: 0.86},
        max_device_width=0.78,
        safe_margin=0.055,
        layout_families=("phone", "shared"),
        export_sizes=((1290, 2796), (1242, 2688)),
    ),
    "android-phone": DeviceFamily(
        key="android-phone",
        label="Android phone",
        device_class=PHONE_CLASS,
        platform="android",
        source_ratio_range=(0.42, 0.58),
        frame=PHONE_FRAME_ANDROID,
        hero_width={PORTRAIT: 0.60, LANDSCAPE: 0.86},
        max_device_width=0.78,
        safe_margin=0.055,
        layout_families=("phone", "shared"),
        export_sizes=((1080, 1920), (1440, 2560)),
    ),
    "ipad": DeviceFamily(
        key="ipad",
        label="iPad",
        device_class=TABLET_CLASS,
        platform="apple",
        source_ratio_range=(0.62, 0.82),
        frame=TABLET_FRAME_APPLE,
        hero_width={PORTRAIT: 0.74, LANDSCAPE: 0.92},
        max_device_width=0.94,
        safe_margin=0.045,
        layout_families=("tablet", "shared"),
        export_sizes=((2048, 2732), (1668, 2388)),
    ),
    "android-tablet": DeviceFamily(
        key="android-tablet",
        label="Android tablet",
        device_class=TABLET_CLASS,
        platform="android",
        source_ratio_range=(0.58, 0.80),
        frame=TABLET_FRAME_ANDROID,
        hero_width={PORTRAIT: 0.74, LANDSCAPE: 0.92},
        max_device_width=0.94,
        safe_margin=0.045,
        layout_families=("tablet", "shared"),
        export_sizes=((1600, 2560), (1200, 1920)),
    ),
}

PLATFORMS = tuple(DEVICE_FAMILIES)


class DeviceClassifier:
    """Classifies a *source screenshot* by shape alone.

    Deliberately shape-based: a screenshot is phone- or tablet-shaped, and no
    amount of output canvas size changes that.
    """

    PHONE_MAX_RATIO = 0.58
    TABLET_MIN_RATIO = 0.62

    @classmethod
    def classify(cls, width: int, height: int) -> dict:
        if width < 1 or height < 1:
            raise ValueError(f"invalid screenshot dimensions: {width}x{height}")
        short, long_ = sorted((width, height))
        ratio = short / long_
        if ratio <= cls.PHONE_MAX_RATIO:
            device_class = PHONE_CLASS
        elif ratio >= cls.TABLET_MIN_RATIO:
            device_class = TABLET_CLASS
        else:
            device_class = UNKNOWN_CLASS
        return {
            "width": width,
            "height": height,
            "orientation": PORTRAIT if height >= width else LANDSCAPE,
            "short_long_ratio": round(ratio, 4),
            "aspect": round(width / height, 4),
            "device_class": device_class,
        }


class TargetDeviceResolver:
    """Answers: may this source be presented as native UI of this target?"""

    @staticmethod
    def family(target: str) -> DeviceFamily:
        try:
            return DEVICE_FAMILIES[target]
        except KeyError:
            raise ValueError(f"unknown target device family: {target}") from None

    @classmethod
    def resolve(cls, analysis: dict, target: str) -> dict:
        family = cls.family(target)
        source_class = analysis["device_class"]
        native = source_class == family.device_class
        low, high = family.source_ratio_range
        in_range = low <= analysis["short_long_ratio"] <= high

        if native and in_range:
            mode = "native"
        elif native:
            # Right class, unusual ratio (foldable, odd capture). Still native UI.
            mode = "native-offspec"
        elif source_class == PHONE_CLASS and family.device_class == TABLET_CLASS:
            mode = "promotional"          # phone artwork on a tablet canvas
        elif source_class == TABLET_CLASS and family.device_class == PHONE_CLASS:
            mode = "incompatible"         # never crop a tablet UI into a phone
        else:
            mode = "incompatible"
        return {
            "target": target,
            "target_class": family.device_class,
            "source_class": source_class,
            "presentation": mode,
            "requires_real_capture": mode in ("promotional", "incompatible"),
        }


class DeviceFrameResolver:
    """Builds a frame whose screen aspect always equals the source aspect.

    This is what makes distortion structurally impossible: the frame adapts to
    the screenshot, never the other way round. The family supplies only bezel
    style and thickness, so a phone-shaped source can never yield a
    tablet-shaped screen area.
    """

    _cache: dict[tuple, dict] = {}

    @classmethod
    def resolve(cls, analysis: dict, target: str, screen_width: float) -> dict:
        key = (analysis["aspect"], target, round(screen_width, 3))
        cached = cls._cache.get(key)
        if cached is not None:
            return dict(cached)

        family = TargetDeviceResolver.family(target)
        style = family.frame
        screen_height = screen_width / analysis["aspect"]
        frame = {
            "family": family.key,
            "frame_class": _frame_class_for(analysis, family),
            "platform": family.platform,
            "screen_width": screen_width,
            "screen_height": screen_height,
            "screen_aspect": analysis["aspect"],
            "side_bezel": style.side_bezel * screen_width,
            "top_bezel": style.top_bezel * screen_width,
            "bottom_bezel": style.bottom_bezel * screen_width,
            "screen_radius": style.screen_radius * screen_width,
            "body_radius": style.body_radius * screen_width,
            "cutout": style.cutout,
            "home_indicator": style.home_indicator,
        }
        frame["body_width"] = screen_width + 2 * frame["side_bezel"]
        frame["body_height"] = screen_height + frame["top_bezel"] + frame["bottom_bezel"]
        cls._cache[key] = dict(frame)
        return frame

    @staticmethod
    def body_width_for_screen(target: str, screen_width: float) -> float:
        style = TargetDeviceResolver.family(target).frame
        return screen_width * (1 + 2 * style.side_bezel)

    @staticmethod
    def screen_width_for_body(target: str, body_width: float) -> float:
        style = TargetDeviceResolver.family(target).frame
        return body_width / (1 + 2 * style.side_bezel)


def _frame_class_for(analysis: dict, family: DeviceFamily) -> str:
    """The shape class the rendered frame actually reads as.

    Derived from the source, not the target, so validation can catch a phone
    frame that ended up in a tablet export.
    """
    if analysis["device_class"] != UNKNOWN_CLASS:
        return analysis["device_class"]
    return family.device_class
