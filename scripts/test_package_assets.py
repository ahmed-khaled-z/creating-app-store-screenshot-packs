import contextlib
import io
import importlib
import json
import os
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS))
package_assets = importlib.import_module("package_assets")

PLATFORMS = ("iphone", "ipad", "android-phone", "android-tablet")


def png(path: Path, width: int, height: int) -> None:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    chunk = lambda kind, data: struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", b"x") + chunk(b"IEND", b""))


class PackageAssetsTest(unittest.TestCase):
    def prepare(self, root: Path, missing: str | None = None) -> None:
        png(root.parent / "supplied-dashboard.png", 50, 100)
        for platform in PLATFORMS:
            if platform != missing:
                folder = root / platform
                folder.mkdir()
                png(folder / "01.png", 100, 200)

    def args(self, staging: Path, output: Path) -> list[str]:
        result = [str(staging), str(output), "--layout", "L2", "--style", "S1", "--language", "en", "--adapted", "ipad"]
        for platform in PLATFORMS:
            result.extend(("--size", f"{platform}=100x200"))
            result.extend(("--source", f"{platform}/01.png={staging.parent / 'supplied-dashboard.png'}"))
        return result

    def invoke(self, args: list[str]) -> int:
        with contextlib.redirect_stderr(io.StringIO()):
            try:
                return package_assets.main(args)
            except SystemExit as error:
                return error.code

    def test_packages_four_platform_folders_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging, output = root / "staging", root / "assets.zip"
            staging.mkdir()
            self.prepare(staging)

            self.assertEqual(self.invoke(self.args(staging, output)), 0)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(
                    archive.namelist(),
                    [
                        "app-store-assets/manifest.json",
                        "app-store-assets/android-phone/01.png",
                        "app-store-assets/android-tablet/01.png",
                        "app-store-assets/ipad/01.png",
                        "app-store-assets/iphone/01.png",
                    ],
                )
                manifest = json.loads(archive.read("app-store-assets/manifest.json"))
                self.assertEqual(archive.read("app-store-assets/iphone/01.png"), (staging / "iphone/01.png").read_bytes())
            self.assertEqual(manifest["layout"], "L2")
            self.assertEqual(manifest["adapted"], ["ipad"])
            self.assertEqual(manifest["platforms"]["iphone"][0], {
                "source": str(root / "supplied-dashboard.png"),
                "staged": "iphone/01.png",
                "output": "app-store-assets/iphone/01.png",
                "dimensions": [100, 200],
            })

    def test_rejects_incomplete_or_ambiguous_source_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging, output = root / "staging", root / "assets.zip"
            staging.mkdir()
            self.prepare(staging)
            valid = self.args(staging, output)
            for mapping in (None, "android-tablet/01.png=", "android-tablet/01.png=missing.png",
                            f"android-tablet/01.png={root}", "invalid", f"iphone/02.png={root / 'supplied-dashboard.png'}"):
                with self.subTest(mapping=mapping):
                    args = valid[:-2]
                    if mapping is not None:
                        args += ["--source", mapping]
                    self.assertNotEqual(self.invoke(args), 0)
                    self.assertFalse(output.exists())
            for mapping in (valid[-1], f"iphone/02.png={root / 'supplied-dashboard.png'}"):
                with self.subTest(extra_mapping=mapping):
                    self.assertNotEqual(self.invoke(valid + ["--source", mapping]), 0)
                    self.assertFalse(output.exists())
            without_sources = valid[:10]
            for platform in PLATFORMS:
                without_sources += ["--size", f"{platform}=100x200"]
            self.assertNotEqual(self.invoke(without_sources), 0)
            self.assertFalse(output.exists())

    def test_repeat_build_is_byte_identical_after_source_mtimes_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging, output = root / "staging", root / "assets.zip"
            staging.mkdir()
            self.prepare(staging)
            self.assertEqual(self.invoke(self.args(staging, output)), 0)
            first = output.read_bytes()
            for source in [root / "supplied-dashboard.png", *staging.glob("*/*.png")]:
                os.utime(source, (1800000000, 1800000000))
            self.assertEqual(self.invoke(self.args(staging, output)), 0)
            self.assertEqual(output.read_bytes(), first)

    def test_rejects_missing_platform_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging, output = root / "staging", root / "assets.zip"
            staging.mkdir()
            self.prepare(staging, missing="ipad")

            self.assertNotEqual(self.invoke(self.args(staging, output)), 0)
            self.assertFalse(output.exists())

    def test_rejects_dimensions_outside_platform_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging, output = root / "staging", root / "assets.zip"
            staging.mkdir()
            self.prepare(staging)
            png(staging / "iphone" / "01.png", 101, 200)

            self.assertNotEqual(self.invoke(self.args(staging, output)), 0)
            self.assertFalse(output.exists())

    def test_rejects_non_numbered_png_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging, output = root / "staging", root / "assets.zip"
            staging.mkdir()
            self.prepare(staging)
            (staging / "iphone" / "01.png").rename(staging / "iphone" / "hero.png")

            self.assertNotEqual(self.invoke(self.args(staging, output)), 0)
            self.assertFalse(output.exists())

    def test_rejects_extra_staging_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging, output = root / "staging", root / "assets.zip"
            staging.mkdir()
            self.prepare(staging)
            (staging / "notes.txt").write_text("extra")

            self.assertNotEqual(self.invoke(self.args(staging, output)), 0)
            self.assertFalse(output.exists())

    def test_rejects_png_with_invalid_ihdr_crc(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            staging, output = root / "staging", root / "assets.zip"
            staging.mkdir()
            self.prepare(staging)
            image = staging / "iphone" / "01.png"
            data = image.read_bytes()
            image.write_bytes(data[:32] + bytes([data[32] ^ 1]) + data[33:])

            self.assertNotEqual(self.invoke(self.args(staging, output)), 0)
            self.assertFalse(output.exists())

    def test_rejects_oversized_png_chunk_without_reading_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "01.png"
            png(image, 100, 200)
            data = image.read_bytes()
            image.write_bytes(data[:-12] + struct.pack(">I4s", 0xFFFFFFFF, b"IDAT"))

            class LimitedReader(io.BytesIO):
                def read(self, size: int = -1) -> bytes:
                    if size > 1024:
                        raise AssertionError("oversized PNG read")
                    return super().read(size)

            with mock.patch.object(Path, "open", return_value=LimitedReader(image.read_bytes())):
                with self.assertRaises(ValueError):
                    package_assets.png_size(image)


if __name__ == "__main__":
    unittest.main()
