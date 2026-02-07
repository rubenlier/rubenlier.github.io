import time, random
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

ARXIV_API_URL = "https://export.arxiv.org/api/query"
HEADERS = {
    "User-Agent": "rubenlier.nl arXiv-scraper/1.0 (contact: ruben.lier@email.com)"
}


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
    # ... your existing parsing loop here ...
    return papers





def generate_html(papers):
    from datetime import datetime
    from datetime import datetime, timezone
    papers_by_year = defaultdict(list)
    for p in papers:
        papers_by_year[p["year"]].append(p)
    sorted_years = sorted(papers_by_year.keys(), reverse=True)

    last_updated = datetime.utcnow().strftime("%Y-%m-%d")
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


~
