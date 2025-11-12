import sys
import time
import re
from collections import defaultdict

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
    papers_by_year = defaultdict(list)
    for p in papers:
        papers_by_year[p["year"]].append(p)
    sorted_years = sorted(papers_by_year.keys(), reverse=True)

    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>My arXiv Papers</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: Arial, sans-serif; background-color: #fff; color: #333; }
.navbar { display: flex; align-items: center; padding: 10px 20px; border-bottom: 1px solid #ccc; justify-content: flex-start; }
.navbar a { text-decoration: none; color: #333; font-size: 1em; margin-right: 20px; }
.navbar a:nth-child(2) { font-weight: bold; }
.navbar a:hover { text-decoration: underline; }
.layout { display: flex; min-height: calc(100vh - 60px); }
.sidebar { width: 250px; border-right: 1px solid #ccc; padding: 20px; }
.sidebar img { width: 100%; margin-bottom: 20px; }
.social-links { list-style: none; padding: 0; }
.social-links li { margin-bottom: 15px; }
.social-links a { display: flex; align-items: center; text-decoration: none; color: #333; }
.social-links a img { width: 14px; height: 14px; margin-right: 10px; position: relative; top: 2px; }
.content { flex: 1; padding: 20px; }
.content h1 { font-size: 2em; margin-bottom: 10px; text-align: center; }
.content h2 { font-size: 1.5em; margin-top: 20px; border-bottom: 2px solid #ccc; padding-bottom: 5px; }
.paper { margin: 16px 0; }
.bold { font-weight: bold; }
</style>
</head>
<body>
<div class="navbar">
  <div style="margin-left: 250px;">
    <a href="index.html">Ruben Lier</a>
    <a href="#">Preprints</a>
    <a href="talks.html">Talks</a>
  </div>
</div>
<div class="layout">
  <div class="sidebar">
    <img src="foto save ruben.PNG" alt="Ruben's Picture">
    <ul class="social-links">
      <li><a href="https://www.uva.nl/en/profile/l/i/r.lier/r.lier.html" target="_blank">
        <img src="uvalogo.png" alt="Contact"><span>Contact</span></a></li>
      <li><a href="https://scholar.google.com/citations?user=jN3gPNkAAAAJ&hl=nl" target="_blank">
        <img src="scholarlogo.png" alt="Google Scholar"><span>Google Scholar</span></a></li>
      <li><a href="https://nl.linkedin.com/in/ruben-lier-b228b2182" target="_blank">
        <img src="https://upload.wikimedia.org/wikipedia/commons/c/ca/LinkedIn_logo_initials.png" alt="LinkedIn"><span>LinkedIn</span></a></li>
      <li><a href="https://www.goodreads.com/user/show/131725587-ruben-lier" target="_blank">
        <img src="goodreads.png" alt="Goodreads"><span>Goodreads</span></a></li>
      <li><a href="https://github.com/rubenlier" target="_blank">
        <img src="https://upload.wikimedia.org/wikipedia/commons/c/c2/GitHub_Invertocat_Logo.svg" alt="GitHub"><span>GitHub</span></a></li>
      <li><a href="https://open.spotify.com/playlist/4nSMm8TaDVlrNi4u9rzImQ" target="_blank">
        <img src="spotify.png" alt="Spotify"><span>Spotify</span></a></li>
    </ul>
  </div>
  <div class="content">
    <h1>My latest arXiv preprints</h1>
"""

    for year in sorted_years:
        html_content += f"<h2>{year}</h2>\n"
        for paper in papers_by_year[year]:
            authors_formatted = ", ".join(
                f'<span class="bold">{name}</span>' if name.strip().lower() == "ruben lier" else name
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

    html_content += """
  </div>
</div>
</body>
</html>
"""
    with open("paper.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("✅ Generated paper.html successfully!")

if __name__ == "__main__":
    papers = fetch_arxiv_papers()
    generate_html(papers)

