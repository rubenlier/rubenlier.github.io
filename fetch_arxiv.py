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

def fetch_arxiv_papers():
    papers = []
    s = make_session()
    try:
        r = s.get(search_url, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT))
    except requests.exceptions.Timeout:
        # transient; let the workflow pass quietly (optional)
        print("arXiv timed out fetching the search page; will try next run.")
        return []
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch arXiv page: {e}")
        return []

    if r.status_code != 200:
        print(f"❌ Failed to fetch arXiv page: HTTP {r.status_code}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")

    for result in soup.find_all("li", class_="arxiv-result"):
        title_tag = result.find("p", class_="title is-5 mathjax")
        link_tag = result.find("p", class_="list-title is-inline-block")
        authors_tag = result.find("p", class_="authors")

        if not (title_tag and link_tag and authors_tag):
            continue

        title = title_tag.get_text(strip=True)
        link = link_tag.find("a")["href"]

        # Ensure abstract URL
        if not re.search(r"/abs/\d", link):
            link = re.sub(r"/(pdf|format)/", "/abs/", link)

        authors = [a.get_text(strip=True) for a in authors_tag.find_all("a")]

        submission_date = get_original_submission_date(link, s)
        year = submission_date.split()[-1] if submission_date != "Unknown" else "Unknown"

        papers.append({
            "title": title,
            "link": link,
            "authors": authors,
            "submission_date": submission_date,
            "year": year
        })

        time.sleep(PAUSE_BETWEEN_REQUESTS)

    return papers


def generate_html(papers):
    from datetime import datetime
    papers_by_year = defaultdict(list)
    for p in papers:
        papers_by_year[p["year"]].append(p)
    sorted_years = sorted(papers_by_year.keys(), reverse=True)

    last_updated = datetime.utcnow().strftime("%Y-%m-%d")

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
    papers = fetch_arxiv_papers()

    # Safety guard:
    # If the arXiv fetch/parsing failed and yielded 0 papers, do NOT clobber the
    # existing paper.html on your website. Fail loudly so GitHub Actions stops.
    if not papers:
        print("❌ No papers fetched from arXiv; refusing to overwrite paper.html.")
        sys.exit(1)

    generate_html(papers)


