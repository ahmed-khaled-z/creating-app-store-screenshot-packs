import argparse
import json
import struct
import sys
import zipfile
import zlib
from pathlib import Path


PLATFORMS = ("iphone", "ipad", "android-phone", "android-tablet")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_size(path: Path) -> tuple[int, int]:
    def invalid() -> ValueError:
        return ValueError(f"malformed PNG: {path}")

    file_size = path.stat().st_size
    with path.open("rb") as image:
        if image.read(8) != PNG_SIGNATURE:
            raise invalid()
        header = image.read(8)
        if len(header) != 8:
            raise invalid()
        length, kind = struct.unpack(">I4s", header)
        if length != 13 or kind != b"IHDR":
            raise invalid()
        data, checksum = image.read(length), image.read(4)
        if len(data) != length or len(checksum) != 4 or zlib.crc32(kind + data) != struct.unpack(">I", checksum)[0]:
            raise invalid()
        width, height = struct.unpack(">II", data[:8])
        if not width or not height:
            raise invalid()
        has_idat = False
        while True:
            header = image.read(8)
            if len(header) != 8:
                raise invalid()
            length, kind = struct.unpack(">I4s", header)
            if length + 4 > file_size - image.tell():
                raise invalid()
            data, checksum = image.read(length), image.read(4)
            if len(data) != length or len(checksum) != 4 or zlib.crc32(kind + data) != struct.unpack(">I", checksum)[0]:
                raise invalid()
            if kind == b"IHDR":
                raise invalid()
            if kind == b"IDAT":
                has_idat = True
            if kind == b"IEND":
                if length or not has_idat or image.read(1):
                    raise invalid()
                return width, height


def collect(staging: Path, allowed: dict[str, set[tuple[int, int]]]) -> dict[str, list[dict]]:
    if {entry.name for entry in staging.iterdir()} != set(PLATFORMS):
        raise ValueError("staging must contain exactly the four platform folders")
    files: dict[str, list[dict]] = {}
    for platform in sorted(PLATFORMS):
        folder = staging / platform
        if not folder.is_dir():
            raise ValueError(f"missing platform folder: {folder}")
        entries = sorted(folder.iterdir(), key=lambda path: path.name)
        if not entries:
            raise ValueError(f"empty platform folder: {folder}")
        files[platform] = []
        for path in entries:
            if not path.is_file() or path.suffix != ".png":
                raise ValueError(f"non-PNG file: {path}")
            if not path.stem.split("-", 1)[0].isdigit():
                raise ValueError(f"non-numbered PNG file: {path}")
            size = png_size(path)
            if size not in allowed[platform]:
                raise ValueError(f"disallowed dimensions for {path}: {size[0]}x{size[1]}")
            files[platform].append({"filename": path.name, "width": size[0], "height": size[1]})
    return files


def build_manifest(files: dict, layout: str, style: str, language: str, adapted: set[str], sources: dict[str, str]) -> dict:
    platforms = {}
    for platform in sorted(files):
        platforms[platform] = [
            {
                "source": sources[f"{platform}/{item['filename']}"],
                "staged": f"{platform}/{item['filename']}",
                "output": f"app-store-assets/{platform}/{item['filename']}",
                "dimensions": [item["width"], item["height"]],
            }
            for item in files[platform]
        ]
    return {
        "layout": layout,
        "style": style,
        "language": language,
        "adapted": sorted(adapted),
        "platforms": platforms,
    }


def package(staging: Path, output: Path, manifest: dict) -> None:
    def write(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, data)

    with zipfile.ZipFile(output, "w") as archive:
        write(archive, "app-store-assets/manifest.json", json.dumps(manifest, indent=2, sort_keys=True).encode() + b"\n")
        for platform in sorted(manifest["platforms"]):
            for item in manifest["platforms"][platform]:
                write(archive, item["output"], (staging / item["staged"]).read_bytes())


def parse_size(value: str) -> tuple[str, tuple[int, int]]:
    try:
        platform, dimensions = value.split("=", 1)
        width, height = (int(part) for part in dimensions.split("x", 1))
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid size: {value}") from error
    if platform not in PLATFORMS or width < 1 or height < 1:
        raise argparse.ArgumentTypeError(f"invalid size: {value}")
    return platform, (width, height)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("staging_dir", type=Path)
    parser.add_argument("output_zip", type=Path)
    parser.add_argument("--layout", required=True)
    parser.add_argument("--style", required=True)
    parser.add_argument("--language", required=True)
    parser.add_argument("--size", action="append", type=parse_size, required=True)
    parser.add_argument("--source", action="append", required=True, metavar="PLATFORM/FILE.PNG=ORIGINAL_PATH",
                        help="one original supplied screenshot path per staged output; relative paths use the current directory")
    parser.add_argument("--adapted", action="append", default=[])
    args = parser.parse_args(argv)
    if set(args.adapted) - set(PLATFORMS):
        parser.error("--adapted must name a supported platform")

    allowed: dict[str, set[tuple[int, int]]] = {platform: set() for platform in PLATFORMS}
    for platform, size in args.size:
        allowed[platform].add(size)
    if any(not sizes for sizes in allowed.values()):
        parser.error("--size is required for every platform")

    try:
        files = collect(args.staging_dir, allowed)
        sources = {}
        for mapping in args.source:
            staged, separator, original = mapping.partition("=")
            if not separator or not original or staged in sources:
                raise ValueError(f"invalid or duplicate --source mapping: {mapping}")
            if not Path(original).is_file():
                raise ValueError(f"original screenshot is not a file: {original}")
            sources[staged] = original
        expected = {f"{platform}/{item['filename']}" for platform in files for item in files[platform]}
        if set(sources) != expected:
            raise ValueError("--source must map every staged platform/filename exactly once, with no extra outputs")
        package(args.staging_dir, args.output_zip, build_manifest(files, args.layout, args.style, args.language, set(args.adapted), sources))
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
