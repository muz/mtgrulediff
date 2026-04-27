"""Build static HTML pages from pre-generated MTG rules diff JSON.

Usage:
    python build_site.py
    python build_site.py --data-dir html/data --out-dir html
"""

import argparse
import html
import json
import re
from difflib import SequenceMatcher
from pathlib import Path


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_text(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content, encoding="utf-8")


def slugify(text):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return slug or "item"


def tokenize_with_ws(text):
    # Keep whitespace tokens so reconstructed text remains human-readable.
    return re.findall(r"\w+|[^\w\s]|\s+", text)


def render_highlighted_diff(old_text, new_text):
    old_tokens = tokenize_with_ws(old_text)
    new_tokens = tokenize_with_ws(new_text)

    sm = SequenceMatcher(a=old_tokens, b=new_tokens)
    old_out = []
    new_out = []

    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            old_out.extend(html.escape(t) for t in old_tokens[i1:i2])
            new_out.extend(html.escape(t) for t in new_tokens[j1:j2])
        elif op == "delete":
            old_chunk = "".join(html.escape(t) for t in old_tokens[i1:i2])
            old_out.append(f'<span class="tok-del">{old_chunk}</span>')
        elif op == "insert":
            new_chunk = "".join(html.escape(t) for t in new_tokens[j1:j2])
            new_out.append(f'<span class="tok-ins">{new_chunk}</span>')
        elif op == "replace":
            old_chunk = "".join(html.escape(t) for t in old_tokens[i1:i2])
            new_chunk = "".join(html.escape(t) for t in new_tokens[j1:j2])
            old_out.append(f'<span class="tok-del">{old_chunk}</span>')
            new_out.append(f'<span class="tok-ins">{new_chunk}</span>')

    return "".join(old_out), "".join(new_out)


def render_summary_cards(summary):
    order = [
        ("unchanged", "Unchanged"),
        ("modified", "Modified"),
        ("added", "Added"),
        ("removed", "Removed"),
        ("renumbered", "Renumbered"),
        ("renumbered_and_modified", "Renumbered + Modified"),
        ("reference_renumbered", "Refs Updated"),
    ]
    cards = []
    for key, label in order:
        cards.append(
            f"""
            <div class=\"stat-card\">
              <div class=\"stat-label\">{label}</div>
              <div class=\"stat-value\">{summary.get(key, 0)}</div>
            </div>
            """.strip()
        )
    return "\n".join(cards)


def render_rule_details(items, mode):
    if not items:
        return "<p class=\"muted\">No entries in this section.</p>"

    blocks = []
    for item in items:
        if mode == "modified":
            rule = item["rule"]
            old_html, new_html = render_highlighted_diff(item["old_text"], item["new_text"])
            blocks.append(
                f"""
                <details class=\"rule-detail\">
                  <summary><span class=\"pill\">{html.escape(rule)}</span> Modified text</summary>
                  <div class=\"diff-grid\">
                    <div>
                      <h4>Old</h4>
                      <p class=\"rule-text\">{old_html}</p>
                    </div>
                    <div>
                      <h4>New</h4>
                      <p class=\"rule-text\">{new_html}</p>
                    </div>
                  </div>
                </details>
                """.strip()
            )
        elif mode == "added":
            blocks.append(
                f"""
                <details class=\"rule-detail\">
                  <summary><span class=\"pill added\">{html.escape(item['rule'])}</span> Added rule</summary>
                  <p class=\"rule-text\">{html.escape(item['text'])}</p>
                </details>
                """.strip()
            )
        elif mode == "removed":
            blocks.append(
                f"""
                <details class=\"rule-detail\">
                  <summary><span class=\"pill removed\">{html.escape(item['rule'])}</span> Removed rule</summary>
                  <p class=\"rule-text\">{html.escape(item['text'])}</p>
                </details>
                """.strip()
            )
        elif mode == "renumbered":
            old_html, new_html = render_highlighted_diff(item["old_text"], item["new_text"])
            blocks.append(
                f"""
                <details class=\"rule-detail\">
                  <summary>
                    <span class=\"pill removed\">{html.escape(item['old_rule'])}</span>
                    <span class=\"arrow\">→</span>
                    <span class=\"pill added\">{html.escape(item['new_rule'])}</span>
                    <span class=\"muted\">similarity {item['similarity']:.3f}</span>
                  </summary>
                  <div class=\"diff-grid\">
                    <div>
                      <h4>Old text</h4>
                      <p class=\"rule-text\">{old_html}</p>
                    </div>
                    <div>
                      <h4>New text</h4>
                      <p class=\"rule-text\">{new_html}</p>
                    </div>
                  </div>
                </details>
                """.strip()
            )

    return "\n".join(blocks)


