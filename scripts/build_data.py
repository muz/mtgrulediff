"""
Build pre-generated JSON data for static site generation.

Usage:
    python build_data.py
    python build_data.py --rules-dir rules --out-dir docs/data

Creates:
  - <out-dir>/releases.json
  - <out-dir>/diffs/<old_date>_to_<new_date>.json (one per adjacent pair)
"""

import argparse
import json
import re
from pathlib import Path

from diff_rules import build_diff
from parse_rules import parse_file

FILENAME_DATE_RE = re.compile(r"(\d{8})")


def extract_filename_date(path):
    m = FILENAME_DATE_RE.search(path.name)
    if not m:
        raise ValueError(f"Could not find YYYYMMDD date in filename: {path.name}")
    return m.group(1)


def discover_rule_files(rules_dir):
    files = [p for p in Path(rules_dir).glob("*.txt") if p.is_file()]
    if not files:
        raise ValueError(f"No .txt files found in {rules_dir}")
    files.sort(key=extract_filename_date)
    return files


def build_release_metadata(rule_files):
    releases = []
    for path in rule_files:
        parsed = parse_file(str(path))
        releases.append(
            {
                "source_file": path.name,
                "file_date": extract_filename_date(path),
                "effective_date": parsed["effective_date"],
                "rule_count": len(parsed["rules"]),
                "glossary_count": len(parsed["glossary"]),
            }
        )
    return releases


def main():
    parser = argparse.ArgumentParser(description="Build JSON artifacts for MTG rules diff site")
    parser.add_argument("--rules-dir", default="rules", help="Directory containing rules text files")
    parser.add_argument("--out-dir", default="docs/data", help="Directory to write JSON artifacts")
    parser.add_argument(
        "--renumber-threshold",
        type=float,
        default=0.96,
        help="Similarity threshold for renumber detection (default: 0.96)",
    )
    args = parser.parse_args()

    rule_files = discover_rule_files(args.rules_dir)

    out_dir = Path(args.out_dir)
    diffs_dir = out_dir / "diffs"
    diffs_dir.mkdir(parents=True, exist_ok=True)

    releases = build_release_metadata(rule_files)

    for i in range(len(rule_files) - 1):
        old_path = rule_files[i]
        new_path = rule_files[i + 1]

        old_date = extract_filename_date(old_path)
        new_date = extract_filename_date(new_path)

        diff = build_diff(
            str(old_path),
            str(new_path),
            renumber_threshold=args.renumber_threshold,
        )

        out_path = diffs_dir / f"{old_date}_to_{new_date}.json"
        out_path.write_text(json.dumps(diff, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {out_path}")

    releases_path = out_dir / "releases.json"
    releases_path.write_text(json.dumps(releases, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {releases_path}")


if __name__ == "__main__":
    main()
