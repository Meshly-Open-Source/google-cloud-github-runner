#!/usr/bin/env python3
"""Assert every issue template's YAML frontmatter parses and is complete.

A malformed frontmatter does NOT error on GitHub. The template is simply not
offered, silently, and the only symptom is that nobody uses it — which looks
exactly like nobody having anything to report. Same failure shape as the rest
of this fleet, so it gets a check rather than a hope.

Exit: 0 clean, 1 findings, 2 cannot analyze (no templates found at all).
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("check-issue-templates: CANNOT ANALYZE — PyYAML not installed.", file=sys.stderr)
    print("  pip install pyyaml   (or: uv run --with pyyaml python scripts/check_issue_templates.py)", file=sys.stderr)
    raise SystemExit(2)

TEMPLATE_DIR = Path(".github/ISSUE_TEMPLATE")
REQUIRED = ("name", "about")


def main() -> int:
    if not TEMPLATE_DIR.is_dir():
        print(f"check-issue-templates: CANNOT ANALYZE — {TEMPLATE_DIR} does not exist.", file=sys.stderr)
        return 2

    templates = sorted(TEMPLATE_DIR.glob("*.md"))
    if not templates:
        # Zero templates would pass every assertion below vacuously.
        print(
            f"check-issue-templates: CANNOT ANALYZE — no *.md templates in {TEMPLATE_DIR}. "
            "Every check would pass vacuously.",
            file=sys.stderr,
        )
        return 2

    findings: list[str] = []
    for f in templates:
        text = f.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            findings.append(f"{f}: no YAML frontmatter — GitHub will not offer this template")
            continue
        parts = text.split("---\n", 2)
        if len(parts) < 3:
            findings.append(f"{f}: frontmatter is not terminated by a second '---'")
            continue
        try:
            meta = yaml.safe_load(parts[1])
        except yaml.YAMLError as exc:
            findings.append(f"{f}: frontmatter is not valid YAML: {exc}")
            continue
        if not isinstance(meta, dict):
            findings.append(f"{f}: frontmatter is {type(meta).__name__}, not a mapping")
            continue
        for key in REQUIRED:
            if not meta.get(key):
                findings.append(f"{f}: missing required key {key!r}")
        print(f"  {f.name:30} name={meta.get('name')!r}")

    config = TEMPLATE_DIR / "config.yml"
    if config.is_file():
        try:
            cfg = yaml.safe_load(config.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            findings.append(f"{config}: not valid YAML: {exc}")
            cfg = {}
        for i, link in enumerate(cfg.get("contact_links") or []):
            for key in ("name", "url", "about"):
                if not (link or {}).get(key):
                    findings.append(f"{config}: contact_links[{i}] missing {key!r}")
        print(f"  {config.name:30} blank_issues_enabled={cfg.get('blank_issues_enabled')!r} "
              f"contact_links={len(cfg.get('contact_links') or [])}")

    if findings:
        print("\ncheck-issue-templates: FINDINGS", file=sys.stderr)
        for f in findings:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print(f"\ncheck-issue-templates: OK — {len(templates)} template(s) parse and are complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