def page_template(title, subtitle, content, root_rel):
    return f"""<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>{html.escape(title)}</title>
    <link rel=\"stylesheet\" href=\"{root_rel}assets/styles.css\" />
  </head>
  <body>
    <div class=\"bg-orb orb-a\"></div>
    <div class=\"bg-orb orb-b\"></div>
    <header class=\"site-header\">
      <a class=\"brand\" href=\"{root_rel}index.html\">MTG Rule Diff</a>
      <p class=\"subtitle\">{html.escape(subtitle)}</p>
    </header>
    <main class=\"container\">
      {content}
    </main>
    <script>
      (function () {{
        function updateScrollMargin() {{
          var nav = document.querySelector('.change-nav');
          if (!nav) return;
          var h = Math.round(nav.getBoundingClientRect().height) + 16;
          var style = document.getElementById('scroll-margin-style');
          if (!style) {{
            style = document.createElement('style');
            style.id = 'scroll-margin-style';
            document.head.appendChild(style);
          }}
          style.textContent = '.doc-rule, .renumber-group {{ scroll-margin-top: ' + h + 'px; }}';
        }}
        updateScrollMargin();
        window.addEventListener('resize', updateScrollMargin);
      }})();
    </script>
  </body>
</html>
"""


def render_change_nav(nav_items):
    if not nav_items:
        return ""

    STATUS_CLASS = {
        "modified": "modified",
        "added": "added",
        "removed": "removed",
        "renumbered": "renumbered",
        "renumbered_and_modified": "renumbered",
    }

    links = []
    for status, entry, anchor_id in nav_items:
        if status == "renumbered_group":
            fo, lo = html.escape(entry['first_old']), html.escape(entry['last_old'])
            fn, ln = html.escape(entry['first_new']), html.escape(entry['last_new'])
            if fo == fn and lo == ln:
                label = f"{fn}\u2013{ln} (refs)" if fn != ln else f"{fn} (refs)"
            else:
                label = f"{fo}\u2013{lo} \u2192 {fn}\u2013{ln}"
            links.append(f'<a class="count-pill renumbered" href="#{anchor_id}">{label}</a>')
        elif status == "added_group":
            fn, ln = html.escape(entry['first']), html.escape(entry['last'])
            label = f"+{fn}\u2013{ln}" if fn != ln else f"+{fn}"
            links.append(f'<a class="count-pill added" href="#{anchor_id}">{label}</a>')
        else:
            pill_class = STATUS_CLASS.get(status, "modified")
            if status in ("renumbered", "renumbered_and_modified"):
                label = f"{html.escape(entry['old_rule'])} → {html.escape(entry['rule'])}"
            else:
                label = html.escape(entry["rule"])
            links.append(f'<a class="count-pill {pill_class}" href="#{anchor_id}">{label}</a>')

    return f"""
    <div class="change-nav">
      <div class="change-nav-title">Navigate {len(nav_items)} changes</div>
      <div class="change-nav-links">{"".join(links)}</div>
    </div>
    """.strip()


def render_unchanged_group(rules):
    count = len(rules)
    first_rule = html.escape(rules[0]["rule"])
    last_rule = html.escape(rules[-1]["rule"])
    range_hint = f"{first_rule} — {last_rule}" if count > 1 else first_rule

    rows = []
    for entry in rules:
        rows.append(
            f'<div class="doc-rule unchanged">'
            f'<span class="doc-rule-num">{html.escape(entry["rule"])}</span>'
            f'<span>{html.escape(entry["text"])}</span>'
            f'</div>'
        )

    return (
        f'<details class="unchanged-group">'
        f'<summary>'
        f'<span class="expand-chevron">›</span>'
        f'<span>{count} unchanged {"rule" if count == 1 else "rules"}</span>'
        f'<span class="range-hint">{range_hint}</span>'
        f'</summary>'
        f'<div class="unchanged-rules-list">{"".join(rows)}</div>'
        f'</details>'
    )


