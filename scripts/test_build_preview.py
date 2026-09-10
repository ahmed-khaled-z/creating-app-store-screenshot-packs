"""Checks on the generated confirmation gallery."""

import re
import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_preview import build
from test_pipeline import write_png


class Elements(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.found: list[tuple[str, dict]] = []

    def handle_starttag(self, tag, attrs):
        self.found.append((tag, dict(attrs)))


def make_gallery(work: Path, source: Path, targets: dict) -> str:
    spec = {
        "app_name": "Schoolz",
        "language": "en",
        "targets": {
            name: {"size": size, "slides": [
                {"sources": [str(source)], "label": "home", "title": "Plan every school day",
                 "subtitle": "Timetables and grades in one place"},
                {"sources": [str(source)], "label": "settings", "title": "Manage your classes",
                 "subtitle": "Add, edit and archive in place"},
            ]} for name, size in targets.items()
        },
    }
    build(spec, work / "gallery.html")
    return (work / "gallery.html").read_text()


class GalleryTest(unittest.TestCase):
    def test_offers_every_style_and_no_layout_radio(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            source = write_png(work / "phone.png", 1170, 2532)
            html = make_gallery(work, source, {"iphone": [1290, 2796]})

        parser = Elements()
        parser.feed(html)
        radios = [attrs for tag, attrs in parser.found if tag == "input" and attrs.get("name") == "style"]
        self.assertEqual([radio["value"] for radio in radios], ["S1", "S2", "S3"])
        self.assertNotIn("name=layout", html)
        self.assertEqual(len([1 for tag, _ in parser.found if tag == "iframe"]), 6)

    def test_tablet_target_from_phone_sources_is_labelled_promotional(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            source = write_png(work / "phone.png", 1170, 2532)
            html = make_gallery(work, source, {"ipad": [2048, 2732]})

        self.assertIn('class="mode mode-promotional"', html)
        self.assertNotIn('class="mode mode-native"', html)
        self.assertIn("Application shown on a phone", html)

    def test_tablet_target_from_tablet_sources_is_labelled_native(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            source = write_png(work / "tablet.png", 2048, 2732)
            html = make_gallery(work, source, {"ipad": [2048, 2732]})

        self.assertIn('class="mode mode-native"', html)
        self.assertNotIn('class="mode mode-promotional"', html)

    def test_changing_style_invalidates_a_confirmed_code(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            source = write_png(work / "phone.png", 1170, 2532)
            html = make_gallery(work, source, {"iphone": [1290, 2796]})

        invalidation = re.search(r"function invalidateSelection\(\) \{(.*?)\n    \}", html, re.S)
        self.assertIsNotNone(invalidation)
        self.assertIn("Not confirmed", invalidation.group(1))
        self.assertIn("copy.hidden = true", invalidation.group(1))
        self.assertIn("copy.disabled = true", invalidation.group(1))
        self.assertIn("input.addEventListener('change', invalidateSelection)", html)

    def test_copy_failure_asks_for_a_manual_copy(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            source = write_png(work / "phone.png", 1170, 2532)
            html = make_gallery(work, source, {"iphone": [1290, 2796]})

        copy_function = re.search(r"async function copyCode\(code\) \{(.*?)\n    \}", html, re.S)
        self.assertIsNotNone(copy_function)
        self.assertIn("return copied", copy_function.group(1))
        self.assertIn("Copy it manually", html)


if __name__ == "__main__":
    unittest.main()
