"""Report what each screenshot is and how it may be presented per target.

    python3 scripts/classify.py shot.png ... [--target iphone --target ipad]
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analyzer import ScreenshotAnalyzer, SetAnalyzer
from devices import PLATFORMS, TargetDeviceResolver


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("screenshots", nargs="+", type=Path)
    parser.add_argument("--target", action="append", choices=PLATFORMS, default=None)
    args = parser.parse_args(argv)
    targets = args.target or list(PLATFORMS)

    analyzer = ScreenshotAnalyzer()
    try:
        analyses = [analyzer.analyze(path) for path in args.screenshots]
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1

    sequenced = SetAnalyzer.sequence(analyses)
    report = {
        "set": SetAnalyzer.summarize(analyses),
        "screenshots": [
            {
                "filename": analysis["filename"],
                "dimensions": [analysis["width"], analysis["height"]],
                "orientation": analysis["orientation"],
                "aspect": analysis["aspect"],
                "device_class": analysis["device_class"],
                "role": analysis["role"],
                "intent": analysis["intent"],
                "sequence_position": sequenced[index]["position"],
                "targets": {
                    target: TargetDeviceResolver.resolve(analysis, target)["presentation"]
                    for target in targets
                },
            }
            for index, analysis in enumerate(analyses)
        ],
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