def render_renumbered_group(entries, anchor_id):
    count = len(entries)
    n_ref = sum(1 for e in entries if e["status"] == "reference_renumbered")
    n_ren = count - n_ref

    if n_ref == count:
        group_label = f"{count} {'rule' if count == 1 else 'rules'} with refs updated"
        fr = html.escape(entries[0]["rule"])
        lr = html.escape(entries[-1]["rule"])
        range_hint = f"{fr} \u2014 {lr}" if count > 1 else fr
    elif n_ren == count:
        group_label = f"{count} {'rule' if count == 1 else 'rules'} renumbered"
        fo = html.escape(entries[0].get("old_rule", entries[0]["rule"]))
        lo = html.escape(entries[-1].get("old_rule", entries[-1]["rule"]))
        fn = html.escape(entries[0]["rule"])
        ln = html.escape(entries[-1]["rule"])
        range_hint = (f"{fo} \u2014 {lo} \u2192 {fn} \u2014 {ln}" if count > 1
                      else f"{fo} \u2192 {fn}")
    else:
        group_label = f"{n_ren} renumbered, {n_ref} refs updated"
        fo = html.escape(entries[0].get("old_rule", entries[0]["rule"]))
        lr = html.escape(entries[-1]["rule"])
        range_hint = f"{fo} \u2014 {lr}" if count > 1 else fo

    rows = []
    for entry in entries:
        if entry["status"] == "reference_renumbered":
            rows.append(
                f'<div class="doc-renumber-row">'
                f'<span class="doc-rule-num renumbered">{html.escape(entry["rule"])}</span>'
                f'<span class="renumber-refs-badge">refs</span>'
                f'<span class="renumber-row-text">{html.escape(entry["new_text"])}</span>'
                f'</div>'
            )
        else:
            old_r = entry.get("old_rule", entry["rule"])
            rows.append(
                f'<div class="doc-renumber-row">'
                f'<span class="doc-rule-num renumbered">{html.escape(old_r)}</span>'
                f'<span class="arrow">\u2192</span>'
                f'<span class="doc-rule-num renumbered">{html.escape(entry["rule"])}</span>'
                f'<span class="renumber-row-text">{html.escape(entry["new_text"])}</span>'
                f'</div>'
            )

    range_span = f'<span class="range-hint">{range_hint}</span>' if range_hint else ""

    return (
        f'<details class="renumber-group" id="{anchor_id}">'
        f'<summary>'
        f'<span class="expand-chevron">\u203a</span>'
        f'<span>{group_label}</span>'
        f'{range_span}'
        f'</summary>'
        f'<div class="renumber-rules-list">{"".join(rows)}</div>'
        f'</details>'
    )


