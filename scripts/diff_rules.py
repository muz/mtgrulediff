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


def rule_sort_key(rule):
    """Numeric sort key for rule numbers like '100.1', '100.1a', '702.19c'."""
    m = re.match(r"^(\d+)(?:\.(\d+)([a-z]*))?", str(rule))
    if not m:
        return (999999, 0, "")
    main = int(m.group(1))
    sub = int(m.group(2)) if m.group(2) else 0
    suffix = m.group(3) or ""
    return (main, sub, suffix)


def similarity(a, b):
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


_RULE_REF_RE = re.compile(r'\b(\d+\.\d+[a-z]*)\b')
# Matches bare section refs preceded by "rule" or "rules", e.g. "see rule 726,"
_RULE_SECTION_REF_RE = re.compile(r'\b(rules?\s+)(\d+)\b(?!\.)', re.IGNORECASE)


def is_reference_only_change(old_text, new_text, renumber_map, section_renumber_map):
    """Return True if old_text and new_text differ only in rule-number references
    that are all accounted for by the supplied renumber maps (sub-rule and section).
    """
    predicted = _RULE_REF_RE.sub(
        lambda m: renumber_map.get(m.group(1), m.group(1)), old_text
    )
    predicted = _RULE_SECTION_REF_RE.sub(
        lambda m: m.group(1) + section_renumber_map.get(m.group(2), m.group(2)), predicted
    )
    return normalize_text(predicted) == normalize_text(new_text)


