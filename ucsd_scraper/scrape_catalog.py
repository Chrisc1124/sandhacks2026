import requests
from bs4 import BeautifulSoup
import json
import time
import os
import re

CATALOG_BASE = "https://catalog.ucsd.edu"
COURSES_INDEX = f"{CATALOG_BASE}/front/courses.html"
OUT_FILE = "data/courses.json"
PER_DEPT = "data/per_department"

# Create directories if not exist
os.makedirs(PER_DEPT, exist_ok=True)

def safe_get(url):
    time.sleep(1)  # polite delay
    resp = requests.get(url)
    resp.raise_for_status()
    return resp.text

def parse_course_header(block):
    """
    Parse p.course-name block: "CSE 3. Fluency in Information Technology (4)"
    Returns dict with code, title, units or None.
    """
    text = block.get_text(separator=" ").strip()
    # Allow trailing content after closing paren (e.g. " (4)  Tag: Applications of Computing")
    m = re.match(r"^([A-Z]{2,4} \d+[A-Z]?)\.\s+(.+?)\s+\((\d+)(?:[–\-]\d+)?\)", text)
    if not m:
        return None
    code, title, units = m.groups()
    return {
        "code": code.strip(),
        "title": title.strip(),
        "units": int(units),
        "description": "",
        "prereq_raw": None,
    }


def parse_course_body(block):
    """
    Parse p.course-descriptions block: description text and "Prerequisites: ..."
    Returns (description, prereq_raw). Handles <strong><em>Prerequisites:</em></strong> in HTML.
    """
    text = block.get_text(separator=" ").strip()
    prereq_raw = None
    # Match "Prerequisites:" or "Prerequisites :  " (optional spaces around colon) and capture the rest
    prereq_m = re.search(r"Prerequisites?\s*:\s*(.+)", text, re.IGNORECASE)
    if prereq_m:
        prereq_raw = prereq_m.group(1).strip()
        text = text[: prereq_m.start()].strip()
    return text, prereq_raw

def scrape_department(path):
    """
    Scrape a single department course page. path is e.g. /courses/CSE.html
    """
    url = CATALOG_BASE + path if path.startswith("/") else CATALOG_BASE + "/" + path
    html = safe_get(url)
    soup = BeautifulSoup(html, "html.parser")

    courses = []
    # Catalog uses p.course-name (header) followed by p.course-descriptions (body + prereqs)
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

    # Write per-department file
    dept_code = path.split("/")[-1].replace(".html", "")
    with open(f"{PER_DEPT}/{dept_code}.json", "w") as f:
        json.dump(courses, f, indent=2)

    return courses

def main():
    html = safe_get(COURSES_INDEX)
    soup = BeautifulSoup(html, "html.parser")

    # Find all course department links (hrefs like /courses/XXX.html or ../courses/XXX.html)
    # Page uses <main> not div.main-content
    dept_links = []
    seen_paths = set()
    for a in soup.select("main a"):
        href = a.get("href")
        if not href or not href.endswith(".html") or "/courses/" not in href:
            continue
        # Normalize to /courses/XXX.html
        path = href.replace("../", "").replace("./", "").strip()
        if not path.startswith("/"):
            path = "/" + path
        if path not in seen_paths and path.startswith("/courses/") and path != "/courses/index.html":
            seen_paths.add(path)
            dept_links.append(path)

    all_courses = []
    seen = set()

    print(f"Found {len(dept_links)} department pages")

    for link in dept_links:
        print(f"Scraping {link} …")
        courses = scrape_department(link)
        for c in courses:
            if c["code"] not in seen:
                seen.add(c["code"])
                all_courses.append(c)


    print(f"Total courses scraped: {len(all_courses)}")

    with open(OUT_FILE, "w") as f:
        json.dump(all_courses, f, indent=2)

if __name__ == "__main__":
    main()