def render_changed_rule(entry, anchor_id):
    status = entry["status"]
    css_class = status.replace("_", "-")

    if status == "modified":
        old_h, new_h = render_highlighted_diff(entry["old_text"], entry["new_text"])
        body = f"""
        <div class="diff-grid">
          <div><div class="version-label">Before</div><p class="rule-text">{old_h}</p></div>
          <div><div class="version-label">After</div><p class="rule-text">{new_h}</p></div>
        </div>"""
        header = (
            f'<span class="doc-rule-num {css_class}">{html.escape(entry["rule"])}</span>'
            f'<span class="change-badge modified">Modified</span>'
        )

    elif status == "added":
        body = f'<p class="rule-text">{html.escape(entry["text"])}</p>'
        header = (
            f'<span class="doc-rule-num {css_class}">{html.escape(entry["rule"])}</span>'
            f'<span class="change-badge added">Added</span>'
        )

    elif status == "removed":
        body = f'<p class="rule-text removed-text">{html.escape(entry["text"])}</p>'
        header = (
            f'<span class="doc-rule-num {css_class}">{html.escape(entry["rule"])}</span>'
            f'<span class="change-badge removed">Removed</span>'
        )

    elif status in ("renumbered", "renumbered_and_modified"):
        label = "Renumbered + Modified" if status == "renumbered_and_modified" else "Renumbered"
        badge_class = "renumbered-modified" if status == "renumbered_and_modified" else "renumbered"
        header = (
            f'<span class="doc-rule-num renumbered">{html.escape(entry["old_rule"])}</span>'
            f'<span class="arrow">→</span>'
            f'<span class="doc-rule-num renumbered">{html.escape(entry["rule"])}</span>'
            f'<span class="change-badge {badge_class}">{label}</span>'
        )
        if status == "renumbered_and_modified":
            old_h, new_h = render_highlighted_diff(entry["old_text"], entry["new_text"])
            body = f"""
            <div class="diff-grid">
              <div><div class="version-label">Before ({html.escape(entry["old_rule"])})</div><p class="rule-text">{old_h}</p></div>
              <div><div class="version-label">After ({html.escape(entry["rule"])})</div><p class="rule-text">{new_h}</p></div>
            </div>"""
        else:
            body = f'<p class="rule-text">{html.escape(entry["new_text"])}</p>'
    else:
        return ""

    return (
        f'<div class="doc-rule {css_class}" id="{anchor_id}">'
        f'<div class="rule-header">{header}</div>'
        f'{body}'
        f'</div>'
    )


_MIN_RENUMBER_GROUP = 3
_MIN_ADDED_GROUP = 3


def render_added_group(entries, anchor_id):
    count = len(entries)
    first = html.escape(entries[0]["rule"])
    last = html.escape(entries[-1]["rule"])
    range_hint = f"{first}\u2013{last}" if count > 1 else first
    summary_label = f"{count} rule{'s' if count != 1 else ''} added"

    rows = []
    for e in entries:
        rows.append(
            f'<div class="doc-renumber-row">'
            f'<span class="doc-rule-num added">{html.escape(e["rule"])}</span>'
            f'<span class="renumber-text">{html.escape(e.get("text", ""))}</span>'
            f'</div>'
        )

    return (
        f'<details class="renumber-group added-group" id="{anchor_id}">'
        f'<summary>'
        f'<span class="expand-chevron">\u203a</span>'
        f'<span>{summary_label}</span>'
        f'<span class="range-hint">{range_hint}</span>'
        f'</summary>'
        f'<div class="renumber-rows">{" ".join(rows)}</div>'
        f'</details>'
    )


