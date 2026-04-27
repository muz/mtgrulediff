"""Run the full MTG rules static site build pipeline.

Usage:
    python build_all.py
    python build_all.py --rules-dir rules --data-dir html/data --out-dir html
"""

import argparse
import subprocess
import sys


def run_step(command, label):
    print(f"\n==> {label}")
    print("$ " + " ".join(command))
    completed = subprocess.run(command)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main():
    parser = argparse.ArgumentParser(description="Build JSON data and static HTML pages")
    parser.add_argument("--rules-dir", default="rules", help="Directory containing rules text files")
    parser.add_argument("--data-dir", default="docs/data", help="Directory for generated JSON data")
    parser.add_argument("--out-dir", default="docs", help="Directory for generated HTML site")
    parser.add_argument(
        "--renumber-threshold",
        type=float,
        default=0.96,
        help="Similarity threshold for renumber detection (default: 0.96)",
    )
    args = parser.parse_args()

    py = sys.executable

    run_step(
        [
            py,
            "scripts/build_data.py",
            "--rules-dir",
            args.rules_dir,
            "--out-dir",
            args.data_dir,
            "--renumber-threshold",
            str(args.renumber_threshold),
        ],
        "Generating data artifacts",
    )

    run_step(
        [
            py,
            "scripts/build_site.py",
            "--data-dir",
            args.data_dir,
            "--out-dir",
            args.out_dir,
        ],
        "Generating static HTML",
    )

    print("\nBuild complete.")
    print(f"Site index: {args.out_dir}/index.html")


if __name__ == "__main__":
    main()
