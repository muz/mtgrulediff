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
  </body>
</html>
"""


def render_diff_page(diff, out_path):
    summary = diff["summary"]
    title = f"{diff['old_effective_date']} to {diff['new_effective_date']}"

    body = f"""
    <section class=\"hero\">
      <h1>{html.escape(title)}</h1>
      <p class=\"muted\">{html.escape(diff['old_file'])} → {html.escape(diff['new_file'])}</p>
      <div class=\"stat-grid\">{render_summary_cards(summary)}</div>
    </section>

    <section>
      <h2 id=\"renumbered\">Renumbered</h2>
      {render_rule_details(diff.get('renumbered', []), 'renumbered')}
    </section>

    <section>
      <h2 id=\"modified\">Modified</h2>
      {render_rule_details(diff.get('modified', []), 'modified')}
    </section>

    <section>
      <h2 id=\"added\">Added</h2>
      {render_rule_details(diff.get('added', []), 'added')}
    </section>

    <section>
      <h2 id=\"removed\">Removed</h2>
      {render_rule_details(diff.get('removed', []), 'removed')}
    </section>
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
