import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


PREVIEW_HTML = Path(__file__).parents[1] / "assets" / "preview.html"


class PreviewParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.elements: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.elements.append((tag, dict(attrs)))


class PreviewHtmlTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = PREVIEW_HTML.read_text()
        cls.parser = PreviewParser()
        cls.parser.feed(cls.source)

    def test_platform_buttons_drive_frame_geometry_labels_and_adaptation_badge(self) -> None:
        tabs = [attrs for tag, attrs in self.parser.elements if tag == "button" and "data-platform" in attrs]

        self.assertEqual(len(tabs), 4)
        self.assertTrue(all(tab.get("role") is None for tab in tabs))
        self.assertEqual([tab.get("aria-pressed") for tab in tabs], ["true", "false", "false", "false"])
        self.assertTrue(any(attrs.get("role") == "group" and attrs.get("aria-label") == "Preview platform" for _, attrs in self.parser.elements))
        self.assertEqual({tab.get("data-device") for tab in tabs}, {"iphone", "ipad", "android-phone", "android-tablet"})
        self.assertTrue(all(tab.get("data-frame") for tab in tabs))
        self.assertIn("true", {tab.get("data-adapted") for tab in tabs})
        self.assertIn('id="adapted-badge"', self.source)
        self.assertIn("preview.dataset.device = button.dataset.device", self.source)
        self.assertIn("label.textContent = button.dataset.frame", self.source)
        self.assertIn("document.querySelector('#adapted-badge').hidden = !adapted", self.source)
        self.assertIn('showPlatform(document.querySelector(\'[data-platform][aria-pressed="true"]\'))', self.source)
        for device in ("iphone", "ipad", "android-phone", "android-tablet"):
            self.assertRegex(self.source, rf'main\[data-device="{device}"\]')
        self.assertRegex(self.source, r'main\[data-device="ipad"\].*\.shot')

    def test_radio_change_invalidates_confirmed_code(self) -> None:
        copy_buttons = [attrs for tag, attrs in self.parser.elements if tag == "button" and attrs.get("id") == "copy"]

        self.assertEqual(len(copy_buttons), 1)
        self.assertIn("hidden", copy_buttons[0])
        self.assertIn("disabled", copy_buttons[0])
        invalidation = re.search(r"function invalidateSelection\(\) \{(.*?)\n    \}", self.source, re.S)
        self.assertIsNotNone(invalidation)
        self.assertIn("Not confirmed", invalidation.group(1))
        self.assertIn("copy.hidden = true", invalidation.group(1))
        self.assertIn("copy.disabled = true", invalidation.group(1))
        self.assertIn("document.querySelectorAll('[name=layout], [name=style]')", self.source)
        self.assertIn("input.addEventListener('change', invalidateSelection)", self.source)

    def test_copy_failure_returns_false_and_requests_manual_copy(self) -> None:
        copy_function = re.search(r"async function copyCode\(code\) \{(.*?)\n    \}", self.source, re.S)

        self.assertIsNotNone(copy_function)
        self.assertIn("return true", copy_function.group(1))
        self.assertIn("return copied", copy_function.group(1))
        self.assertIn("Copy it manually", self.source)


if __name__ == "__main__":
    unittest.main()