def render_document_view(diff):
    all_rules = diff.get("all_rules_ordered")
    if not all_rules:
        return "<p class=\"muted\">Document view unavailable — re-run build_data.py to regenerate diff JSON.</p>"

    segments = []
    nav_items = []
    change_counter = 0
    current_unchanged = []
    current_renumbered = []  # buffer for consecutive pure-renumber entries
    current_added = []       # buffer for consecutive added entries

    def flush_unchanged():
        if current_unchanged:
            segments.append(("group", list(current_unchanged)))
            current_unchanged.clear()

    def flush_added():
        nonlocal change_counter
        if not current_added:
            return
        entries = list(current_added)
        current_added.clear()
        if len(entries) >= _MIN_ADDED_GROUP:
            change_counter += 1
            anchor_id = f"c{change_counter}"
            segments.append(("added_group", entries, anchor_id))
            nav_items.append(("added_group", {
                "first": entries[0]["rule"],
                "last":  entries[-1]["rule"],
                "count": len(entries),
            }, anchor_id))
        else:
            for entry in entries:
                change_counter += 1
                anchor_id = f"c{change_counter}"
                segments.append(("changed", entry, anchor_id))
                nav_items.append((entry["status"], entry, anchor_id))

    def flush_renumbered():
        nonlocal change_counter
        if not current_renumbered:
            return
        entries = list(current_renumbered)
        current_renumbered.clear()
        # reference_renumbered entries are always collapsed (even singletons);
        # pure-renumbered entries need at least _MIN_RENUMBER_GROUP to collapse.
        all_ref = all(e["status"] == "reference_renumbered" for e in entries)
        min_size = 1 if all_ref else _MIN_RENUMBER_GROUP
        if len(entries) >= min_size:
            change_counter += 1
            anchor_id = f"c{change_counter}"
            segments.append(("renumber_group", entries, anchor_id))
            nav_items.append(("renumbered_group", {
                "first_old": entries[0].get("old_rule", entries[0]["rule"]),
                "last_old":  entries[-1].get("old_rule", entries[-1]["rule"]),
                "first_new": entries[0]["rule"],
                "last_new":  entries[-1]["rule"],
                "count":     len(entries),
            }, anchor_id))
        else:
            for entry in entries:
                change_counter += 1
                anchor_id = f"c{change_counter}"
                segments.append(("changed", entry, anchor_id))
                nav_items.append((entry["status"], entry, anchor_id))

    for entry in all_rules:
        if entry["status"] == "unchanged":
            flush_renumbered()
            flush_added()
            current_unchanged.append(entry)
        elif entry["status"] in ("renumbered", "reference_renumbered"):
            flush_unchanged()
            flush_added()
            current_renumbered.append(entry)
        elif entry["status"] == "added":
            flush_unchanged()
            flush_renumbered()
            current_added.append(entry)
        else:
            flush_unchanged()
            flush_renumbered()
            flush_added()
            change_counter += 1
            anchor_id = f"c{change_counter}"
            segments.append(("changed", entry, anchor_id))
            nav_items.append((entry["status"], entry, anchor_id))

    flush_unchanged()
    flush_renumbered()
    flush_added()

    parts = []
    for seg in segments:
        if seg[0] == "group":
            parts.append(render_unchanged_group(seg[1]))
        elif seg[0] == "renumber_group":
            parts.append(render_renumbered_group(seg[1], seg[2]))
        elif seg[0] == "added_group":
            parts.append(render_added_group(seg[1], seg[2]))
        else:
            parts.append(render_changed_rule(seg[1], seg[2]))

    return f"""
    {render_change_nav(nav_items)}
    <div class="doc-view">
      {"".join(parts)}
    </div>
    """.strip()


def render_diff_page(diff, out_path):
    summary = diff["summary"]
    title = f"{diff['old_effective_date']} to {diff['new_effective_date']}"

    body = f"""
    <section class=\"hero\">
      <h1>{html.escape(title)}</h1>
      <p class=\"muted\">{html.escape(diff['old_file'])} → {html.escape(diff['new_file'])}</p>
      <div class=\"stat-grid\">{render_summary_cards(summary)}</div>
    </section>

    {render_document_view(diff)}
    """

    page = page_template(
        title=f"MTG Rules Diff: {title}",
        subtitle="Comprehensive Rules change report",
        content=body,
        root_rel="../",
    )
    write_text(out_path, page)


def render_index_page(releases, diff_files, out_path):
    entries = []
    for diff_file in sorted(diff_files, reverse=True):
        diff = load_json(diff_file)
        name = diff_file.stem
        entries.append(
            f"""
            <li class=\"timeline-item\">
              <a class=\"timeline-link\" href=\"releases/{name}.html\">
                <span class=\"timeline-dates\">{html.escape(diff['old_effective_date'])} → {html.escape(diff['new_effective_date'])}</span>
                <span class=\"timeline-stats\">
                  <span class=\"count-pill added\">+{diff['summary']['added']} added</span>
                  <span class=\"count-pill removed\">-{diff['summary']['removed']} removed</span>
                  <span class=\"count-pill modified\">~{diff['summary']['modified']} modified</span>
                  <span class=\"count-pill renumbered\">#{diff['summary']['renumbered']} renumbered</span>
                </span>
              </a>
            </li>
            """.strip()
        )

    release_meta = []
    for r in sorted(releases, key=lambda x: x["file_date"], reverse=True):
        release_meta.append(
            f"""
            <li>
              <span class=\"pill\">{html.escape(r['effective_date'] or r['file_date'])}</span>
              <span class=\"muted\">{html.escape(r['source_file'])}</span>
              <span class=\"muted\">{r['rule_count']} rules, {r['glossary_count']} glossary terms</span>
            </li>
            """.strip()
        )

    body = f"""
    <section class=\"hero\">
      <h1>Magic Comprehensive Rules Updates</h1>
      <p>
        Browse change reports between rules releases.
      </p>
    </section>

    <section>
      <h2>Release Diffs</h2>
      <ol class=\"timeline\">
        {' '.join(entries) if entries else '<p class="muted">No diff files found yet.</p>'}
      </ol>
    </section>

    <section>
      <h2>Tracked Rules Files</h2>
      <ul class=\"release-list\">
        {' '.join(release_meta)}
      </ul>
    </section>
    """

    page = page_template(
        title="MTG Rule Diff",
      subtitle="Comprehensive Rules update tracker",
        content=body,
        root_rel="",
    )
    write_text(out_path, page)


