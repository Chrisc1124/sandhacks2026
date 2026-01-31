"""
Audit scraped data against the live UCSD catalog.

For each department page:
- Fetches the live page and parses courses (same logic as scrape_catalog).
- Compares count and per-course (code, title, units, prereq_raw) to our courses.json.
- Reports: missing in ours, extra in ours, and field mismatches for matching codes.

Run: python validate_audit.py
Output: data/validation_report.txt and summary to stdout.
"""

import json
import os
import re
import sys

# Reuse scraper logic
from scrape_catalog import (
    CATALOG_BASE,
    COURSES_INDEX,
    safe_get,
    parse_course_header,
    parse_course_body,
)

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
COURSES_PATH = os.path.join(DATA_DIR, "courses.json")
REPORT_PATH = os.path.join(DATA_DIR, "validation_report.txt")


def get_dept_links():
    """Return list of /courses/XXX.html paths from the index page."""
    html = safe_get(COURSES_INDEX)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    dept_links = []
    seen = set()
    for a in soup.select("main a"):
        href = a.get("href")
        if not href or not href.endswith(".html") or "/courses/" not in href:
            continue
        path = href.replace("../", "").replace("./", "").strip()
        if not path.startswith("/"):
            path = "/" + path
        if path not in seen and path.startswith("/courses/") and path != "/courses/index.html":
            seen.add(path)
            dept_links.append(path)
    return dept_links


def fetch_live_courses(path):
    """Fetch department page and return list of courses (same parsing as scraper)."""
    url = CATALOG_BASE + path if path.startswith("/") else CATALOG_BASE + "/" + path
    html = safe_get(url)
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")
    courses = []
    current_header = None
    for p in soup.select("main p"):
        classes = p.get("class") or []
        if "course-name" in classes:
            current_header = parse_course_header(p)
        elif "course-descriptions" in classes and current_header:
            description, prereq_raw = parse_course_body(p)
            current_header["description"] = description
            current_header["prereq_raw"] = prereq_raw
            courses.append(current_header)
            current_header = None
    return courses


def normalize(s):
    """Normalize string for comparison: collapse whitespace, strip."""
    if s is None:
        return ""
    return " ".join(str(s).split()).strip()


def main():
    with open(COURSES_PATH) as f:
        our_courses = json.load(f)

    # Our courses by code (one course can only appear on one catalog page)
    our_by_code = {c["code"]: c for c in our_courses}

    dept_links = get_dept_links()
    lines = []
    all_expected_codes = set()
    total_missing = 0
    total_title_mismatch = 0
    total_units_mismatch = 0
    total_prereq_mismatch = 0
    depts_ok = 0
    depts_with_issues = []

    for path in sorted(dept_links):
        dept = path.replace("/courses/", "").replace(".html", "")
        live = fetch_live_courses(path)
        expected_codes = {c["code"] for c in live}
        expected_by_code = {c["code"]: c for c in live}
        all_expected_codes |= expected_codes

        # Compare by code: missing = on live page but not in our data
        missing = expected_codes - our_by_code.keys()
        # Extra = in our data but not on this page (we'll aggregate at end)
        our_codes_on_page = expected_codes & our_by_code.keys()

        total_missing += len(missing)

        title_mismatch = []
        units_mismatch = []
        prereq_mismatch = []
        for code in our_codes_on_page:
            e = expected_by_code[code]
            o = our_by_code[code]
            if normalize(e.get("title")) != normalize(o.get("title")):
                title_mismatch.append((code, e.get("title"), o.get("title")))
            if str(e.get("units")) != str(o.get("units")):
                units_mismatch.append((code, e.get("units"), o.get("units")))
            if normalize(e.get("prereq_raw")) != normalize(o.get("prereq_raw")):
                prereq_mismatch.append((code, e.get("prereq_raw"), o.get("prereq_raw")))

        total_title_mismatch += len(title_mismatch)
        total_units_mismatch += len(units_mismatch)
        total_prereq_mismatch += len(prereq_mismatch)

        ok = not missing and not title_mismatch and not units_mismatch and not prereq_mismatch
        if ok:
            depts_ok += 1
        else:
            depts_with_issues.append(dept)

        lines.append(f"\n{'='*60}")
        lines.append(f"Department: {dept} ({path})")
        lines.append(f"  Live catalog: {len(expected_codes)} courses | In our data: {len(our_codes_on_page)}")
        if missing:
            lines.append(f"  MISSING IN OURS ({len(missing)}): {sorted(missing)[:20]}{' ...' if len(missing) > 20 else ''}")
        if title_mismatch:
            lines.append(f"  TITLE MISMATCH ({len(title_mismatch)}):")
            for code, live_title, our_title in title_mismatch[:5]:
                lines.append(f"    {code}: live={repr(live_title[:60])}... ours={repr(our_title[:60])}...")
            if len(title_mismatch) > 5:
                lines.append(f"    ... and {len(title_mismatch) - 5} more")
        if units_mismatch:
            lines.append(f"  UNITS MISMATCH ({len(units_mismatch)}): {[(c, e, o) for c, e, o in units_mismatch[:10]]}")
        if prereq_mismatch:
            lines.append(f"  PREREQ MISMATCH ({len(prereq_mismatch)}):")
            for code, live_pr, our_pr in prereq_mismatch[:10]:
                live_s = (live_pr or "")[:100]
                our_s = (our_pr or "")[:100]
                lines.append(f"    {code}:")
                lines.append(f"      live: {repr(live_s)}")
                lines.append(f"      ours: {repr(our_s)}")
            if len(prereq_mismatch) > 10:
                lines.append(f"    ... and {len(prereq_mismatch) - 10} more")
        if ok:
            lines.append("  OK")

    extra_in_ours = set(our_by_code.keys()) - all_expected_codes

    # Summary at top
    summary = [
        "UCSD Catalog Validation Report",
        "=" * 60,
        f"Department pages checked: {len(dept_links)}",
        f"Departments with no issues: {depts_ok}",
        f"Departments with issues: {len(depts_with_issues)} {depts_with_issues[:15]}{' ...' if len(depts_with_issues) > 15 else ''}",
        "",
        f"Total unique courses on live catalog: {len(all_expected_codes)}",
        f"Total courses in our JSON: {len(our_courses)}",
        f"Missing in ours (on catalog but not in our data): {total_missing}",
        f"Extra in ours (in our data but not on any catalog page): {len(extra_in_ours)}",
        f"Title mismatches (matching code, different title): {total_title_mismatch}",
        f"Units mismatches (matching code, different units): {total_units_mismatch}",
        f"Prereq_raw mismatches (matching code, different prereq text): {total_prereq_mismatch}",
    ]
    if extra_in_ours:
        summary.append(f"  (sample extra: {sorted(extra_in_ours)[:10]})")
    full_report = "\n".join(summary) + "\n" + "\n".join(lines)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(full_report)

    print("\n".join(summary))
    print(f"\nFull report written to {REPORT_PATH}")
    return 0 if total_missing == 0 and len(extra_in_ours) == 0 and total_title_mismatch == 0 and total_units_mismatch == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