def build_section_renumber_map(renumber_map):
    """Infer section-level renames from sub-rule renumberings.
    If all observed sub-rules of section N unanimously map to section M,
    emit N → M in the returned dict.
    """
    from collections import defaultdict
    votes = defaultdict(lambda: defaultdict(int))
    for old_r, new_r in renumber_map.items():
        old_sec = old_r.split(".")[0]
        new_sec = new_r.split(".")[0]
        if old_sec != new_sec:
            votes[old_sec][new_sec] += 1

    result = {}
    for old_sec, counts in votes.items():
        best_new = max(counts, key=counts.__getitem__)
        if counts[best_new] == sum(counts.values()):  # unanimous
            result[old_sec] = best_new
    return result


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

    # Rules where the same key appears in both versions but the text has very low
    # similarity are almost certainly a section-shift collision — an entirely
    # different rule happened to land on the same number.  Pull these out of the
    # "modified" bucket and feed them into the renumber-detection pool instead,
    # so that the actual textual matches can be found across the shift boundary.
    COLLISION_THRESHOLD = 0.45
    true_modified = []
    collision_removed = {}  # old-key → old_text
    collision_added = {}    # new-key → new_text
    for entry in modified:
        score = similarity(entry["old_text"], entry["new_text"])
        if score < COLLISION_THRESHOLD:
            collision_removed[entry["rule"]] = entry["old_text"]
            collision_added[entry["rule"]] = entry["new_text"]
        else:
            true_modified.append(entry)
    modified = true_modified

    removed = {rule: old_rules[rule] for rule in sorted(old_keys - new_keys)}
    added = {rule: new_rules[rule] for rule in sorted(new_keys - old_keys)}

    # Merge collision candidates with genuinely key-absent rules for detection.
    removed_pool = {**removed, **collision_removed}
    added_pool = {**added, **collision_added}

    renumbered, remaining_removed_pool, remaining_added_pool = detect_renumberings(
        removed_pool, added_pool, threshold=renumber_threshold
    )

    # Split remaining back into true-removed (key absent) and collision leftovers.
    # Collision leftovers that weren't matched by renumber detection are true
    # modifications after all — reinstate them in the modified list.
    removed_after = {k: v for k, v in remaining_removed_pool.items() if k not in collision_removed}
    added_after = {k: v for k, v in remaining_added_pool.items() if k not in collision_added}

    unmatched_collision_old = {k: v for k, v in remaining_removed_pool.items() if k in collision_removed}
    unmatched_collision_new = {k: v for k, v in remaining_added_pool.items() if k in collision_added}
    # Re-pair unmatched collision rules that share the same key back into modified.
    for key in set(unmatched_collision_old) & set(unmatched_collision_new):
        modified.append({
            "rule": key,
            "old_text": unmatched_collision_old[key],
            "new_text": unmatched_collision_new[key],
        })
    # Any that lost their pair entirely become true removed/added.
    for key, text in unmatched_collision_old.items():
        if key not in unmatched_collision_new:
            removed_after[key] = text
    for key, text in unmatched_collision_new.items():
        if key not in unmatched_collision_old:
            added_after[key] = text
    modified.sort(key=lambda r: rule_sort_key(r["rule"]))

    # Displacement detection: handles section shifts where the structural
    # similarity between old and new content at the same key exceeds the
    # collision threshold (so collision detection didn't fire), but a
    # key-absent removed rule has near-identical text to the modified
    # rule's new content.  In that case the removed rule was actually
    # renamed to that key, and the old occupant is truly removed.
    disp_candidates = []
    for old_key, old_text in list(removed_after.items()):
        for mod_entry in modified:
            score = similarity(old_text, mod_entry["new_text"])
            if score >= renumber_threshold:
                disp_candidates.append((score, old_key, mod_entry["rule"], mod_entry))
    disp_candidates.sort(reverse=True)
    used_disp_old: set = set()
    used_disp_mod: set = set()
    disp_keys_removed: set = set()
    disp_keys_mod: set = set()
    for score, old_key, mod_key, mod_entry in disp_candidates:
        if old_key in used_disp_old or mod_key in used_disp_mod:
            continue
        used_disp_old.add(old_key)
        used_disp_mod.add(mod_key)
        disp_keys_removed.add(old_key)
        disp_keys_mod.add(mod_key)
        renumbered.append({
            "old_rule": old_key,
            "new_rule": mod_key,
            "similarity": score,
            "old_text": removed_after[old_key],
            "new_text": mod_entry["new_text"],
        })
        # The old occupant at mod_key is now truly removed.
        removed_after[mod_key] = mod_entry["old_text"]
    for key in disp_keys_removed:
        del removed_after[key]
    modified = [e for e in modified if e["rule"] not in disp_keys_mod]
    modified.sort(key=lambda r: rule_sort_key(r["rule"]))

    # Build renumber maps first so they can be used in the split below.
    renumber_map = {r["old_rule"]: r["new_rule"] for r in renumbered}
    section_renumber_map = build_section_renumber_map(renumber_map)

    renumbered_only = [
        r for r in renumbered
        if normalize_text(r["old_text"]) == normalize_text(r["new_text"])
        or is_reference_only_change(r["old_text"], r["new_text"], renumber_map, section_renumber_map)
    ]
    renumbered_and_modified = [
        r for r in renumbered
        if normalize_text(r["old_text"]) != normalize_text(r["new_text"])
        and not is_reference_only_change(r["old_text"], r["new_text"], renumber_map, section_renumber_map)
    ]

    # Detect modified rules whose only change is rule-number references that
    # map directly to a known renumbering.  These are really just reference
    # maintenance — no semantic change — so we surface them like renumberings.
    true_modified = []
    ref_renumbered = []
    for entry in modified:
        if is_reference_only_change(entry["old_text"], entry["new_text"],
                                    renumber_map, section_renumber_map):
            ref_renumbered.append(entry)
        else:
            true_modified.append(entry)
    modified = true_modified
    ref_renumbered_lookup = {r["rule"]: r for r in ref_renumbered}

    # Build ordered list of all rules for the document-view HTML page.
    modified_lookup = {r["rule"]: r for r in modified}
    renumbered_new_lookup = {r["new_rule"]: r for r in renumbered}
    added_after_set = set(added_after.keys())

    all_entries = []
    for rule_id, text in new_rules.items():
        if rule_id in modified_lookup:
            r = modified_lookup[rule_id]
            all_entries.append({
                "rule": rule_id,
                "status": "modified",
                "old_text": r["old_text"],
                "new_text": r["new_text"],
            })
        elif rule_id in ref_renumbered_lookup:
            r = ref_renumbered_lookup[rule_id]
            all_entries.append({
                "rule": rule_id,
                "status": "reference_renumbered",
                "old_text": r["old_text"],
                "new_text": r["new_text"],
            })
        elif rule_id in renumbered_new_lookup:
            r = renumbered_new_lookup[rule_id]
            is_mod = normalize_text(r["old_text"]) != normalize_text(r["new_text"])
            if is_mod and is_reference_only_change(r["old_text"], r["new_text"],
                                                   renumber_map, section_renumber_map):
                is_mod = False
            all_entries.append({
                "rule": rule_id,
                "status": "renumbered_and_modified" if is_mod else "renumbered",
                "old_rule": r["old_rule"],
                "old_text": r["old_text"],
                "new_text": r["new_text"],
                "similarity": r["similarity"],
            })
        elif rule_id in added_after_set:
            all_entries.append({"rule": rule_id, "status": "added", "text": text})
        else:
            all_entries.append({"rule": rule_id, "status": "unchanged", "text": text})

    for rule_id, text in removed_after.items():
        all_entries.append({"rule": rule_id, "status": "removed", "text": text})

    all_entries.sort(key=lambda e: rule_sort_key(e["rule"]))

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
            "reference_renumbered": len(ref_renumbered),
        },
        "modified": modified,
        "reference_renumbered": ref_renumbered,
        "added": [{"rule": k, "text": v} for k, v in sorted(added_after.items())],
        "removed": [{"rule": k, "text": v} for k, v in sorted(removed_after.items())],
        "renumbered": sorted(renumbered, key=lambda r: (r["old_rule"], r["new_rule"])),
        "all_rules_ordered": all_entries,
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
