import os
import time
import random
import requests
import xml.etree.ElementTree as ET

ARXIV_API_URL = "https://export.arxiv.org/api/query"

DEFAULT_UA = "rubenlier.nl arXiv-scraper/1.0 (contact: ruben.lier@email.com)"
USER_AGENT = os.getenv("ARXIV_USER_AGENT", DEFAULT_UA)

HEADERS = {"User-Agent": USER_AGENT}

def fetch_arxiv_papers_api(author: str = "Ruben Lier", max_results: int = 100):
    params = {
        "search_query": f'au:"{author}"',
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    session = requests.Session()
    last_status = None
    last_exc = None

    for i in range(8):
        try:
            r = session.get(
                ARXIV_API_URL,
                params=params,
                headers=HEADERS,
                timeout=(10, 120),  # (connect timeout, read timeout)
            )
            last_status = r.status_code

            if r.status_code == 200:
                xml_text = r.text
                break

            if r.status_code not in (429, 500, 502, 503, 504):
                r.raise_for_status()

        except requests.exceptions.RequestException as e:
            last_exc = e

        time.sleep(min(60, 2**i) + random.random())

    else:
        if last_exc is not None:
            raise RuntimeError("arXiv API failed after retries due to network error") from last_exc
        raise RuntimeError(f"arXiv API failed after retries (HTTP {last_status})")

    root = ET.fromstring(xml_text)
    return root  # or continue your parsing as you already do
