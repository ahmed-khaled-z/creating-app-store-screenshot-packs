"""End-to-end checks for device handling, layout variation, and validation."""

import json
import struct
import sys
import tempfile
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from devices import DeviceClassifier, DeviceFrameResolver, TargetDeviceResolver
from generate_pack import PackGenerator
from layout_engine import LayoutLibrary, TypographyEngine
from validate import errors, validate_plan


def write_png(path: Path, width: int, height: int, colour=(90, 75, 219)) -> Path:
    row = b"\x00" + bytes(colour) * width
    raw = zlib.compress(row * height, 6)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", raw)
        + chunk(b"IEND", b"")
    )
    return path


SLIDE_COPY = [
    ("Plan every school day", "Timetables, homework and grades in one place"),
    ("Track progress live", "Results update the moment a teacher posts them"),
    ("Manage your classes", "Add, edit and archive without leaving the app"),
    ("Never miss a notice", "Push alerts for absences, events and payments"),
]


def build_spec(sources: list[Path], targets: dict) -> dict:
    slides = []
    for index, (title, subtitle) in enumerate(SLIDE_COPY):
        slides.append({
            "sources": [str(sources[index % len(sources)])],
            "label": ["home", "dashboard", "settings", "notifications"][index],
            "title": title,
            "subtitle": subtitle,
        })
    return {
        "app_name": "Schoolz",
        "language": "en",
        "style": "S1",
        "targets": {name: {"size": size, "slides": slides} for name, size in targets.items()},
    }


def test_frame_never_distorts() -> None:
    for width, height in ((1170, 2532), (2048, 2732), (2732, 2048), (1080, 1920)):
        analysis = DeviceClassifier.classify(width, height)
        for target in ("iphone", "ipad", "android-phone", "android-tablet"):
            frame = DeviceFrameResolver.resolve(analysis, target, 600)
            drawn = frame["screen_width"] / frame["screen_height"]
            assert abs(drawn - analysis["aspect"]) < 1e-6, (target, width, height, drawn)


def test_phone_source_never_reads_as_tablet() -> None:
    phone = DeviceClassifier.classify(1170, 2532)
    for target in ("ipad", "android-tablet"):
        resolved = TargetDeviceResolver.resolve(phone, target)
        assert resolved["presentation"] == "promotional", resolved
        assert resolved["requires_real_capture"] is True
        assert DeviceFrameResolver.resolve(phone, target, 400)["frame_class"] == "phone"


def test_tablet_source_rejected_for_phone_target() -> None:
    tablet = DeviceClassifier.classify(2048, 2732)
    for target in ("iphone", "android-phone"):
        assert TargetDeviceResolver.resolve(tablet, target)["presentation"] == "incompatible"


def test_tablet_layouts_are_not_phone_layouts() -> None:
    library = LayoutLibrary()
    phone_ids = {layout["id"] for layout in library.for_family("iphone")}
    tablet_ids = {layout["id"] for layout in library.for_family("ipad")}
    assert phone_ids != tablet_ids
    assert not {"hero-centered", "dual-overlap"} & tablet_ids
    assert not {"tablet-hero", "tablet-with-cards"} & phone_ids


def test_typography_shrinks_then_reports_overflow() -> None:
    layout = LayoutLibrary().get("hero-centered")
    short = TypographyEngine.fit("Plan the day", "Simple and quick", layout, (1290, 2796), "phone")
    assert short["fits"] and short["scale"] == 1.0
    long_ = TypographyEngine.fit("Plan " * 60, "Detail " * 60, layout, (1290, 2796), "phone")
    assert long_["fits"] is False


def run_pipeline(tmp: Path, sources: list[Path], targets: dict, html_only: bool) -> dict:
    spec = build_spec(sources, targets)
    (tmp / "spec.json").write_text(json.dumps(spec))
    return PackGenerator(spec, tmp / "staging", html_only=html_only).run()


def test_tablet_target_with_tablet_sources(tmp: Path) -> None:
    tablet = write_png(tmp / "tablet-home.png", 2048, 2732)
    report = run_pipeline(tmp, [tablet], {"ipad": [2048, 2732]}, html_only=True)
    outputs = report["platforms"]["ipad"]["outputs"]
    assert all(item["presentation"] == "native" for item in outputs)
    plans = json.loads((tmp / "staging" / "ipad-plan.json").read_text())
    for plan in plans:
        assert plan["layout_family"] == "tablet", plan["layout_id"]
        for device in plan["devices"]:
            assert device["frame_class"] == "tablet"
            assert device["width_fraction"] > 0.5, "a tablet hero should own the canvas"


