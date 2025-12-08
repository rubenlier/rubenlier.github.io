import os
import requests
import html

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]

TABLE = "chat_history"

# Fill this with any substrings you want to block (case-insensitive)
DISALLOWED_PROMPT_PATTERNS = [
    "kanker",
    "nazi",
    "moeder",
    "jood",
    "neger",
    "nigger",
    "flikker",
    "fuck",
]


def is_allowed_prompt(prompt: str) -> bool:
    if not prompt:
        return False
    lower = prompt.lower()
    for bad in DISALLOWED_PROMPT_PATTERNS:
        if bad and bad.lower() in lower:
            return False
    return True


def fetch_recent_rows(limit=50):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE}"
    params = {
        # now also fetch response + timestamp
        "select": "prompt,response,created_at",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    }
    r = requests.get(url, params=params, headers=headers)
    r.raise_for_status()
    return r.json()


def build_history_html(rows, keep=5):
    filtered = []
    for row in rows:
        prompt = row.get("prompt") or ""
        if not is_allowed_prompt(prompt):
            continue
        filtered.append(row)
        if len(filtered) >= keep:
            break

    if not filtered:
        return "<p>No recent prompts yet.</p>\n"

    lines = ["<ul>"]
    for row in filtered:
        prompt = row.get("prompt") or ""
        response = row.get("response") or ""
        created_at = row.get("created_at") or ""

        # show just the date part if it's an ISO timestamp
        if "T" in created_at:
            created_display = created_at.split("T", 1)[0]
        else:
            created_display = created_at

        prompt_safe = html.escape(prompt)
        response_safe = html.escape(response)
        date_safe = html.escape(created_display)

        lines.append(
            "  <li>"
            f"<strong>{date_safe}</strong><br>"
            f"<em>Prompt:</em> {prompt_safe}<br>"
            f"<em>Holden:</em> {response_safe}"
            "</li>"
        )

    lines.append("</ul>")
    return "\n".join(lines) + "\n"


def main():
    rows = fetch_recent_rows(limit=50)
    html_snippet = build_history_html(rows, keep=5)

    out_path = "holden_history.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_snippet)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
