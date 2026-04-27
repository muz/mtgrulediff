"""
Diff two Magic Comprehensive Rules files parsed by parse_rules.py.

Usage:
    python diff_rules.py <old_rules_file> <new_rules_file> [--output path]

Output JSON shape:
{
  "old_effective_date": "...",
  "new_effective_date": "...",
  "summary": {
    "unchanged": int,
    "modified": int,
    "added": int,
    "removed": int,
    "renumbered": int,
    "renumbered_and_modified": int
  },
  "modified": [
    {"rule": "100.1", "old_text": "...", "new_text": "..."}
  ],
  "added": [
    {"rule": "123.4", "text": "..."}
  ],
  "removed": [
    {"rule": "456.7", "text": "..."}
  ],
  "renumbered": [
    {
      "old_rule": "100.1",
      "new_rule": "100.2",
      "similarity": 1.0,
      "old_text": "...",
      "new_text": "..."
    }
  ]
}
"""

import argparse
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

from parse_rules import parse_file


def normalize_text(text):
    # Collapsing whitespace improves similarity checks across line-wrap changes.
    return re.sub(r"\s+", " ", text).strip()


def similarity(a, b):
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def detect_renumberings(removed, added, threshold=0.96):
    """
    Greedily pair removed rules with added rules by text similarity.

    A high threshold favors precision over recall, reducing false-positive
    renumber matches where unrelated rules happen to be somewhat similar.
    """
    candidates = []

    for old_rule, old_text in removed.items():
        for new_rule, new_text in added.items():
            score = similarity(old_text, new_text)
            if score >= threshold:
                candidates.append((score, old_rule, new_rule))

    # Highest-confidence matches first.
    candidates.sort(reverse=True)

    used_old = set()
    used_new = set()
    renumbered = []

    for score, old_rule, new_rule in candidates:
        if old_rule in used_old or new_rule in used_new:
            continue

        used_old.add(old_rule)
        used_new.add(new_rule)
        renumbered.append(
            {
                "old_rule": old_rule,
                "new_rule": new_rule,
                "similarity": round(score, 6),
                "old_text": removed[old_rule],
                "new_text": added[new_rule],
            }
        )

    remaining_removed = {k: v for k, v in removed.items() if k not in used_old}
    remaining_added = {k: v for k, v in added.items() if k not in used_new}

    return renumbered, remaining_removed, remaining_added


def build_diff(old_path, new_path, renumber_threshold=0.96):
    old_data = parse_file(old_path)
    new_data = parse_file(new_path)

    old_rules = old_data["rules"]
    new_rules = new_data["rules"]

    old_keys = set(old_rules.keys())
    new_keys = set(new_rules.keys())

    common = old_keys & new_keys

    unchanged = []
    modified = []

    for rule in sorted(common):
        old_text = old_rules[rule]
        new_text = new_rules[rule]
        if normalize_text(old_text) == normalize_text(new_text):
            unchanged.append(rule)
        else:
            modified.append({"rule": rule, "old_text": old_text, "new_text": new_text})

    removed = {rule: old_rules[rule] for rule in sorted(old_keys - new_keys)}
    added = {rule: new_rules[rule] for rule in sorted(new_keys - old_keys)}

    renumbered, removed_after, added_after = detect_renumberings(
        removed, added, threshold=renumber_threshold
    )

    renumbered_only = [
        r for r in renumbered if normalize_text(r["old_text"]) == normalize_text(r["new_text"])
    ]
    renumbered_and_modified = [
        r for r in renumbered if normalize_text(r["old_text"]) != normalize_text(r["new_text"])
    ]

    result = {
        "old_file": str(Path(old_path).name),
        "new_file": str(Path(new_path).name),
        "old_effective_date": old_data["effective_date"],
        "new_effective_date": new_data["effective_date"],
        "summary": {
            "unchanged": len(unchanged),
            "modified": len(modified),
            "added": len(added_after),
            "removed": len(removed_after),
            "renumbered": len(renumbered_only),
            "renumbered_and_modified": len(renumbered_and_modified),
        },
        "modified": modified,
        "added": [{"rule": k, "text": v} for k, v in sorted(added_after.items())],
        "removed": [{"rule": k, "text": v} for k, v in sorted(removed_after.items())],
        "renumbered": sorted(renumbered, key=lambda r: (r["old_rule"], r["new_rule"])),
    }

    return result


def parse_args():
    parser = argparse.ArgumentParser(description="Diff two MTG Comprehensive Rules files")
    parser.add_argument("old_rules_file", help="Path to older rules text file")
    parser.add_argument("new_rules_file", help="Path to newer rules text file")
    parser.add_argument(
        "--output",
        "-o",
        help="Write JSON diff to this path (default: stdout)",
        default=None,
    )
    parser.add_argument(
        "--renumber-threshold",
        type=float,
        default=0.96,
        help="Similarity threshold for renumber detection (default: 0.96)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    diff = build_diff(
        args.old_rules_file,
        args.new_rules_file,
        renumber_threshold=args.renumber_threshold,
    )

    output = json.dumps(diff, indent=2)

    if args.output:
        Path(args.output).write_text(output + "\n", encoding="utf-8")
        print(f"Wrote diff JSON: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