def write_stylesheet(path):
    css = """
:root {
  --bg: #f6f5f1;
  --paper: #fffdf8;
  --ink: #1f1b16;
  --muted: #655b4f;
  --line: #d8cfbf;
  --accent: #0f766e;
  --accent-2: #b45309;
  --good: #166534;
  --bad: #991b1b;
  --radius: 16px;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: "Avenir Next", "Gill Sans", "Trebuchet MS", sans-serif;
  color: var(--ink);
  background:
    radial-gradient(1200px 500px at -10% -20%, #d8eadf 0%, transparent 65%),
    radial-gradient(1100px 480px at 110% -10%, #f7dfc6 0%, transparent 70%),
    var(--bg);
}

.bg-orb {
  position: fixed;
  width: 280px;
  height: 280px;
  border-radius: 50%;
  filter: blur(45px);
  z-index: -1;
  opacity: 0.35;
}
.orb-a { top: 8%; left: -80px; background: #82c7ae; }
.orb-b { top: 42%; right: -100px; background: #f1b67a; }

.site-header {
  max-width: 1100px;
  margin: 0 auto;
  padding: 22px 18px 8px;
}
.brand {
  text-decoration: none;
  color: var(--ink);
  font-weight: 800;
  font-size: 1.2rem;
  letter-spacing: 0.02em;
}
.subtitle { color: var(--muted); margin-top: 6px; }

.container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 12px 18px 50px;
}

.hero {
  background: linear-gradient(140deg, #fffdf8, #fff8ee);
  border: 1px solid var(--line);
  border-radius: calc(var(--radius) + 4px);
  padding: 20px;
  margin-bottom: 24px;
  box-shadow: 0 12px 30px rgba(0, 0, 0, 0.05);
}

h1, h2, h3, h4 {
  font-family: "Palatino", "Book Antiqua", "Times New Roman", serif;
  margin-top: 0;
}
h2 { margin-top: 30px; }

.muted { color: var(--muted); }

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 10px;
  margin-top: 12px;
}
.stat-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 10px;
}
.stat-label { color: var(--muted); font-size: 0.88rem; }
.stat-value { font-size: 1.5rem; font-weight: 750; }

.timeline {
  list-style: none;
  counter-reset: diffindex;
  margin: 0;
  padding-left: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.timeline-item {
  counter-increment: diffindex;
  margin: 0;
  display: grid;
  grid-template-columns: 2.2rem 1fr;
  gap: 8px;
  align-items: center;
}
.timeline-item::before {
  content: counter(diffindex) ".";
  color: var(--muted);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  text-align: right;
}
.timeline-link {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: baseline;
  text-decoration: none;
  color: inherit;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px 12px;
  width: 100%;
}
.timeline-link:hover {
  background: #fff9ef;
}
.timeline-dates {
  font-weight: 700;
}
.timeline-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 0.9rem;
  justify-content: flex-end;
}

.count-pill {
  display: inline-flex;
  align-items: center;
  border: 1px solid #c9bc9f;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 0.82rem;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
}
.count-pill.added {
  border-color: #7cbf93;
  background: #eaf9ef;
  color: #0f5132;
}
.count-pill.removed {
  border-color: #d7a0a0;
  background: #ffefef;
  color: #7f1d1d;
}
.count-pill.modified {
  border-color: #d9c089;
  background: #fff5df;
  color: #7a4b03;
}
.count-pill.renumbered {
  border-color: #8fb9d9;
  background: #ecf6ff;
  color: #1f4d76;
}

.release-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.release-list li {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 10px;
}

.rule-detail {
  border: 1px solid var(--line);
  background: var(--paper);
  border-radius: 12px;
  padding: 8px 12px;
  margin: 10px 0;
}
.rule-detail summary {
  cursor: pointer;
  font-weight: 650;
}
.arrow { margin: 0 5px; color: var(--muted); }

.pill {
  display: inline-block;
  border: 1px solid #b6a98f;
  background: #fef5e8;
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 0.84rem;
  font-weight: 700;
}
.pill.added { border-color: #7cbf93; background: #eaf9ef; color: #0f5132; }
.pill.removed { border-color: #d7a0a0; background: #ffefef; color: #7f1d1d; }

.diff-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 10px;
}
.rule-text {
  margin: 0;
  line-height: 1.55;
  padding: 10px;
  border: 1px dashed var(--line);
  border-radius: 10px;
  background: #fff;
}

.tok-ins {
  background: #d8f6df;
  border-radius: 4px;
  box-decoration-break: clone;
}
.tok-del {
  background: #ffdede;
  border-radius: 4px;
  text-decoration: line-through;
  box-decoration-break: clone;
}

@media (max-width: 820px) {
  .diff-grid { grid-template-columns: 1fr; }
  .timeline-link { flex-direction: column; align-items: flex-start; }
  .timeline-stats { justify-content: flex-start; }
  .site-header { padding: 18px 14px 6px; }
  .container { padding: 10px 14px 40px; }
}

/* ── Document view ─────────────────────────────────────────────────────────── */

.change-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(255, 253, 248, 0.92);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border: 1px solid var(--line);
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 20px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.07);
}
.change-nav-title {
  font-size: 0.8rem;
  font-weight: 700;
  color: var(--muted);
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.change-nav-links {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  max-height: 180px;
  overflow-y: auto;
}
.change-nav-links a { text-decoration: none; }

.doc-view {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

/* Collapsed unchanged group */
.unchanged-group {
  border: none;
  background: transparent;
  padding: 0;
  margin: 0;
}
.unchanged-group > summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px dashed #c9c0af;
  color: var(--muted);
  font-size: 0.84rem;
  user-select: none;
  transition: background 0.15s;
}
.unchanged-group > summary::-webkit-details-marker { display: none; }
.unchanged-group > summary::marker { display: none; }
.unchanged-group > summary:hover { background: #f0ece4; }
.expand-chevron {
  display: inline-block;
  font-style: normal;
  font-size: 1rem;
  line-height: 1;
  transition: transform 0.18s;
  flex-shrink: 0;
}
.unchanged-group[open] > summary .expand-chevron { transform: rotate(90deg); }
.range-hint {
  font-family: "Menlo", "Monaco", monospace;
  font-size: 0.76rem;
  opacity: 0.65;
  margin-left: auto;
}
.unchanged-rules-list {
  border-left: 2px solid #d8cfbf;
  margin-left: 18px;
  padding: 4px 0;
}
.doc-rule.unchanged {
  display: grid;
  grid-template-columns: 7ch 1fr;
  gap: 10px;
  padding: 3px 12px;
  font-size: 0.87rem;
  line-height: 1.5;
}

/* Offset anchor targets below the sticky nav (updated dynamically by JS) */
.doc-rule,
.renumber-group {
  scroll-margin-top: 120px;
}

/* Changed rule cards */
.doc-rule.modified,
.doc-rule.added,
.doc-rule.removed,
.doc-rule.renumbered,
.doc-rule.renumbered-and-modified {
  border-radius: 10px;
  border: 1px solid;
  padding: 12px 14px;
  margin: 6px 0;
}
.doc-rule.modified { background: #fffdf5; border-color: #e6cc88; }
.doc-rule.added    { background: #f0faf3; border-color: #7cbf93; }
.doc-rule.removed  { background: #fff5f5; border-color: #d7a0a0; }
.doc-rule.renumbered              { background: #f0f6ff; border-color: #8fb9d9; }
.doc-rule.renumbered-and-modified { background: #f8f0ff; border-color: #c4a0d9; }

.rule-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.doc-rule-num {
  font-weight: 700;
  font-family: "Menlo", "Monaco", monospace;
  font-size: 0.88rem;
  color: var(--muted);
  white-space: nowrap;
}
.doc-rule-num.modified           { color: #7a4b03; }
.doc-rule-num.added              { color: #0f5132; }
.doc-rule-num.removed            { color: #7f1d1d; }
.doc-rule-num.renumbered         { color: #1f4d76; }
.doc-rule-num.renumbered-and-modified { color: #4b1d7a; }

.change-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 1px 8px;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.01em;
}
.change-badge.modified           { background: #fff5df; color: #7a4b03; border: 1px solid #d9c089; }
.change-badge.added              { background: #eaf9ef; color: #0f5132; border: 1px solid #7cbf93; }
.change-badge.removed            { background: #ffefef; color: #7f1d1d; border: 1px solid #d7a0a0; }
.change-badge.renumbered         { background: #ecf6ff; color: #1f4d76; border: 1px solid #8fb9d9; }
.change-badge.renumbered-modified { background: #f5edff; color: #4b1d7a; border: 1px solid #c4a0d9; }

.version-label {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--muted);
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.removed-text {
  opacity: 0.72;
  text-decoration: line-through;
  text-decoration-color: #d7a0a0;
}

/* Collapsed renumber group */
.renumber-group {
  border: none;
  background: transparent;
  padding: 0;
  margin: 3px 0;
}
.renumber-group > summary {
  cursor: pointer;
  list-style: none;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 5px 10px;
  border-radius: 8px;
  border: 1px dashed #8fb9d9;
  color: #1f4d76;
  font-size: 0.84rem;
  user-select: none;
  transition: background 0.15s;
  background: #f4f9ff;
}
.renumber-group > summary::-webkit-details-marker { display: none; }
.renumber-group > summary::marker { display: none; }
.renumber-group > summary:hover { background: #e6f1fb; }
.renumber-group[open] > summary .expand-chevron { transform: rotate(90deg); }

/* Added group — same layout as renumber-group but green */
.added-group > summary {
  border-color: #7cbf93;
  color: #0f5132;
  background: #f0faf3;
}
.added-group > summary:hover { background: #ddf3e4; }
.added-group .doc-renumber-row {
  grid-template-columns: 7ch 1fr;
  grid-template-areas: 'num text';
}
.added-group .doc-renumber-row .doc-rule-num { grid-area: num; }
.added-group .doc-renumber-row .renumber-text { grid-area: text; white-space: normal; word-break: break-word; }
.renumber-rules-list {
  border-left: 2px solid #8fb9d9;
  margin-left: 18px;
  padding: 4px 0;
}
.doc-renumber-row {
  display: grid;
  grid-template-columns: 7ch auto auto 1fr;
  gap: 6px;
  align-items: baseline;
  padding: 3px 12px;
  font-size: 0.87rem;
  line-height: 1.5;
}
.renumber-row-text {
  color: var(--muted);
  white-space: normal;
  overflow: visible;
  word-break: break-word;
}
.renumber-refs-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  padding: 1px 6px;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  background: #ecf6ff;
  color: #1f4d76;
  border: 1px solid #8fb9d9;
  white-space: nowrap;
  flex-shrink: 0;
}
""".strip()
    write_text(path, css + "\n")


def main():
    parser = argparse.ArgumentParser(description="Build static HTML from MTG diff JSON")
    parser.add_argument("--data-dir", default="html/data", help="Directory with releases.json and diffs/")
    parser.add_argument("--out-dir", default="html", help="Output HTML directory")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)

    releases_path = data_dir / "releases.json"
    diffs_dir = data_dir / "diffs"

    if not releases_path.exists():
        raise FileNotFoundError(f"Missing {releases_path}")
    if not diffs_dir.exists():
        raise FileNotFoundError(f"Missing {diffs_dir}")

    releases = load_json(releases_path)
    diff_files = sorted(diffs_dir.glob("*.json"))

    write_stylesheet(out_dir / "assets" / "styles.css")

    for diff_file in diff_files:
        diff = load_json(diff_file)
        out_path = out_dir / "releases" / f"{diff_file.stem}.html"
        render_diff_page(diff, out_path)
        print(f"Wrote {out_path}")

    render_index_page(releases, diff_files, out_dir / "index.html")
    print(f"Wrote {out_dir / 'index.html'}")


if __name__ == "__main__":
    main()
