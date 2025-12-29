#!/usr/bin/env python3
import argparse
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
import yaml
from bs4 import BeautifulSoup, Tag


JUNK_TEXT_PATTERNS = [
    r"^(read more|more|listen|watch|subscribe|sign in|log in|register)$",
    r"^(privacy|cookies|cookie policy|terms|contact|about|help)$",
    r"^(advert|advertisement)$",
]
JUNK_TEXT_RE = re.compile("|".join(JUNK_TEXT_PATTERNS), re.IGNORECASE)

BAD_ANCESTOR_TAGS = {"nav", "footer", "header", "aside"}
GOOD_ANCESTOR_TAGS = {"main", "article"}

DEFAULT_TIMEOUT = 20.0


@dataclass
class SourceCfg:
    name: str
    url: str
    source_continent: str = "Unknown"
    allow_url_regex: Optional[str] = None
    deny_url_regex: Optional[str] = None


def load_sources(path: str) -> List[SourceCfg]:
    with open(path, "r", encoding="utf-8") as f:
        obj = yaml.safe_load(f)
    out: List[SourceCfg] = []
    for s in obj.get("sources", []):
        out.append(
            SourceCfg(
                name=s["name"],
                url=s["url"],
                source_continent = s.get("continent", "Unknown"),
                allow_url_regex=s.get("allow_url_regex"),
                deny_url_regex=s.get("deny_url_regex"),
            )
        )
    return out


def normalize_url(u: str) -> str:
    try:
        p = urlparse(u)
        p = p._replace(fragment="")
        if p.query:
            qs = []
            for part in p.query.split("&"):
                k = part.split("=", 1)[0].lower()
                if k.startswith("utm_") or k in {"fbclid", "gclid"}:
                    continue
                qs.append(part)
            p = p._replace(query="&".join(qs))
        return urlunparse(p)
    except Exception:
        return u


def is_probably_article_url(url: str) -> bool:
    path = urlparse(url).path or ""
    if re.search(r"/\d{4}/\d{2}/\d{2}/", path):
        return True
    if len(path) > 25 and path.count("/") >= 2:
        return True
    return False


def anchor_text(a: Tag) -> str:
    return a.get_text(" ", strip=True)


def has_bad_ancestor(a: Tag) -> bool:
    cur = a
    while cur is not None and isinstance(cur, Tag):
        if cur.name in BAD_ANCESTOR_TAGS:
            return True
        cur = cur.parent
    return False


def has_good_ancestor(a: Tag) -> bool:
    cur = a
    while cur is not None and isinstance(cur, Tag):
        if cur.name in GOOD_ANCESTOR_TAGS:
            return True
        cur = cur.parent
    return False


def score_anchor(a: Tag, text: str, url: str) -> float:
    score = 0.0
    ln = len(text)

    if 25 <= ln <= 140:
        score += 3.0
    elif 15 <= ln < 25:
        score += 1.0
    elif ln > 140:
        score -= 1.0

    parent_names = {p.name for p in a.parents if isinstance(p, Tag)}
    if {"h1", "h2", "h3"} & parent_names:
        score += 4.0

    if has_good_ancestor(a):
        score += 2.0
    if has_bad_ancestor(a):
        score -= 4.0

    if is_probably_article_url(url):
        score += 1.0

    return score


def passes_url_filters(
    url: str, allow_re: Optional[re.Pattern], deny_re: Optional[re.Pattern]
) -> bool:
    if deny_re and deny_re.search(url):
        return False
    if allow_re and not allow_re.search(url):
        return False
    return True


