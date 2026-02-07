#!/usr/bin/env python3

import time
import random
import sys
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from collections import defaultdict

ARXIV_API_URL = "https://export.arxiv.org/api/query"
HEADERS = {
    "User-Agent": "rubenlier.nl arXiv-scraper/1.0 (contact: ruben.lier@email.com)"
}


def _iso_to_pretty_date(iso: str) -> str:
    """Convert arXiv Atom ISO datetime to '19 August 2025'."""
    if not iso:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d %B %Y").lstrip("0")
    except Exception:
        return "Unknown"


def fetch_arxiv_papers_api(author: str = "Ruben Lier", max_results: int = 100):
    params = {
        "search_query": f'au:"{author}"',
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    # --- fetch arXiv feed with retries ---
    for i in range(6):
        r = requests.get(
            ARXIV_API_URL,
            params=params,
            headers=HEADERS,
            timeout=30,
        )

        if r.status_code == 200:
            xml_text = r.text
            break

        if r.status_code not in (429, 500, 502, 503, 504):
            r.raise_for_status()

        time.sleep(min(60, 2**i) + random.random())
    else:
        raise RuntimeError(f"arXiv API failed after retries (HTTP {r.status_code})")

    root = ET.fromstring(xml_text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    papers = []

    for entry in root.findall("atom:entry", ns):
        title = (
            entry.findtext("atom:title", default="", namespaces=ns)
            .strip()
            .replace("\n", " ")
        )

        published_iso = entry.findtext("atom:published", default="", namespaces=ns) or ""
        year = published_iso[:4] if published_iso else "????"
        submission_date = _iso_to_pretty_date(published_iso)

        authors = []
        for a in entry.findall("atom:author", ns):
            name = (a.findtext("atom:name", default="", namespaces=ns) or "").strip()
            if name:
                authors.append(name)

        link_abs = ""
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("rel") == "alternate":
                link_abs = (link.attrib.get("href", "") or "").strip()
                break
        if not link_abs:
            link_abs = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()

        if not title or not link_abs:
            continue

        papers.append(
            {
                "title": title,
                "url": link_abs,
                "link": link_abs,
                "authors": authors,
                "submission_date": submission_date,
                "year": year,
            }
        )

    return papers


def generate_html(papers):
    papers_by_year = defaultdict(list)
    for p in papers:
        papers_by_year[p["year"]].append(p)

    sorted_years = sorted(papers_by_year.keys(), reverse=True)
    last_updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    html_content = f'<p><em>Last updated: {last_updated} (UTC)</em></p>\n'

    for year in sorted_years:
        html_content += (
            f'<h2 style="margin-top:20px;'
            f'border-bottom:2px solid #333;'
            f'padding-bottom:5px;">{year}</h2>\n'
        )

        for paper in papers_by_year[year]:
            authors_formatted = ", ".join(
                f"<strong>{name}</strong>"
                if name.strip().lower() == "ruben lier"
                else name
                for name in paper["authors"]
            )

            html_content += f"""
<div class="paper">
  <h3><a href="{paper['link']}" target="_blank" rel="noopener">{paper['title']}</a></h3>
  <p><strong>Authors:</strong> {authors_formatted}</p>
  <p><strong>Originally submitted:</strong> {paper['submission_date']}</p>
</div>
<hr>
"""

    with open("paper.html", "w", encoding="utf-8") as f:
        f.write(html_content.strip())

    print("✅ Generated paper.html snippet successfully!")


if __name__ == "__main__":
    papers = fetch_arxiv_papers_api()

    if not papers:
        print("❌ No papers fetched from arXiv API; refusing to overwrite paper.html.")
        sys.exit(1)

    generate_html(papers)
