import os
import time
import random
import requests

ARXIV_API_URL = "https://export.arxiv.org/api/query"

# arXiv wants you to identify your client; set this in workflow env too if you like.
DEFAULT_UA = "rubenlier.nl arXiv-scraper/1.0 (contact: ruben.lier@email.com)"
USER_AGENT = os.getenv("ARXIV_USER_AGENT", DEFAULT_UA)

def _sleep_with_jitter(seconds: float) -> None:
    time.sleep(seconds + random.uniform(0.0, 0.8))

def fetch_arxiv_papers_api(
    author: str = "Ruben Lier",
    start: int = 0,
    max_results: int = 100,
    max_attempts: int = 8,
):
    """
    Fetch arXiv Atom feed for an author with retries, backoff, and polite headers.

    - Retries on: timeouts, 429, 5xx
    - Respects Retry-After when present
    - Uses separate connect/read timeouts to avoid 30s read stalls killing the job
    """
    params = {
        "search_query": f'au:"{author}"',
        "start": start,
        "max_results": max_results,
    }

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/atom+xml, text/xml;q=0.9, */*;q=0.1",
    })

    # (connect timeout, read timeout)
    timeout = (10, 90)

    base_sleep = 3.0  # arXiv API etiquette when making multiple requests

    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = session.get(ARXIV_API_URL, params=params, timeout=timeout)
            status = resp.status_code

            # Success
            if status == 200 and "<entry" in resp.text:
                return resp.text  # return raw Atom XML (parse later)

            # Throttling or transient server errors
            if status in (429, 500, 502, 503, 504):
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    sleep_s = float(retry_after)
                else:
                    # exponential backoff capped
                    sleep_s = min(120.0, base_sleep * (2 ** (attempt - 1)))
                _sleep_with_jitter(sleep_s)
                continue

            # Other non-retriable errors
            resp.raise_for_status()

            # If 200 but no entries: still return text so you can debug / handle "no papers" gracefully
            return resp.text

        except (requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ConnectionError) as e:
            last_exc = e
            sleep_s = min(120.0, base_sleep * (2 ** (attempt - 1)))
            _sleep_with_jitter(sleep_s)
            continue

    # Exhausted retries
    raise RuntimeError(f"Failed to fetch arXiv after {max_attempts} attempts") from last_exc
