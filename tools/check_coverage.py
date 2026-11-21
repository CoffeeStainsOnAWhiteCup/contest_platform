"""Check each core module independently using coverage.py JSON output."""

import json
import sys
from pathlib import Path


def main() -> int:
    report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    failed = False
    for module in ("auth", "rating", "judge"):
        summaries = [file["summary"] for path, file in report["files"].items()
                     if f"/modules/{module}/" in "/" + path.replace("\\", "/")]
        total = sum(s["num_statements"] for s in summaries)
        hits = sum(s["covered_lines"] for s in summaries)
        percent = 100 * hits / total if total else 0
        print(f"{module}: {hits}/{total} lines ({percent:.1f}%)")
        failed |= percent < 70
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
