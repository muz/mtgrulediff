"""
parse_rules.py — Parse a Magic: The Gathering Comprehensive Rules plain-text file.

Usage:
    python parse_rules.py <rules_file>

Outputs a JSON object with:
  - effective_date: string
  - rules: {rule_number: rule_text}
  - glossary: {term: definition}

File structure
--------------
The plain-text file has three major sections, in order:

  1. Preamble + Table of Contents
       Includes bare headings like "Glossary" and "Credits" as TOC entries.
  2. Rules body
       Numbered sections ("100. General") and individual rules ("100.1.", "100.1a").
  3. Glossary
       Term / definition pairs separated by blank lines.
  4. Credits
"""

import json
import re
import sys
from pathlib import Path

# Matches rule lines like:
#   "100.1. These Magic rules..."
#   "100.1a A two-player game..."
#   "702.19c Some text..."
RULE_RE = re.compile(r'^(\d+\.\d+[a-z]*)\.?\s{1,4}(\S.+)')


def find_section_bounds(lines):
    """
    Return (body_start, glossary_start, credits_start) as line indices.

    The file has a Table of Contents near the top that contains bare "Glossary"
    and "Credits" entries before the actual rules body starts. We detect which
    "Credits" line is the TOC entry vs. the real Credits section by checking
    whether it is followed by a line starting with "1." (body) or attribution
    text (real Credits).
    """
    body_start = 0
    glossary_start = len(lines)
    credits_start = len(lines)

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped == 'Credits':
            # Peek at the next non-blank line
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and re.match(r'^\d+\.', lines[j].strip()):
                # Followed by a numbered section — this is the TOC Credits
                body_start = i + 1
            else:
                # This is the real Credits section at the end
                credits_start = i
                break

        elif stripped == 'Glossary' and body_start > 0:
            # The first "Glossary" after body_start is the real glossary
            glossary_start = i

    return body_start, glossary_start, credits_start


def parse_effective_date(lines):
    for line in lines[:10]:
        m = re.search(r'effective as of (.+?)\.', line, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def parse_rules(lines, body_start, glossary_start):
    """Return {rule_number: rule_text} for all numbered rules in the body."""
    rules = {}
    for line in lines[body_start:glossary_start]:
        m = RULE_RE.match(line)
        if m:
            rules[m.group(1)] = m.group(2).strip()
    return rules


def parse_glossary(lines, glossary_start, credits_start):
    """
    Return {term: definition} for all glossary entries.

    Glossary format:
        Term
        Definition text, possibly multiple sentences.

        Next Term
        ...
    """
    glossary = {}
    term = None
    defn_lines = []

    for line in lines[glossary_start + 1 : credits_start]:
        stripped = line.strip()

        if not stripped:
            if term and defn_lines:
                glossary[term] = ' '.join(defn_lines)
                term = None
                defn_lines = []
            continue

        if term is None:
            term = stripped
        else:
            defn_lines.append(stripped)

    # Flush last entry
    if term and defn_lines:
        glossary[term] = ' '.join(defn_lines)

    return glossary


def parse_file(filepath):
    text = Path(filepath).read_text(encoding='utf-8')
    lines = text.splitlines()

    body_start, glossary_start, credits_start = find_section_bounds(lines)

    return {
        'effective_date': parse_effective_date(lines),
        'rules': parse_rules(lines, body_start, glossary_start),
        'glossary': parse_glossary(lines, glossary_start, credits_start),
    }


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} <rules_file>', file=sys.stderr)
        sys.exit(1)

    result = parse_file(sys.argv[1])
    print(f"Effective date : {result['effective_date']}", file=sys.stderr)
    print(f"Rules parsed   : {len(result['rules'])}", file=sys.stderr)
    print(f"Glossary terms : {len(result['glossary'])}", file=sys.stderr)
    print(json.dumps(result, indent=2))
