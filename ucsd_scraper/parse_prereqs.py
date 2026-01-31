"""
Parse prereq_raw strings into structured AND/OR form for graph building.

Run after scrape_catalog.py to enrich courses.json with prereq_structured
and build data/prereq_edges.json.

Output: prereq_structured = list of tuples.
- Each tuple = one "OR" group (satisfy at least one of these courses).
- The list = "AND" of those groups (must satisfy every tuple).
- Course codes are normalized (e.g. "MATH 20A", "CSE 12").

Example:
  "ECON 100A or ECON 120A or ECE 109; and MATH 20A"
  -> [("ECON 100A", "ECON 120A", "ECE 109"), ("MATH 20A",)]

  "ECON 1 and 3."
  -> [("ECON 1",), ("ECON 3",)]
"""

import json
import re
import os

# UCSD course code: 2-4 letter dept + space + number + optional trailing letters (e.g. MATH 31AH)
COURSE_CODE_RE = re.compile(r"[A-Z]{2,4} \d+[A-Z]*")

# Standalone number (possibly with letter) used as shorthand for "DEPT N" (e.g. "3" -> "ECON 3")
STANDALONE_NUM_RE = re.compile(r"^\d+[A-Z]?$", re.IGNORECASE)


def extract_course_codes(text: str) -> list[str]:
    """Return list of course codes found in text, in order. Normalizes spacing and strips trailing punctuation."""
    codes = []
    for m in COURSE_CODE_RE.finditer(text):
        code = m.group(0).strip()
        # Strip trailing period/comma if present (e.g. "ECON 3." -> "ECON 3")
        code = re.sub(r"[.,;]+$", "", code)
        if code and code not in codes:
            codes.append(code)
    return codes


def parse_prereq_raw(raw: str | None) -> list[tuple[str, ...]]:
    """
    Parse prereq_raw into list of OR-group tuples (AND between groups).

    - Splits by " and " to get AND segments.
    - Each segment is an OR group: extract all course codes (and handle "DEPT N and M" -> DEPT N, DEPT M).
    - Returns only course-based requirements; non-course text (e.g. "consent of instructor") is ignored.
    """
    if not raw or not raw.strip():
        return []

    text = raw.strip()
    # Only parse the first clause (before ";") to avoid "Students may not receive credit for both X and Y"
    if ";" in text:
        text = text.split(";", 1)[0].strip()
    # Normalize whitespace and common punctuation
    text = re.sub(r"\s+", " ", text)
    # Split by " and " to get AND groups (each group may contain " or " alternatives)
    and_segments = re.split(r"\s+and\s+", text, flags=re.IGNORECASE)

    result: list[tuple[str, ...]] = []
    last_dept: str | None = None

    for segment in and_segments:
        segment = segment.strip()
        if not segment:
            continue

        codes = extract_course_codes(segment)

        # Abbreviated form: "ECON 1 and 3" -> second segment is just "3" -> treat as "ECON 3"
        if not codes and last_dept and STANDALONE_NUM_RE.match(segment.rstrip(".,;")):
            short = segment.rstrip(".,;").strip()
            codes = [f"{last_dept} {short}"]

        if codes:
            result.append(tuple(codes))
            # Track department from last code in this segment (for next abbreviated segment)
            last_dept = codes[-1].split()[0]

    return result


def build_prereq_edges(courses: list[dict]) -> list[dict]:
    """
    Build edge list for a prerequisite graph: courses = nodes, prereqs = directed edges.

    Each edge: { "source": "CSE 8B", "target": "CSE 12", "or_group_index": 0 }.

    Semantics for a target course:
    - Edges with the same (target, or_group_index) form an OR group: satisfy at least one.
    - Edges with different or_group_index are AND: must satisfy one from each group.
    """
    code_to_course = {c["code"]: c for c in courses}
    edges = []

    for course in courses:
        target = course["code"]
        structured = course.get("prereq_structured") or []
        for or_group_index, or_tuple in enumerate(structured):
            for source in or_tuple:
                # Only add edge if source is a known course (node in our graph)
                if source in code_to_course:
                    edges.append({
                        "source": source,
                        "target": target,
                        "or_group_index": or_group_index,
                    })
    return edges


def main():
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    in_path = os.path.join(data_dir, "courses.json")
    out_path = os.path.join(data_dir, "courses.json")  # overwrite with enriched version
    edges_path = os.path.join(data_dir, "prereq_edges.json")

    with open(in_path) as f:
        courses = json.load(f)

    for c in courses:
        raw = c.get("prereq_raw")
        c["prereq_structured"] = parse_prereq_raw(raw)

    with open(out_path, "w") as f:
        json.dump(courses, f, indent=2)

    edges = build_prereq_edges(courses)
    with open(edges_path, "w") as f:
        json.dump(edges, f, indent=2)

    # Stats
    with_structured = sum(1 for c in courses if c.get("prereq_structured"))
    with_edges = sum(1 for c in courses if any(c.get("prereq_structured")))
    print(f"Enriched {len(courses)} courses with prereq_structured")
    print(f"Courses with at least one prereq group: {with_edges}")
    print(f"Total edges: {len(edges)}")
    print(f"Written: {out_path}")
    print(f"Edges: {edges_path}")


if __name__ == "__main__":
    main()
