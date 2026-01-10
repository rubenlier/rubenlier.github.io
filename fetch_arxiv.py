import sys
import time
import re
from collections import defaultdict
from datetime import datetime  # NEW

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# ---- Config ----
search_url = "https://arxiv.org/search/?query=ruben+Lier&searchtype=all&source=header"
USER_AGENT = "rubenlier-arxiv-bot/1.0 (+https://rubenlier.github.io)"
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 60
PAUSE_BETWEEN_REQUESTS = 0.3
# ----------------

DATE_RE = re.compile(r"(?:Submitted on|Submitted)\s+(\d{1,2}\s+\w+\s+\d{4})", re.IGNORECASE)

def make_session() -> requests.Session:
    """Create a requests session with retries + backoff and a proper UA."""
    s = requests.Session()
    retry = Retry(
        total=6,                # total attempts
        connect=3,              # connection retries
        read=6,                 # read retries
        backoff_factor=1.5,     # 1.5s, 3s, 4.5s, ...
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": USER_AGENT})
    return s

def get_original_submission_date(abs_url: str, session: requests.Session) -> str:
    """
    Fetch the abstract page and return the first (v1) submission date.
    Falls back to 'Unknown' if not found.
    """
    try:
        r = session.get(abs_url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
        if r.status_code != 200:
            return "Unknown"

        soup = BeautifulSoup(r.text, "html.parser")

        # 1) Newer arXiv HTML: <div id="submission-history"><li>...</li></div>
        hist = soup.select_one("#submission-history")
        if hist:
            lis = hist.select("li")
            if lis:
                first = lis[0].get_text(" ", strip=True)
                m = re.search(r"(\d{1,2}\s+\w+\s+\d{4})", first)
                if m:
                    return m.group(1)

        # 2) Older format: <div class="dateline">Submitted on ...</div>
        dateline = soup.select_one("div.dateline")
        if dateline:
            m = DATE_RE.search(dateline.get_text(" ", strip=True))
            if m:
                return m.group(1)

        # 3) Fallback: scan whole page
        m = DATE_RE.search(soup.get_text(" ", strip=True))
        if m:
            return m.group(1)

        return "Unknown"
    except requests.exceptions.RequestException:
        return "Unknown"


import requests
import xml.etree.ElementTree as ET

ARXIV_API_URL = "http://export.arxiv.org/api/query"

import requests
import xml.etree.ElementTree as ET
from datetime import datetime

ARXIV_API_URL = "http://export.arxiv.org/api/query"

def _iso_to_pretty_date(iso: str) -> str:
    """
    Convert arXiv Atom ISO datetime (e.g. 2025-08-19T12:34:56Z) to '19 August 2025'.
    """
    if not iso:
        return "Unknown"
    try:
        # arXiv usually uses trailing 'Z'
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        # Strip leading zero from day for nicer display
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

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; rubenlier-bot/1.0; +https://rubenlier.nl)"
    }

    r = requests.get(ARXIV_API_URL, params=params, headers=headers, timeout=30)
    r.raise_for_status()

    root = ET.fromstring(r.text)

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    papers = []
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip().replace("\n", " ")

        # published = first submission date (v1); updated = last update
        published_iso = entry.findtext("atom:published", default="", namespaces=ns) or ""
        year = published_iso[:4] if published_iso else "????"
        submission_date = _iso_to_pretty_date(published_iso)

        # Authors
        authors = []
        for a in entry.findall("atom:author", ns):
            name = (a.findtext("atom:name", default="", namespaces=ns) or "").strip()
            if name:
                authors.append(name)

        # Link to abstract page (HTML)
        link_abs = ""
        for link in entry.findall("atom:link", ns):
            if link.attrib.get("rel") == "alternate":
                link_abs = link.attrib.get("href", "")
                break
        if not link_abs:
            link_abs = entry.findtext("atom:id", default="", namespaces=ns) or ""

        papers.append({
            "title": title,
            "authors": authors,              # <-- required by generate_html
            "submission_date": submission_date,  # <-- required
            "year": year,
            "link": link_abs,                # <-- required (generate_html uses paper['link'])
        })

    return papers





def generate_html(papers):
    from datetime import datetime, timezone
    papers_by_year = defaultdict(list)
    for p in papers:
        papers_by_year[p["year"]].append(p)
    sorted_years = sorted(papers_by_year.keys(), reverse=True)

    last_updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # small header at the top of the snippet
    html_content = f'<p><em>Last updated: {last_updated} (UTC)</em></p>\n'

    for year in sorted_years:
        # 👇 add bar + spacing directly via inline style
        html_content += (
            f'<h2 style="margin-top:20px;'
            f'border-bottom:2px solid #333;'
            f'padding-bottom:5px;">{year}</h2>\n'
        )

        for paper in papers_by_year[year]:
            authors_formatted = ", ".join(
                f"<strong>{name}</strong>" if name.strip().lower() == "ruben lier" else name
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