def extract_candidates(
    html: str,
    base_url: str,
    allow: Optional[str],
    deny: Optional[str],
    max_items: int = 40,
) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")

    allow_re = re.compile(allow) if allow else None
    deny_re = re.compile(deny) if deny else None

    selectors = [
        "h1 a[href], h2 a[href], h3 a[href]",
        "article a[href]",
        "main a[href]",
        "a[href]",
    ]

    seen = set()
    scored: List[Tuple[float, Dict[str, Any]]] = []

    for sel in selectors:
        for a in soup.select(sel):
            if not isinstance(a, Tag):
                continue
            href = a.get("href")
            if not href:
                continue

            text = anchor_text(a)
            if not text:
                continue

            text_norm = re.sub(r"\s+", " ", text).strip()
            if len(text_norm) < 12:
                continue
            if JUNK_TEXT_RE.search(text_norm.lower()):
                continue

            abs_url = normalize_url(urljoin(base_url, href))
            if not abs_url.startswith(("http://", "https://")):
                continue

            if not passes_url_filters(abs_url, allow_re, deny_re):
                continue

            key = hashlib.sha1(
                (abs_url + "||" + text_norm.lower()).encode("utf-8")
            ).hexdigest()
            if key in seen:
                continue
            seen.add(key)

            s = score_anchor(a, text_norm, abs_url)
            scored.append((s, {"title": text_norm, "url": abs_url}))

        if len(scored) >= max_items * 2 and sel != "a[href]":
            break

    scored.sort(key=lambda t: t[0], reverse=True)

    by_url: Dict[str, Dict[str, Any]] = {}
    for s, item in scored:
        u = item["url"]
        if u not in by_url or s > by_url[u]["score"]:
            by_url[u] = {"score": s, **item}

    items = list(by_url.values())
    items.sort(key=lambda x: x["score"], reverse=True)
    items = items[:max_items]

    for it in items:
        it.pop("score", None)
    return items


def fetch(client: httpx.Client, url: str) -> Optional[str]:
    try:
        r = client.get(url)
        r.raise_for_status()
        ct = r.headers.get("content-type", "").lower()
        if "text/html" not in ct and "application/xhtml+xml" not in ct:
            return None
        return r.text
    except Exception:
        return None


def scrape_source(
    client: httpx.Client, src: SourceCfg, max_items: int, sleep_s: float
) -> List[Dict[str, Any]]:
    html = fetch(client, src.url)
    if html is None:
        return []

    items = extract_candidates(
        html=html,
        base_url=src.url,
        allow=src.allow_url_regex,
        deny=src.deny_url_regex,
        max_items=max_items,
    )

    ts = datetime.now(timezone.utc).isoformat()
    for it in items:
        it["source_name"] = src.name
        it["source_home"] = src.url
        it["continent"] = src.source_continent
        it["scraped_at_utc"] = ts

    time.sleep(sleep_s)
    return items


def write_json(path: str, obj: Any) -> None:
    dir_ = os.path.dirname(path)
    if dir_:
        os.makedirs(dir_, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", default="sources.yaml")
    ap.add_argument("--out", default="headlines_latest.json")
    ap.add_argument("--per_site", type=int, default=25)
    ap.add_argument("--sleep", type=float, default=1.0)
    args = ap.parse_args()

    sources = load_sources(args.sources)
    if not sources:
        print("No sources found in sources.yaml", file=sys.stderr)
        return 2

    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; LocalHeadlineBot/0.1; +https://rubenlier.nl)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.8,nl;q=0.7",
    }

    rows: List[Dict[str, Any]] = []
    with httpx.Client(timeout=DEFAULT_TIMEOUT, headers=headers, follow_redirects=True) as client:
        for src in sources:
            items = scrape_source(client, src, max_items=args.per_site, sleep_s=args.sleep)
            rows.extend(items)

    seen_url = set()
    deduped: List[Dict[str, Any]] = []
    for r in rows:
        u = normalize_url(r["url"])
        if u in seen_url:
            continue
        seen_url.add(u)
        r["url"] = u
        deduped.append(r)

    payload = {"items": deduped}
    write_json(args.out, payload)
    print(f"Wrote {len(deduped)} headlines to {args.out} (wrapped as {{'items': [...]}})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())