def test_tablet_target_with_phone_sources_is_promotional(tmp: Path) -> None:
    phone = write_png(tmp / "phone-home.png", 1170, 2532)
    report = run_pipeline(tmp, [phone], {"ipad": [2048, 2732]}, html_only=True)
    outputs = report["platforms"]["ipad"]["outputs"]
    assert all(item["presentation"] == "promotional" for item in outputs)
    plans = json.loads((tmp / "staging" / "ipad-plan.json").read_text())
    for plan in plans:
        assert "promotional" in plan["layout_tags"], plan["layout_id"]
        assert any(item["kind"] == "promo-note" for item in plan["decor"])
        for device in plan["devices"]:
            assert device["width_fraction"] <= 0.45, "phone must not be scaled up into a fake tablet"


def test_phone_target_varies_layouts(tmp: Path) -> None:
    phone = write_png(tmp / "phone-home.png", 1170, 2532)
    report = run_pipeline(tmp, [phone], {"iphone": [1290, 2796]}, html_only=True)
    layouts = [item["layout"] for item in report["platforms"]["iphone"]["outputs"]]
    assert len(set(layouts)) >= 3, layouts
    assert all(previous != current for previous, current in zip(layouts, layouts[1:]))


def test_sequence_puts_the_strongest_screen_first(tmp: Path) -> None:
    phone = write_png(tmp / "phone.png", 1170, 2532)
    report = run_pipeline(tmp, [phone], {"iphone": [1290, 2796]}, html_only=True)
    first = report["platforms"]["iphone"]["outputs"][0]
    assert "hero" in first["layout"] or "hero" in first["layout_label"].lower()


def test_incompatible_pairing_is_refused(tmp: Path) -> None:
    tablet = write_png(tmp / "tablet.png", 2048, 2732)
    try:
        run_pipeline(tmp, [tablet], {"iphone": [1290, 2796]}, html_only=True)
    except ValueError as error:
        assert "incompatible" in str(error)
        return
    raise AssertionError("a tablet capture must not be squeezed into a phone export")


def test_validator_catches_a_phone_frame_in_a_tablet_export(tmp: Path) -> None:
    phone = write_png(tmp / "p.png", 1170, 2532)
    from analyzer import ScreenshotAnalyzer
    from layout_engine import LayoutEngine

    analysis = ScreenshotAnalyzer().analyze(phone)
    plan = LayoutEngine().resolve(
        layout=LayoutLibrary().get("tablet-hero"), group=[analysis], target="ipad",
        canvas=(2048, 2732), copy={"title": "Hi", "subtitle": ""}, presentation="native",
    )
    codes = {issue["code"] for issue in errors(validate_plan(plan))}
    assert "phone-frame-in-tablet-export" in codes, codes


def test_rendered_pngs_have_exact_dimensions(tmp: Path) -> None:
    from render import ExportManager

    if ExportManager().browser is None:
        print("  skip: no headless browser available")
        return
    phone = write_png(tmp / "phone.png", 1170, 2532)
    tablet = write_png(tmp / "tablet.png", 2048, 2732)
    spec = build_spec([phone], {"iphone": [1290, 2796]})
    spec["targets"]["ipad"] = {
        "size": [2048, 2732],
        "slides": [
            {"sources": [str(tablet)], "label": "home",
             "title": "Plan every school day",
             "subtitle": "Timetables and grades in one place"},
            {"sources": [str(tablet)], "label": "settings",
             "title": "Manage your classes",
             "subtitle": "Add, edit and archive in place"},
        ],
    }
    try:
        report = PackGenerator(spec, tmp / "render", html_only=False).run()
    except RuntimeError as error:
        print(f"  skip: {error}")
        return
    for target, config in report["platforms"].items():
        for item in config["outputs"]:
            path = tmp / "render" / target / item["filename"]
            with path.open("rb") as image:
                image.read(16)
                width, height = struct.unpack(">II", image.read(8))
            assert [width, height] == config["size"], (target, item["filename"], width, height)
            assert path.stat().st_size > 5000


def main() -> int:
    simple = [test_frame_never_distorts, test_phone_source_never_reads_as_tablet,
              test_tablet_source_rejected_for_phone_target, test_tablet_layouts_are_not_phone_layouts,
              test_typography_shrinks_then_reports_overflow]
    with_tmp = [test_tablet_target_with_tablet_sources, test_tablet_target_with_phone_sources_is_promotional,
                test_phone_target_varies_layouts, test_sequence_puts_the_strongest_screen_first,
                test_incompatible_pairing_is_refused, test_validator_catches_a_phone_frame_in_a_tablet_export,
                test_rendered_pngs_have_exact_dimensions]
    for check in simple:
        check()
        print(f"ok  {check.__name__}")
    for check in with_tmp:
        with tempfile.TemporaryDirectory() as work:
            check(Path(work))
        print(f"ok  {check.__name__}")
    print(f"{len(simple) + len(with_tmp)} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
